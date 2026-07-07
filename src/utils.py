from __future__ import annotations
import re
import unicodedata
from pathlib import Path
from datetime import datetime

VIETNAM_TZ_LABEL = "Asia/Ho_Chi_Minh"

def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def safe_name(name: str, default: str = "bao_cao") -> str:
    raw = Path(name).stem if name else default
    raw = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii") or default
    raw = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("._")
    return raw[:80] or default

def normalize_text(value) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", " ", s)

def truthy(value) -> bool:
    s = normalize_text(value).lower()
    if not s or s in {"nan", "none", "khong", "không", "no", "n", "0", "false"}:
        return False
    return True

def to_float(value, default=None):
    s = normalize_text(value).replace(",", ".")
    m = re.search(r"-?\d+(\.\d+)?", s)
    if not m:
        return default
    try:
        return float(m.group(0))
    except ValueError:
        return default
