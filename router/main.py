"""
Model router service. POST /route classifies the task, picks the right model
from the registry, forwards the request, and returns which model handled it
(so the UI can visibly prove auto-selection to judges).

Run: uvicorn router.main:app --port 8000 --reload
"""
import base64
from typing import Optional
import httpx
from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel

from router.registry import registry
from router.classifier import classify_task

app = FastAPI(title="SIH-26117 Model Router")


class RouteRequest(BaseModel):
    prompt: str
    task_type_override: Optional[str] = None   # let the agent force a task type when it already knows


class RouteResponse(BaseModel):
    task_type: str
    model_used: str
    response: str


@app.get("/models")
def list_models():
    return {
        "provider": registry.provider,
        "models": [m.__dict__ for m in registry.models],
        "health": registry.health_check(),
    }


@app.post("/route", response_model=RouteResponse)
def route(req: RouteRequest):
    task_type = req.task_type_override or classify_task(req.prompt)
    model = registry.get_for_task(task_type)
    text = _call_ollama(model.ollama_model, req.prompt)
    return RouteResponse(task_type=task_type, model_used=model.name, response=text)


@app.post("/route-vision", response_model=RouteResponse)
async def route_vision(prompt: str = Form(...), image: UploadFile = File(...)):
    """Separate endpoint for image-bearing requests (scanned docs, drawings, photos)."""
    task_type = "vision"
    model = registry.get_for_task(task_type)
    img_bytes = await image.read()
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    text = _call_ollama(model.ollama_model, prompt, images=[img_b64])
    return RouteResponse(task_type=task_type, model_used=model.name, response=text)


def _call_ollama(ollama_model: str, prompt: str, images: Optional[list] = None) -> str:
    payload = {"model": ollama_model, "prompt": prompt, "stream": False}
    if images:
        payload["images"] = images
    r = httpx.post(f"{registry.base_url}/api/generate", json=payload, timeout=300.0)
    r.raise_for_status()
    return r.json().get("response", "")
