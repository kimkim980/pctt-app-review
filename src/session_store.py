from __future__ import annotations
from pathlib import Path
import json
from .utils import now_stamp, safe_name

SESSION_DIR = Path("sessions")

def save_session(result: dict, input_names: list[str], rule_names: list[str]) -> Path:
    SESSION_DIR.mkdir(exist_ok=True)
    payload = {"input_files": input_names, "rule_files": rule_names, "result": result}
    path = SESSION_DIR / f"session_{now_stamp()}_{safe_name('_'.join(input_names)[:30], 'run')}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

def list_sessions() -> list[Path]:
    SESSION_DIR.mkdir(exist_ok=True)
    return sorted(SESSION_DIR.glob("session_*.json"), reverse=True)
