from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import List, Dict

# Danh sach goi y tinh. Khi can chinh xac theo tai khoan/API key, dung fetch_models().
MODEL_CATALOG: Dict[str, List[str]] = {
    "offline": ["Offline Rule Engine"],
    "openai": [
        "gpt-5.5",
        "gpt-5.4-mini",
        "gpt-5.4-nano",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-4o",
        "gpt-4o-mini",
        "o3",
        "o3-mini",
        "o4-mini",
    ],
    "gemini": [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ],
    "groq": [
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
        "qwen/qwen3-32b",
        "deepseek-r1-distill-llama-70b",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "meta-llama/llama-4-maverick-17b-128e-instruct",
    ],
    "openrouter": [
        "qwen/qwen3-8b:free",
        "qwen/qwen3-14b:free",
        "qwen/qwen3-32b:free",
        "deepseek/deepseek-r1:free",
        "deepseek/deepseek-chat:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "google/gemma-3-12b-it:free",
        "mistralai/mistral-7b-instruct:free",
    ],
    "ollama": [
        "qwen2.5:7b",
        "qwen2.5:14b",
        "qwen3:8b",
        "llama3.1:8b",
        "llama3.2:3b",
        "mistral:7b",
        "gemma2:9b",
        "deepseek-r1:7b",
    ],
    "lmstudio": [
        "local-model",
        "qwen2.5-7b-instruct",
        "llama-3.1-8b-instruct",
        "mistral-7b-instruct",
        "gemma-2-9b-it",
    ],
}

PROVIDER_BASE_URL = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
    "lmstudio": "http://localhost:1234/v1",
}


def get_static_models(provider: str) -> List[str]:
    return MODEL_CATALOG.get((provider or "").lower(), [])


def _get_json(url: str, headers: dict | None = None, timeout: int = 12) -> dict:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_models(provider: str, api_key: str = "", base_url: str = "", timeout: int = 12) -> List[str]:
    """Tra ve danh sach model kha dung theo provider.

    - OpenAI/Groq/OpenRouter/LM Studio: goi OpenAI-compatible GET /models.
    - Gemini: goi Google models endpoint va loc model generateContent.
    - Ollama: uu tien /api/tags de lay model da pull local, fallback /v1/models.
    Neu loi hoac thieu key, raise Exception de GUI thong bao va fallback catalog tinh.
    """
    provider = (provider or "").lower().strip()
    if provider == "offline":
        return get_static_models(provider)

    if provider == "gemini":
        key = api_key or os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Gemini cần API key để làm mới danh sách model.")
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        data = _get_json(url, timeout=timeout)
        models = []
        for item in data.get("models", []):
            name = item.get("name", "").replace("models/", "")
            methods = item.get("supportedGenerationMethods", [])
            if name and (not methods or "generateContent" in methods):
                models.append(name)
        return sorted(set(models))

    if provider == "ollama":
        # Ollama native endpoint khong can key va tra dung model da co tren may.
        native_base = (base_url or os.getenv("AI_BASE_URL") or "http://localhost:11434/v1").replace("/v1", "")
        try:
            data = _get_json(native_base.rstrip("/") + "/api/tags", timeout=timeout)
            models = [m.get("name") or m.get("model") for m in data.get("models", [])]
            models = [m for m in models if m]
            if models:
                return sorted(set(models))
        except Exception:
            pass

    # OpenAI-compatible providers.
    base = base_url or os.getenv("AI_BASE_URL") or PROVIDER_BASE_URL.get(provider, "")
    if not base:
        raise RuntimeError(f"Chưa có Base URL cho provider {provider}.")
    key_env = {
        "openai": "OPENAI_API_KEY",
        "groq": "GROQ_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "lmstudio": "LMSTUDIO_API_KEY",
        "ollama": "OLLAMA_API_KEY",
    }.get(provider, "AI_API_KEY")
    key = api_key or os.getenv("AI_API_KEY") or os.getenv(key_env) or ("local" if provider in {"ollama", "lmstudio"} else "")
    if provider in {"openai", "groq", "openrouter"} and not key:
        raise RuntimeError("Provider này cần API key để làm mới danh sách model.")
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    if provider == "openrouter":
        headers.update({"HTTP-Referer": "http://localhost", "X-Title": "BTS PCTT Local Tool"})
    data = _get_json(base.rstrip("/") + "/models", headers=headers, timeout=timeout)
    models = []
    for item in data.get("data", []):
        mid = item.get("id")
        if mid:
            models.append(mid)
    return sorted(set(models))


def models_help_text(provider: str) -> str:
    provider = (provider or "").lower()
    if provider == "ollama":
        return "Ollama chỉ hiện model đã pull trên máy. Ví dụ chạy: ollama pull qwen2.5:7b"
    if provider == "lmstudio":
        return "LM Studio cần bật Local Server, thường ở http://localhost:1234/v1"
    if provider in {"openai", "gemini", "groq", "openrouter"}:
        return "Muốn làm mới danh sách thật theo tài khoản, nhập API key rồi bấm 'Làm mới model'."
    return "Offline Rule Engine không cần model AI."
