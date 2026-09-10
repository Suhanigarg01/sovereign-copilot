"""
Hand-rolled ReAct loop (plan -> act -> observe, repeat) sitting on top of the
model router. Deliberately not hidden behind a heavy framework: every step is
a plain dict you can print/stream to the UI, which is what proves "agent, not
chatbot" to judges.

Each step the model must reply with STRICT JSON:
  {"thought": "...", "action": {"tool": "<name>", "args": {...}}}
or, to finish:
  {"thought": "...", "final_answer": "..."}
"""
import json
import re
import httpx

from router.registry import registry
from agent.tools import TOOL_REGISTRY, tool_specs_for_prompt, call_tool

SYSTEM_TEMPLATE = """You are an on-premise engineering/office assistant.

You solve the user's task using the available local tools.

IMPORTANT RULES:
1. Choose ONE tool at a time when you need information.
2. Never invent tool results.
3. For questions about uploaded documents, use doc_search to retrieve relevant
   information from the knowledge base.
4. After receiving useful results from doc_search, use those results to answer
   the user's question.
5. Do NOT repeatedly call doc_search for the same question.
6. Usually 1-2 doc_search calls are sufficient for a document question.
7. If the available evidence is sufficient, STOP using tools and return final_answer.
8. If a previous tool call already provided the information needed, do not call
   another tool. Synthesize the information and answer.
9. You MUST eventually return a final_answer.

Available tools:
{tool_specs}

Respond with STRICT JSON only, no markdown fences, no commentary outside the JSON.

For a tool call:
{{"thought": "<brief reasoning>", "action": {{"tool": "<tool_name>", "args": {{...}}}}}}

To finish:
{{"thought": "<brief reasoning>", "final_answer": "<the final answer text>"}}

Task: {task}
"""


def _extract_json(text: str) -> dict:
    # tolerate models that wrap JSON in ```json fences or add stray text
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model output: {text[:200]}")
    return json.loads(match.group(0))


def _call_reasoner(prompt: str) -> str:
    model = registry.get_for_task("agent_planning")
    r = httpx.post(
        f"{registry.base_url}/api/generate",
        json={"model": model.ollama_model, "prompt": prompt, "stream": False, "options": {"temperature": 0.2}},
        timeout=300.0,
        trust_env=False,  # ignore HTTP_PROXY/ALL_PROXY etc. — this is loopback-only traffic to Ollama
    )
    r.raise_for_status()
    return r.json().get("response", "")


def run_agent(task: str, max_steps: int = None):
    """
    Returns (final_answer: str, trace: list[dict]).
    Each trace entry: {"step": i, "thought": ..., "action": {...} or None,
                        "observation": ... or None, "final_answer": ... or None}
    Yield this trace to the UI as it grows to satisfy the "show the trace visibly" requirement.
    """
    max_steps = max_steps or registry.max_agent_steps
    history = []
    trace = []

    for step in range(1, max_steps + 1):
        transcript = "\n".join(
            f"Step {h['step']} thought: {h['thought']}\nAction: {h['action']}\nObservation: {h['observation']}"
            for h in history
        )
        prompt = SYSTEM_TEMPLATE.format(tool_specs=tool_specs_for_prompt(), task=task)
        if transcript:
            prompt += f"\n\nProgress so far:\n{transcript}\n\nContinue with the next step."

        raw = _call_reasoner(prompt)
        try:
            parsed = _extract_json(raw)
        except ValueError as e:
            trace.append({"step": step, "error": str(e), "raw_output": raw})
            continue  # let it retry next loop iteration with the same history

        thought = parsed.get("thought", "")

        if "final_answer" in parsed and parsed["final_answer"]:
            entry = {"step": step, "thought": thought, "action": None,
                      "observation": None, "final_answer": parsed["final_answer"]}
            trace.append(entry)
            return parsed["final_answer"], trace

        action = parsed.get("action")
        if not action or "tool" not in action:
            trace.append({"step": step, "thought": thought, "error": "No valid action or final_answer given"})
            continue

        observation = call_tool(action["tool"], action.get("args", {}))
        entry = {"step": step, "thought": thought, "action": action, "observation": observation, "final_answer": None}
        history.append(entry)
        trace.append(entry)

    return "Step limit reached without a final answer.", trace