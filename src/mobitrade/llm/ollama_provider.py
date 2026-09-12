import json
import time
import urllib.request
import urllib.error
from typing import List, Optional, Dict, Any
from mobitrade.llm.base import LocalLLMProvider

class OllamaLLMProvider(LocalLLMProvider):
    """
    Provider integrating with local Ollama runtime via HTTP API.
    Supports explicit model eviction/unloading via keep_alive=0.
    """
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        provider_version: str = "1.0.0"
    ):
        super().__init__(provider_name="OLLAMA_LOCAL", provider_version=provider_version)
        self.base_url = base_url.rstrip("/")

    def health_check(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def load_model(self, model_tag: str) -> float:
        """
        Pre-loads the model into VRAM by making a minimal generate request.
        """
        start = time.perf_counter()
        payload = json.dumps({
            "model": model_tag,
            "prompt": "",
            "keep_alive": "5m"
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                pass
        except Exception:
            pass # Preload request may return empty response

        self.currently_loaded_model = model_tag
        load_time_ms = (time.perf_counter() - start) * 1000.0
        return load_time_ms

    def unload_model(self, model_tag: str) -> float:
        """
        Immediately evicts model from GPU VRAM by setting keep_alive to 0.
        """
        start = time.perf_counter()
        payload = json.dumps({
            "model": model_tag,
            "keep_alive": 0
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                pass
        except Exception:
            pass

        if self.currently_loaded_model == model_tag:
            self.currently_loaded_model = None

        unload_time_ms = (time.perf_counter() - start) * 1000.0
        return unload_time_ms

    def generate(
        self,
        model_tag: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 30.0
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/api/generate"
        body: Dict[str, Any] = {
            "model": model_tag,
            "prompt": prompt,
            "stream": False,
            "format": "json" # Enforces JSON mode in Ollama
        }
        if system_prompt:
            body["system"] = system_prompt

        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                latency_ms = (time.perf_counter() - start) * 1000.0
                return {
                    "raw_text": data.get("response", ""),
                    "latency_ms": latency_ms,
                    "tokens_prompt": data.get("prompt_eval_count"),
                    "tokens_generated": data.get("eval_count"),
                    "metadata": {
                        "total_duration_ns": data.get("total_duration"),
                        "load_duration_ns": data.get("load_duration"),
                    }
                }
        except urllib.error.URLError as e:
            if "timed out" in str(e).lower():
                raise TimeoutError(f"Ollama generation timed out after {timeout_seconds}s")
            raise RuntimeError(f"Ollama connection error: {e}")
