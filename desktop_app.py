from __future__ import annotations

import os
import json
import threading
import traceback
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from src.file_reader import file_to_markdown
from src.rule_loader import load_rules, DEFAULT_RULES
from src.deterministic_engine import analyze_all_files
from src.agent import analyze_with_gpt, merge_results, PROVIDER_PRESETS
from src.model_registry import get_static_models, fetch_models, models_help_text
from src.exporter import export_report
from src.session_store import save_session

APP_DIR = Path(__file__).resolve().parent
RULE_DIR = APP_DIR / "rules"
OUTPUT_DIR = APP_DIR / "output"
SESSIONS_DIR = APP_DIR / "sessions"

SUPPORTED_FILES = [
    ("File hỗ trợ", "*.xlsx *.xls *.csv *.docx *.pdf *.md *.txt"),
    ("Excel", "*.xlsx *.xls *.csv"),
    ("Word/PDF", "*.docx *.pdf"),
    ("Text/Markdown", "*.txt *.md"),
    ("Tất cả", "*.*"),
]


def mask_secret(value: str) -> str:
    """Che API key khi hien thi log/thong bao."""
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * max(4, len(value) - 8) + value[-4:]


def sanitize_secret_text(text: str, *secrets: str) -> str:
    """Xoa API key khoi traceback, messagebox va log GUI."""
    cleaned = text or ""
    for secret in secrets:
        secret = (secret or "").strip()
        if secret:
            cleaned = cleaned.replace(secret, mask_secret(secret))
    # Gemini thuong dua key len URL dang ?key=... trong loi HTTP.
    import re
    cleaned = re.sub(r"([?&]key=)[^\s&]+", r"\1****", cleaned)
    cleaned = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]+", r"\1****", cleaned, flags=re.I)
    return cleaned

class DesktopApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Thẩm định PCTT/UCTT BTS - Local AI Tool")
        self.geometry("1100x760")
        self.minsize(980, 680)

        self.input_files: list[str] = []
        self.rule_files: list[str] = []
        self.last_result: dict | None = None
        self.last_exports: dict[str, str] = {}
        self.stop_event = threading.Event()
        self.worker_thread: threading.Thread | None = None
        self.run_started_at: float | None = None

        self.offline_var = tk.BooleanVar(value=os.getenv("OFFLINE_MODE", "0").lower() in {"1", "true", "yes"})
        self.fast_var = tk.BooleanVar(value=os.getenv("FAST_MODE", "1").lower() in {"1", "true", "yes"})
        self.provider_options = [
            "offline|Offline Rule Engine",
            "openai|OpenAI GPT",
            "gemini|Google Gemini",
            "groq|Groq",
            "openrouter|OpenRouter",
            "ollama|Ollama Local",
            "lmstudio|LM Studio Local",
        ]
        current_provider = os.getenv("AI_PROVIDER", "offline" if self.offline_var.get() else "openai").lower()
        self.provider_var = tk.StringVar(value=self._provider_display(current_provider))
        self.model_var = tk.StringVar(value=self._default_model(current_provider))
        self.model_options = get_static_models(current_provider)
        self.base_url_var = tk.StringVar(value=os.getenv("AI_BASE_URL", ""))
        self.api_key_var = tk.StringVar(value=os.getenv("AI_API_KEY", ""))
        self.timeout_var = tk.StringVar(value=os.getenv("RUN_TIMEOUT_SECONDS", "300"))
        self.status_var = tk.StringVar(value="Sẵn sàng")
        self.score_var = tk.StringVar(value="-")
        self.result_var = tk.StringVar(value="-")

        self._init_rule_files()
        self._build_ui()
        self._refresh_lists()


    def _provider_key(self) -> str:
        value = self.provider_var.get()
        if "|" in value:
            return value.split("|", 1)[0].strip().lower()
        for item in self.provider_options:
            key, label = item.split("|", 1)
            if value == label:
                return key
        return value.strip().lower() or "offline"

    def _provider_display(self, key: str) -> str:
        key = (key or "offline").lower()
        for item in getattr(self, "provider_options", []):
            k, label = item.split("|", 1)
            if k == key:
                return item
        return "offline|Offline Rule Engine"

    def _default_model(self, provider: str) -> str:
        provider = (provider or "offline").lower()
        if provider == "offline":
            return ""
        generic = os.getenv("AI_MODEL")
        if generic:
            return generic
        preset = PROVIDER_PRESETS.get(provider, {})
        env_name = preset.get("model_env")
        if env_name and os.getenv(env_name):
            return os.getenv(env_name, "")
        return preset.get("default_model", "")

    def _on_provider_changed(self, event=None):
        provider = self._provider_key()
        self.offline_var.set(provider == "offline")
        self._set_model_options(get_static_models(provider), set_default=True)
        if provider != "offline" and not self.model_var.get().strip():
            self.model_var.set(self._default_model(provider))
        if provider in PROVIDER_PRESETS:
            preset = PROVIDER_PRESETS[provider]
            if preset.get("base_url"):
                self.base_url_var.set(preset.get("base_url"))
        self.status_var.set(models_help_text(provider))

    def _set_model_options(self, models, set_default=False):
        models = [m for m in (models or []) if m]
        self.model_options = models
        if hasattr(self, "model_combo"):
            self.model_combo.configure(values=models)
        if set_default:
            current = self.model_var.get().strip()
            if models and current not in models:
                self.model_var.set(models[0])

    def refresh_models(self):
        provider = self._provider_key()
        try:
            self.status_var.set(f"Đang làm mới danh sách model: {provider}...")
            self.update_idletasks()
            models = fetch_models(
                provider=provider,
                api_key=self.api_key_var.get().strip(),
                base_url=self.base_url_var.get().strip(),
                timeout=15,
            )
            if not models:
                raise RuntimeError("Không nhận được model nào từ provider.")
            self._set_model_options(models, set_default=True)
            self.status_var.set(f"Đã tải {len(models)} model khả dụng cho {provider}.")
            messagebox.showinfo("Danh sách model", f"Đã tải {len(models)} model khả dụng cho {provider}.")
        except Exception as e:
            fallback = get_static_models(provider)
            self._set_model_options(fallback, set_default=not self.model_var.get().strip())
            self.status_var.set("Không làm mới được model, đã dùng danh sách gợi ý offline.")
            messagebox.showwarning("Không làm mới được model", f"{e}\n\nTool sẽ dùng danh sách gợi ý offline.")

    def _init_rule_files(self):
        defaults = [APP_DIR / p for p in DEFAULT_RULES]
        self.rule_files = [str(p) for p in defaults if p.exists()]

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(12, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Tool thẩm định phương án PCTT/UCTT trạm BTS", font=("Segoe UI", 15, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self.status_var).grid(row=0, column=1, sticky="e")

        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))

        left = ttk.Frame(main, padding=8)
        right = ttk.Frame(main, padding=8)
        main.add(left, weight=1)
        main.add(right, weight=2)

        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        left.rowconfigure(4, weight=1)

        ttk.Label(left, text="1. File cần thẩm định", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.input_list = tk.Listbox(left, height=9, selectmode=tk.EXTENDED)
        self.input_list.grid(row=1, column=0, sticky="nsew", pady=4)
        btns1 = ttk.Frame(left)
        btns1.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(btns1, text="Thêm file", command=self.add_input_files).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btns1, text="Xoá chọn", command=self.remove_selected_input).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btns1, text="Xoá hết", command=self.clear_input).pack(side=tk.LEFT)

        ttk.Label(left, text="2. File rule", font=("Segoe UI", 11, "bold")).grid(row=3, column=0, sticky="w")
        self.rule_list = tk.Listbox(left, height=7, selectmode=tk.EXTENDED)
        self.rule_list.grid(row=4, column=0, sticky="nsew", pady=4)
        btns2 = ttk.Frame(left)
        btns2.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(btns2, text="Thêm rule", command=self.add_rule_files).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btns2, text="Thay bằng rule mới", command=self.replace_rule_files).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btns2, text="Rule mặc định", command=self.reset_rules).pack(side=tk.LEFT)

        cfg = ttk.LabelFrame(left, text="3. Cấu hình chạy", padding=8)
        cfg.grid(row=6, column=0, sticky="ew", pady=(0, 10))
        cfg.columnconfigure(1, weight=1)
        ttk.Checkbutton(cfg, text="Fast mode - chạy nhanh, chỉ preview dữ liệu lớn", variable=self.fast_var).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(cfg, text="AI Provider:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        provider_combo = ttk.Combobox(cfg, textvariable=self.provider_var, values=self.provider_options, state="readonly")
        provider_combo.grid(row=1, column=1, sticky="ew", pady=(8, 0))
        provider_combo.bind("<<ComboboxSelected>>", self._on_provider_changed)
        ttk.Label(cfg, text="Model:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        model_row = ttk.Frame(cfg)
        model_row.grid(row=2, column=1, sticky="ew", pady=(8, 0))
        model_row.columnconfigure(0, weight=1)
        self.model_combo = ttk.Combobox(model_row, textvariable=self.model_var, values=self.model_options, state="normal")
        self.model_combo.grid(row=0, column=0, sticky="ew")
        ttk.Button(model_row, text="Làm mới model", command=self.refresh_models).grid(row=0, column=1, padx=(6, 0))
        ttk.Label(cfg, text="Base URL local/API:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(cfg, textvariable=self.base_url_var).grid(row=3, column=1, sticky="ew", pady=(8, 0))
        ttk.Label(cfg, text="API key tùy chọn:").grid(row=4, column=0, sticky="w", pady=(8, 0))
        self.api_key_entry = ttk.Entry(cfg, textvariable=self.api_key_var, show="*")
        self.api_key_entry.grid(row=4, column=1, sticky="ew", pady=(8, 0))
        ttk.Label(cfg, text="API key luôn được che bằng dấu * và không ghi ra báo cáo/log.", foreground="#666666").grid(row=5, column=1, sticky="w", pady=(2, 0))
        ttk.Label(cfg, text="Tự dừng sau (giây):").grid(row=6, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(cfg, textvariable=self.timeout_var).grid(row=6, column=1, sticky="ew", pady=(8, 0))

        runbox = ttk.Frame(left)
        runbox.grid(row=7, column=0, sticky="ew")
        self.run_button = ttk.Button(runbox, text="CHẠY THẨM ĐỊNH", command=self.run_analysis)
        self.run_button.pack(fill=tk.X, pady=(0, 6))
        self.stop_button = ttk.Button(runbox, text="DỪNG / STOP", command=self.request_stop, state=tk.DISABLED)
        self.stop_button.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(runbox, text="Mở thư mục kết quả", command=self.open_output_dir).pack(fill=tk.X)

        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)
        summary = ttk.LabelFrame(right, text="Kết luận", padding=8)
        summary.grid(row=0, column=0, sticky="ew")
        summary.columnconfigure(1, weight=1)
        ttk.Label(summary, text="Điểm tổng:").grid(row=0, column=0, sticky="w")
        ttk.Label(summary, textvariable=self.score_var, font=("Segoe UI", 12, "bold")).grid(row=0, column=1, sticky="w")
        ttk.Label(summary, text="Kết luận:").grid(row=1, column=0, sticky="w")
        ttk.Label(summary, textvariable=self.result_var, font=("Segoe UI", 12, "bold")).grid(row=1, column=1, sticky="w")

        export_box = ttk.Frame(right)
        export_box.grid(row=1, column=0, sticky="ew", pady=8)
        ttk.Button(export_box, text="Export lại báo cáo", command=self.export_again).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(export_box, text="Mở file Word", command=lambda: self.open_export("docx")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(export_box, text="Mở file Excel", command=lambda: self.open_export("xlsx")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(export_box, text="Mở Markdown", command=lambda: self.open_export("markdown")).pack(side=tk.LEFT)

        notebook = ttk.Notebook(right)
        notebook.grid(row=2, column=0, sticky="nsew")
        tab_report = ttk.Frame(notebook)
        tab_json = ttk.Frame(notebook)
        notebook.add(tab_report, text="Báo cáo")
        notebook.add(tab_json, text="JSON")
        tab_report.columnconfigure(0, weight=1)
        tab_report.rowconfigure(0, weight=1)
        tab_json.columnconfigure(0, weight=1)
        tab_json.rowconfigure(0, weight=1)
        self.report_text = tk.Text(tab_report, wrap=tk.WORD, font=("Consolas", 10))
        self.report_text.grid(row=0, column=0, sticky="nsew")
        self.json_text = tk.Text(tab_json, wrap=tk.NONE, font=("Consolas", 10))
        self.json_text.grid(row=0, column=0, sticky="nsew")

        footer = ttk.Frame(self, padding=(12, 0, 12, 10))
        footer.grid(row=2, column=0, sticky="ew")
        self.progress = ttk.Progressbar(footer, mode="indeterminate")
        self.progress.pack(fill=tk.X)

    def _refresh_lists(self):
        self.input_list.delete(0, tk.END)
        for f in self.input_files:
            self.input_list.insert(tk.END, f)
        self.rule_list.delete(0, tk.END)
        for f in self.rule_files:
            self.rule_list.insert(tk.END, f)

    def add_input_files(self):
        files = filedialog.askopenfilenames(title="Chọn file cần thẩm định", filetypes=SUPPORTED_FILES)
        for f in files:
            if f not in self.input_files:
                self.input_files.append(f)
        self._refresh_lists()

    def remove_selected_input(self):
        selected = set(self.input_list.curselection())
        self.input_files = [f for i, f in enumerate(self.input_files) if i not in selected]
        self._refresh_lists()

    def clear_input(self):
        self.input_files = []
        self._refresh_lists()

    def add_rule_files(self):
        files = filedialog.askopenfilenames(title="Chọn file rule bổ sung", filetypes=SUPPORTED_FILES)
        for f in files:
            if f not in self.rule_files:
                self.rule_files.append(f)
        self._refresh_lists()

    def replace_rule_files(self):
        files = filedialog.askopenfilenames(title="Chọn file rule thay thế", filetypes=SUPPORTED_FILES)
        if files:
            self.rule_files = list(files)
        self._refresh_lists()

    def reset_rules(self):
        self._init_rule_files()
        self._refresh_lists()

    def run_analysis(self):
        if not self.input_files:
            messagebox.showwarning("Thiếu file", "Bạn cần thêm ít nhất 1 file cần thẩm định.")
            return
        if not self.rule_files:
            messagebox.showwarning("Thiếu rule", "Bạn cần thêm ít nhất 1 file rule.")
            return
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("Đang chạy", "Tool đang thẩm định. Bấm DỪNG / STOP nếu muốn hủy phiên hiện tại.")
            return

        self.stop_event.clear()
        self.run_started_at = time.time()
        self.progress.start(10)
        self.status_var.set("Đang thẩm định...")
        self.run_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)
        self.worker_thread = threading.Thread(target=self._run_analysis_worker, daemon=True)
        self.worker_thread.start()
        self._schedule_timeout_watch()

    def request_stop(self):
        self.stop_event.set()
        self.status_var.set("Đang yêu cầu dừng... chờ tác vụ hiện tại kết thúc")
        self.stop_button.configure(state=tk.DISABLED)

    def _schedule_timeout_watch(self):
        try:
            timeout_seconds = int(float(self.timeout_var.get().strip() or "0"))
        except Exception:
            timeout_seconds = 0
        if timeout_seconds <= 0:
            return

        def watcher():
            if self.worker_thread and self.worker_thread.is_alive() and self.run_started_at:
                if time.time() - self.run_started_at >= timeout_seconds and not self.stop_event.is_set():
                    self.stop_event.set()
                    self.status_var.set(f"Tự dừng do quá {timeout_seconds} giây")
                    self.stop_button.configure(state=tk.DISABLED)
                else:
                    self.after(1000, watcher)
        self.after(1000, watcher)

    def _should_stop(self) -> bool:
        return self.stop_event.is_set()

    def _run_analysis_worker(self):
        try:
            provider = self._provider_key()
            self.offline_var.set(provider == "offline")
            os.environ["AI_PROVIDER"] = provider
            os.environ["OFFLINE_MODE"] = "1" if provider == "offline" else "0"
            os.environ["RUN_TIMEOUT_SECONDS"] = self.timeout_var.get().strip() or "300"
            os.environ["AI_TIMEOUT_SECONDS"] = self.timeout_var.get().strip() or "300"
            if self.model_var.get().strip():
                os.environ["AI_MODEL"] = self.model_var.get().strip()
                os.environ["OPENAI_MODEL"] = self.model_var.get().strip()
            if self.base_url_var.get().strip():
                os.environ["AI_BASE_URL"] = self.base_url_var.get().strip()
            else:
                os.environ.pop("AI_BASE_URL", None)
            if self.api_key_var.get().strip():
                os.environ["AI_API_KEY"] = self.api_key_var.get().strip()

            self.after(0, lambda: self.status_var.set("Đang chạy rule engine..."))
            det_result = analyze_all_files(self.input_files, self.rule_files)
            if self._should_stop():
                self.after(0, self._show_stopped)
                return

            ai_result = None
            if provider != "offline":
                self.after(0, lambda: self.status_var.set("Đang chuyển file sang Markdown preview..."))
                markdown_parts = []
                for f in self.input_files:
                    if self._should_stop():
                        self.after(0, self._show_stopped)
                        return
                    markdown_parts.append(f"# FILE: {Path(f).name}\n" + file_to_markdown(f, fast=self.fast_var.get()))
                if self._should_stop():
                    self.after(0, self._show_stopped)
                    return
                input_md = "\n\n---\n\n".join(markdown_parts)
                rules_md = load_rules(self.rule_files)
                if self._should_stop():
                    self.after(0, self._show_stopped)
                    return
                self.after(0, lambda: self.status_var.set(f"Đang gọi AI ({provider}) phân tích... Có thể bấm STOP để bỏ qua kết quả AI."))
                ai_result = analyze_with_gpt(input_md, rules_md, det_result, self.model_var.get().strip(), provider=provider)
                if self._should_stop():
                    self.after(0, self._show_stopped)
                    return
            else:
                self.after(0, lambda: self.status_var.set("Offline Rule Engine: bỏ qua AI và Markdown preview..."))

            if self._should_stop():
                self.after(0, self._show_stopped)
                return
            result = merge_results(det_result, ai_result)
            exports = export_report(result, str(OUTPUT_DIR), "bao_cao_tham_dinh_pctt_bts")
            save_session(result, [Path(x).name for x in self.input_files], [Path(x).name for x in self.rule_files])
            self.after(0, lambda: self._show_result(result, exports))
        except Exception as e:
            detail = traceback.format_exc()
            self.after(0, lambda: self._show_error(str(e), detail))

    def _show_result(self, result: dict, exports: dict[str, str]):
        self.progress.stop()
        self.last_result = result
        self.last_exports = exports
        summary = result.get("summary", {})
        self.score_var.set(str(summary.get("overall_score", "-")))
        self.result_var.set(str(summary.get("overall_result", "-")))
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert(tk.END, result.get("report_markdown", ""))
        self.json_text.delete("1.0", tk.END)
        self.json_text.insert(tk.END, json.dumps(result, ensure_ascii=False, indent=2))
        self.status_var.set("Hoàn thành. Đã export báo cáo.")
        self.run_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)
        messagebox.showinfo("Xong", "Đã thẩm định và export báo cáo vào thư mục output.")

    def _show_stopped(self):
        self.progress.stop()
        self.status_var.set("Đã dừng phiên thẩm định")
        self.run_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)
        messagebox.showinfo("Đã dừng", "Phiên thẩm định đã được dừng. Kết quả chưa hoàn tất sẽ không được export.")

    def _show_error(self, err: str, detail: str):
        self.progress.stop()
        self.status_var.set("Có lỗi")
        self.run_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)
        safe_err = sanitize_secret_text(err, self.api_key_var.get())
        safe_detail = sanitize_secret_text(detail, self.api_key_var.get())
        self.json_text.delete("1.0", tk.END)
        self.json_text.insert(tk.END, safe_detail)
        messagebox.showerror("Lỗi", safe_err)

    def export_again(self):
        if not self.last_result:
            messagebox.showwarning("Chưa có kết quả", "Bạn cần chạy thẩm định trước.")
            return
        self.last_exports = export_report(self.last_result, str(OUTPUT_DIR), "bao_cao_tham_dinh_pctt_bts")
        messagebox.showinfo("Đã export", "Đã export lại báo cáo.")

    def open_output_dir(self):
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(str(OUTPUT_DIR)) if os.name == "nt" else os.system(f'xdg-open "{OUTPUT_DIR}"')

    def open_export(self, kind: str):
        path = self.last_exports.get(kind)
        if not path or not Path(path).exists():
            messagebox.showwarning("Chưa có file", "Chưa có file export tương ứng. Hãy chạy thẩm định trước.")
            return
        os.startfile(path) if os.name == "nt" else os.system(f'xdg-open "{path}"')

if __name__ == "__main__":
    app = DesktopApp()
    app.mainloop()
