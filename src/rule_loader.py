from __future__ import annotations
from pathlib import Path
import pandas as pd
from .file_reader import file_to_markdown
from .utils import normalize_text

DEFAULT_RULES = ["rules/rule_csdl.xlsx", "rules/rule_phuongan.xlsx"]

def load_rules(rule_files: list[str]) -> str:
    blocks = []
    for path in rule_files:
        blocks.append(f"# RULE FILE: {Path(path).name}\n" + file_to_markdown(path))
    return "\n\n---\n\n".join(blocks)

def parse_rule_catalog(rule_files: list[str]) -> pd.DataFrame:
    rows = []
    for path in rule_files:
        p = Path(path)
        try:
            sheets = pd.read_excel(p, sheet_name=None, dtype=str, header=None)
        except Exception:
            rows.append({"file": p.name, "sheet": "", "group": "", "rule_name": p.name, "definition": file_to_markdown(str(p))[:2000], "evidence_required": ""})
            continue
        for sheet, raw in sheets.items():
            raw = raw.fillna("")
            current_group = ""
            for _, r in raw.iterrows():
                vals = [normalize_text(x) for x in r.tolist()]
                if not any(vals):
                    continue
                first, second = (vals + ["", ""])[0], (vals + ["", ""])[1]
                if first in {"I", "II", "III", "IV", "V"} or second.lower().startswith("phương án"):
                    current_group = second or first
                    continue
                if first.lower() in {"stt", "tt"} or "nội dung" in second.lower():
                    continue
                rows.append({
                    "file": p.name,
                    "sheet": sheet,
                    "group": current_group,
                    "rule_no": first,
                    "rule_name": second or vals[1] if len(vals) > 1 else first,
                    "data_column": vals[2] if len(vals) > 2 else "",
                    "definition": vals[3] if len(vals) > 3 else (vals[2] if len(vals) > 2 else ""),
                    "evidence_required": vals[3] if len(vals) > 3 else "",
                })
    return pd.DataFrame(rows)
