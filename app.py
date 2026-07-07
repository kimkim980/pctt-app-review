from __future__ import annotations
import os
import tempfile
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

from src.file_reader import file_to_markdown
from src.rule_loader import load_rules, parse_rule_catalog, DEFAULT_RULES
from src.deterministic_engine import analyze_all_files
from src.agent import analyze_with_gpt, merge_results, build_markdown_report
from src.exporter import export_report
from src.session_store import save_session, list_sessions
from src.utils import safe_name

load_dotenv()
st.set_page_config(page_title="AI thẩm định PCTT BTS", layout="wide")
st.title("AI thẩm định phương án PCTT/UCTT trạm BTS")
st.caption("Chạy local, đọc biểu mẫu/CSDL, đối chiếu rule cứng + GPT, xuất báo cáo Word/Excel/Markdown/JSON.")

with st.sidebar:
    st.header("Cấu hình")
    model = st.text_input("Model GPT", value=os.getenv("OPENAI_MODEL", "gpt-4.1"))
    offline = st.toggle("Offline mode - không gọi GPT", value=os.getenv("OFFLINE_MODE", "0") == "1")
    if offline:
        os.environ["OFFLINE_MODE"] = "1"
    else:
        os.environ["OFFLINE_MODE"] = "0"
    st.caption("Nếu không có OPENAI_API_KEY, tool tự chạy bằng rule engine cứng.")
    st.divider()
    use_default = st.checkbox("Dùng 2 rule mặc định", value=True)
    mode = st.radio("Chế độ rule import", ["Bổ sung rule mặc định", "Thay thế toàn bộ rule"], horizontal=False)

uploaded_rules = st.file_uploader("Import file rule bổ sung/thay thế", type=["xlsx","xls","csv","docx","pdf","md","txt"], accept_multiple_files=True)
input_files = st.file_uploader("Import file cần thẩm định", type=["xlsx","xls","csv","docx","pdf","md","txt"], accept_multiple_files=True)

col_a, col_b, col_c = st.columns([1,1,2])
run_btn = col_a.button("Chạy thẩm định", type="primary", use_container_width=True)
preview_rules = col_b.button("Xem catalog rule", use_container_width=True)

if preview_rules:
    tmp_rule_paths = []
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        if use_default and mode == "Bổ sung rule mặc định":
            tmp_rule_paths.extend(DEFAULT_RULES)
        if uploaded_rules:
            if mode == "Thay thế toàn bộ rule":
                tmp_rule_paths = []
            for f in uploaded_rules:
                p = tmp / f.name
                p.write_bytes(f.getvalue())
                tmp_rule_paths.append(str(p))
        if tmp_rule_paths:
            st.dataframe(parse_rule_catalog(tmp_rule_paths), use_container_width=True)
        else:
            st.warning("Chưa có rule để xem.")

if run_btn:
    if not input_files:
        st.error("Bạn cần import ít nhất 1 file cần thẩm định.")
        st.stop()
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        rule_paths = []
        if use_default and mode == "Bổ sung rule mặc định":
            rule_paths.extend(DEFAULT_RULES)
        if uploaded_rules:
            if mode == "Thay thế toàn bộ rule":
                rule_paths = []
            for f in uploaded_rules:
                p = tmp / f.name
                p.write_bytes(f.getvalue())
                rule_paths.append(str(p))
        if not rule_paths:
            st.error("Chưa có rule để phân tích.")
            st.stop()
        input_paths, md_inputs = [], []
        progress = st.progress(0, text="Đang đọc file đầu vào...")
        for idx, f in enumerate(input_files, 1):
            p = tmp / f.name
            p.write_bytes(f.getvalue())
            input_paths.append(str(p))
            md_inputs.append(f"# INPUT FILE: {f.name}\n" + file_to_markdown(str(p)))
            progress.progress(int(idx / len(input_files) * 30), text=f"Đã chuyển markdown: {f.name}")
        progress.progress(40, text="Đang chạy rule engine cứng...")
        det = analyze_all_files(input_paths, rule_paths)
        progress.progress(60, text="Đang nạp rule...")
        rules_md = load_rules(rule_paths)
        joined_md = "\n\n---\n\n".join(md_inputs)
        progress.progress(75, text="Đang phân tích bằng GPT nếu có API key...")
        ai = analyze_with_gpt(joined_md, rules_md, det, model=model)
        result = merge_results(det, ai)
        if not result.get("report_markdown"):
            result["report_markdown"] = build_markdown_report(result)
        progress.progress(90, text="Đang xuất báo cáo...")
        base = safe_name(input_files[0].name if input_files else "bao_cao")
        paths = export_report(result, "output", base_name=f"bao_cao_{base}")
        sess = save_session(result, [f.name for f in input_files], [Path(x).name for x in rule_paths])
        progress.progress(100, text="Hoàn thành")
    st.success("Hoàn thành thẩm định")
    s = result.get("summary", {})
    m1, m2, m3 = st.columns(3)
    m1.metric("Điểm tổng", s.get("overall_score", "N/A"))
    m2.metric("Kết luận", s.get("overall_result", "N/A"))
    m3.metric("Số phát hiện", len(result.get("checks", [])))
    st.subheader("Báo cáo")
    st.markdown(result.get("report_markdown", ""))
    st.subheader("Bảng chi tiết")
    st.dataframe(result.get("checks", []), use_container_width=True)
    st.caption(f"Đã lưu phiên: {sess}")
    st.subheader("Tải báo cáo")
    for label, path in paths.items():
        with open(path, "rb") as fp:
            st.download_button(f"Tải {label.upper()}", fp, file_name=Path(path).name, use_container_width=False)

with st.expander("Lịch sử phiên gần đây"):
    sessions = list_sessions()[:10]
    if not sessions:
        st.caption("Chưa có phiên nào.")
    for p in sessions:
        st.write(p.name)
