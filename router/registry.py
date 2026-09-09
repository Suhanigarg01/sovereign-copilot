"""
Loads config/models.yaml and exposes model lookup + health-check helpers.
This is the piece that makes "add a model later without redesign" literally true:
new capability = new YAML entry, nothing here changes.
"""
import yaml
import httpx
from pathlib import Path
from dataclasses import dataclass

CONFIG_PATH = Path(__file__).parent.parent / "config" / "models.yaml"


@dataclass
class ModelSpec:
    name: str
    ollama_model: str
    task_types: list
    context_window: int
    notes: str = ""


class ModelRegistry:
    def __init__(self, config_path: Path = CONFIG_PATH):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        self.base_url = cfg["runtime"]["base_url"]
        self.provider = cfg["runtime"]["provider"]
        self.default_task_type = cfg.get("default_task_type", "general")
        self.max_agent_steps = cfg.get("max_agent_steps", 8)
        self.models = [ModelSpec(**m) for m in cfg["models"]]

        # task_type -> list of ModelSpec that can handle it, in config order
        self._by_task = {}
        for m in self.models:
            for t in m.task_types:
                self._by_task.setdefault(t, []).append(m)

    def get_for_task(self, task_type: str) -> ModelSpec:
        candidates = self._by_task.get(task_type) or self._by_task.get(self.default_task_type)
        if not candidates:
            raise ValueError(f"No model registered for task_type={task_type!r} and no default fallback")
        return candidates[0]

    def get_by_name(self, name: str) -> ModelSpec:
        for m in self.models:
            if m.name == name:
                return m
        raise ValueError(f"Unknown model name: {name}")

    def health_check(self) -> dict:
        """Ping each model once (tiny prompt). Returns {model_name: True/False}."""
        results = {}
        for m in self.models:
            try:
                r = httpx.post(
                    f"{self.base_url}/api/generate",
                    json={"model": m.ollama_model, "prompt": "ping", "stream": False, "options": {"num_predict": 1}},
                    timeout=15.0,
                )
                results[m.name] = r.status_code == 200
            except Exception:
                results[m.name] = False
        return results


registry = ModelRegistry()
