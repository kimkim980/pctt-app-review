from __future__ import annotations

import json
import os
import re
import urllib.request
import urllib.error
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

SYSTEM_PROMPT = """
Bạn là AI thẩm định phương án phòng chống thiên tai và ứng cứu thông tin trạm BTS.
Bạn đánh giá theo rule được cung cấp và theo kết quả rule engine cứng.
Luôn trả JSON hợp lệ theo schema:
{
  "summary": {"overall_score": 0, "overall_result": "DAT|CAN_BO_SUNG|KHONG_DAT", "key_findings": []},
  "checks": [
    {"rule_group":"", "rule_name":"", "result":"DAT|CAN_BO_SUNG|KHONG_DAT|KHONG_DU_DU_LIEU", "severity":"LOW|MEDIUM|HIGH|CRITICAL", "evidence":"", "gap":"", "recommendation":"", "source_file":"", "source_sheet":"", "source_row":"", "source_column":"", "source_cell":"", "source_value":"", "abnormal_type":""}
  ],
  "report_markdown": ""
}
Nguyên tắc: không bịa dữ liệu; nếu thiếu căn cứ thì đánh dấu KHONG_DU_DU_LIEU. Ưu tiên chỉ ra thiếu phụ lục, thiếu danh sách nhân sự, thiếu SĐT, thiếu vị trí ém quân, sai logic MPĐ/ATS, rủi ro ngập/chia cắt, TGX ắc quy không đủ.
"""

PROVIDER_PRESETS = {
    "openai": {
        "label": "OpenAI GPT",
        "base_url": None,
        "api_key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
        "default_model": "gpt-4.1",
    },
    "gemini": {
        "label": "Google Gemini",
        "api_key_env": "GEMINI_API_KEY",
        "model_env": "GEMINI_MODEL",
        "default_model": "gemini-1.5-flash",
    },
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "model_env": "GROQ_MODEL",
        "default_model": "llama-3.1-8b-instant",
    },
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "model_env": "OPENROUTER_MODEL",
        "default_model": "qwen/qwen3-8b:free",
    },
    "ollama": {
        "label": "Ollama Local",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": "OLLAMA_API_KEY",
        "model_env": "OLLAMA_MODEL",
        "default_model": "qwen2.5:7b",
    },
    "lmstudio": {
        "label": "LM Studio Local",
        "base_url": "http://localhost:1234/v1",
        "api_key_env": "LMSTUDIO_API_KEY",
        "model_env": "LMSTUDIO_MODEL",
        "default_model": "local-model",
    },
}


def _env_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


def _clean_provider(provider: str | None) -> str:
    p = (provider or os.getenv("AI_PROVIDER") or "openai").strip().lower()
    aliases = {
        "gpt": "openai",
        "openai gpt": "openai",
        "google": "gemini",
        "google gemini": "gemini",
        "ollama local": "ollama",
        "lm studio": "lmstudio",
        "lmstudio local": "lmstudio",
        "offline": "offline",
        "offline rule engine": "offline",
    }
    return aliases.get(p, p)


def _resolve_model(provider: str, model: str | None = None) -> str:
    if model and model.strip():
        return model.strip()
    generic = os.getenv("AI_MODEL")
    if generic:
        return generic.strip()
    preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["openai"])
    model_env = preset.get("model_env")
    if model_env and os.getenv(model_env):
        return os.getenv(model_env, "").strip()
    return preset.get("default_model", "gpt-4.1")


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("AI không trả nội dung.")
    try:
        return json.loads(text)
    except Exception:
        pass
    # fallback khi model bọc JSON trong ```json ... ``` hoặc có lời dẫn
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
    if match:
        return json.loads(match.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start:end + 1])
    raise ValueError("Không parse được JSON từ phản hồi AI.")


def _build_user_prompt(markdown_input: str, rules_markdown: str, deterministic_result: dict) -> str:
    return f"""
## RULES
{rules_markdown}

## KET_QUA_RULE_ENGINE_CUNG
{json.dumps(deterministic_result, ensure_ascii=False, indent=2)}

## FILE_CAN_THAM_DINH_MARKDOWN
{markdown_input}

Hãy thẩm định chi tiết. Giữ lại các lỗi của rule engine cứng, bổ sung đánh giá về nội dung thuyết minh/phụ lục và đưa khuyến nghị sửa cụ thể.
Chỉ trả về JSON hợp lệ, không thêm lời dẫn ngoài JSON.
"""


def _call_openai_compatible(provider: str, model: str, user_prompt: str, timeout_seconds: int, api_key: str | None = None, base_url: str | None = None) -> dict:
    preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["openai"])
    base_url = base_url or os.getenv("AI_BASE_URL") or preset.get("base_url")
    api_key_env = preset.get("api_key_env", "OPENAI_API_KEY")
    api_key = api_key or os.getenv("AI_API_KEY") or os.getenv(api_key_env)

    if not api_key:
        if provider in {"ollama", "lmstudio"}:
            api_key = "local"
        else:
            return None

    kwargs = {"api_key": api_key, "timeout": timeout_seconds}
    if base_url:
        kwargs["base_url"] = base_url
    if OpenAI is None:
        raise RuntimeError("Thiếu thư viện openai. Chạy setup_once.bat hoặc pip install openai.")
    client = OpenAI(**kwargs)

    extra_headers = None
    if provider == "openrouter":
        extra_headers = {
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost"),
            "X-Title": os.getenv("OPENROUTER_APP_NAME", "BTS PCTT Local Tool"),
        }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    create_kwargs = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
    }
    # Ollama/LM Studio/Groq đôi khi không hỗ trợ response_format tùy model, nên thử JSON trước rồi fallback.
    try:
        create_kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**create_kwargs, extra_headers=extra_headers)
    except Exception:
        create_kwargs.pop("response_format", None)
        resp = client.chat.completions.create(**create_kwargs, extra_headers=extra_headers)

    content = resp.choices[0].message.content or ""
    return _extract_json(content)


def _call_gemini(model: str, user_prompt: str, timeout_seconds: int, api_key: str | None = None) -> dict | None:
    api_key = api_key or os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as r:
        data = json.loads(r.read().decode("utf-8"))
    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    return _extract_json(text)


def analyze_with_gpt(markdown_input: str, rules_markdown: str, deterministic_result: dict, model: str | None = None, provider: str | None = None, api_key: str | None = None, base_url: str | None = None) -> dict | None:
    provider = _clean_provider(provider)
    if _env_bool("OFFLINE_MODE") or provider == "offline":
        return None
    timeout_seconds = int(float(os.getenv("AI_TIMEOUT_SECONDS", "300") or "300"))
    model = _resolve_model(provider, model)
    user_prompt = _build_user_prompt(markdown_input, rules_markdown, deterministic_result)

    if provider == "gemini":
        return _call_gemini(model, user_prompt, timeout_seconds, api_key=api_key)
    if provider in PROVIDER_PRESETS:
        return _call_openai_compatible(provider, model, user_prompt, timeout_seconds, api_key=api_key, base_url=base_url)


    raise ValueError(f"AI_PROVIDER không hỗ trợ: {provider}")


def merge_results(det_result: dict, ai_result: dict | None) -> dict:
    if not ai_result:
        checks = det_result.get("checks", [])
        score = det_result.get("summary", {}).get("deterministic_score", 100)
        result = "DAT" if score >= 85 else ("CAN_BO_SUNG" if score >= 60 else "KHONG_DAT")
        return {
            "summary": {"overall_score": score, "overall_result": result, "key_findings": [f"Rule engine phát hiện {det_result.get('summary',{}).get('deterministic_failed',0)} vấn đề cần xử lý."]},
            "checks": checks,
            "report_markdown": build_markdown_report({"summary": {"overall_score": score, "overall_result": result}, "checks": checks})
        }
    checks = det_result.get("checks", []) + ai_result.get("checks", [])
    ai_score = ai_result.get("summary", {}).get("overall_score", 100)
    try:
        ai_score = int(ai_score)
    except Exception:
        ai_score = 100
    det_score = int(det_result.get("summary", {}).get("deterministic_score", 100))
    score = min(ai_score, det_score)
    result = "DAT" if score >= 85 else ("CAN_BO_SUNG" if score >= 60 else "KHONG_DAT")
    merged = {
        "summary": {
            "overall_score": score,
            "overall_result": result,
            "key_findings": ai_result.get("summary", {}).get("key_findings", []) + [f"Điểm rule engine CSDL: {det_score}"]
        },
        "checks": checks,
        "report_markdown": ai_result.get("report_markdown") or ""
    }
    if not merged["report_markdown"]:
        merged["report_markdown"] = build_markdown_report(merged)
    return merged


def build_markdown_report(result: dict) -> str:
    summary = result.get("summary", {})
    lines = ["# Báo cáo thẩm định PCTT/UCTT trạm BTS", "", "## 1. Kết luận tổng hợp", ""]
    lines.append(f"- Điểm tổng: **{summary.get('overall_score','N/A')}**")
    lines.append(f"- Kết luận: **{summary.get('overall_result','N/A')}**")
    for f in summary.get("key_findings", []) or []:
        lines.append(f"- {f}")
    lines += ["", "## 2. Chi tiết phát hiện", ""]
    checks = result.get("checks", [])
    if not checks:
        lines.append("Không có phát hiện chi tiết.")
    for i, c in enumerate(checks, 1):
        lines.append(f"### {i}. {c.get('rule_name','')}")
        lines.append(f"- Nhóm rule: {c.get('rule_group','')}")
        lines.append(f"- Kết quả: **{c.get('result','')}** | Mức độ: **{c.get('severity','')}**")
        src = "/".join([str(c.get('source_file','')), str(c.get('source_sheet','')), str(c.get('source_row',''))]).strip("/")
        if src:
            lines.append(f"- Nguồn: {src}")
        if c.get('source_cell'):
            lines.append(f"- Vị trí ô: **{c.get('source_cell','')}** | Cột: {c.get('source_column','')} | Giá trị: {c.get('source_value','')}")
        if c.get('abnormal_type'):
            lines.append(f"- Loại bất thường: {c.get('abnormal_type','')}")
        lines.append(f"- Bằng chứng: {c.get('evidence','')}")
        lines.append(f"- Khoảng thiếu/rủi ro: {c.get('gap','')}")
        lines.append(f"- Khuyến nghị: {c.get('recommendation','')}")
        lines.append("")
    lines += ["## 3. Hướng xử lý ưu tiên", "", "1. Xử lý ngay các lỗi CRITICAL/HIGH trước khi phê duyệt phương án.", "2. Cập nhật phụ lục nhân sự ém quân, SĐT, vị trí, thời gian tiếp cận và danh sách MPĐ.", "3. Rà soát lại CSDL trạm có nguy cơ ngập/chia cắt và trạm TGX ắc quy thấp."]
    return "\n".join(lines)
