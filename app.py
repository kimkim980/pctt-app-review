from __future__ import annotations
import os
import tempfile
import json
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

from src.file_reader import file_to_markdown
from src.rule_loader import load_rules, parse_rule_catalog, DEFAULT_RULES
from src.deterministic_engine import analyze_all_files
from src.agent import analyze_with_gpt, merge_results, build_markdown_report, PROVIDER_PRESETS
from src.model_registry import get_static_models, fetch_models, models_help_text
from src.exporter import export_report
from src.session_store import save_session, list_sessions
from src.utils import safe_name

# Tải cấu hình từ .env nếu chạy cục bộ
load_dotenv()

# Cấu hình giao diện Streamlit
st.set_page_config(
    page_title="AI thẩm định PCTT BTS",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS cho phong cách thiết kế hiện đại, cao cấp
st.markdown("""
<style>
    /* Styling cho phần tiêu đề và giao diện chính */
    .main-title {
        color: #1e3a8a;
        font-family: 'Outfit', 'Inter', sans-serif;
        font-weight: 700;
        font-size: 2.2rem;
        margin-bottom: 0.1rem;
    }
    .main-caption {
        color: #4b5563;
        font-size: 1rem;
        margin-bottom: 2rem;
    }
    /* Bo góc và đổ bóng cho các metrics */
    div[data-testid="stMetric"] {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 15px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    /* Bo góc mượt mà cho các tabs */
    button[data-baseweb="tab"] {
        font-weight: 600;
        font-size: 1rem;
    }
    /* Nút tải báo cáo chuyên nghiệp */
    .stDownloadButton button {
        background-color: #2563eb !important;
        color: white !important;
        font-weight: bold;
        border-radius: 8px !important;
        border: none !important;
        transition: background-color 0.2s;
    }
    .stDownloadButton button:hover {
        background-color: #1d4ed8 !important;
    }
</style>
""", unsafe_allow_html=True)

# Hiển thị tiêu đề
st.markdown('<div class="main-title">AI Thẩm định phương án PCTT/UCTT trạm BTS</div>', unsafe_allow_html=True)
st.markdown('<div class="main-caption">Được đối chiếu song song giữa Rule Engine cứng offline và AI (GPT, Gemini, Groq, Ollama) để xuất báo cáo kiểm định.</div>', unsafe_allow_html=True)

# --- CẤU HÌNH SIDEBAR ---
with st.sidebar:
    st.header("Cấu hình hệ thống")
    
    # 1. Chọn chế độ Fast Mode
    fast_mode = st.checkbox("Fast mode - chạy nhanh, chỉ preview dữ liệu lớn", value=True)
    
    # 2. Chọn AI Provider
    provider_options = [
        "offline|Offline Rule Engine",
        "openai|OpenAI GPT",
        "gemini|Google Gemini",
        "groq|Groq",
        "openrouter|OpenRouter",
        "ollama|Ollama Local",
        "lmstudio|LM Studio Local",
    ]
    provider_labels = [p.split("|", 1)[1] for p in provider_options]
    provider_mapping = {p.split("|", 1)[1]: p.split("|", 1)[0] for p in provider_options}
    
    # Đọc provider mặc định từ env
    env_provider = os.getenv("AI_PROVIDER", "offline").lower()
    default_provider_idx = 0
    for idx, item in enumerate(provider_options):
        if item.split("|", 1)[0] == env_provider:
            default_provider_idx = idx
            break
            
    selected_label = st.selectbox("AI Provider", provider_labels, index=default_provider_idx)
    provider_key = provider_mapping[selected_label]
    
    preset = PROVIDER_PRESETS.get(provider_key, {})
    
    # Gợi ý trợ giúp tương ứng
    st.caption(models_help_text(provider_key))
    
    # 3. API Key & Base URL (chỉ hiển thị khi không chọn Offline)
    base_url_val = ""
    api_key_val = ""
    selected_model = ""
    
    if provider_key != "offline":
        # Nạp giá trị mặc định từ env
        env_base_url = os.getenv("AI_BASE_URL") or preset.get("base_url") or ""
        key_env_name = preset.get("api_key_env", "AI_API_KEY")
        env_api_key = os.getenv("AI_API_KEY") or os.getenv(key_env_name) or ""
        
        base_url_input = st.text_input("Base URL local/API", value=env_base_url)
        api_key_input = st.text_input("API key tùy chọn", value=env_api_key, type="password")
        
        base_url_val = base_url_input.strip()
        api_key_val = api_key_input.strip()
        
        # 4. Hộp chọn Model & Nút làm mới
        static_models = get_static_models(provider_key)
        
        # Cho phép làm mới danh sách model từ API
        if st.button("Làm mới danh sách model"):
            with st.spinner("Đang tải model..."):
                try:
                    fetched = fetch_models(
                        provider=provider_key,
                        api_key=api_key_val,
                        base_url=base_url_val,
                        timeout=15
                    )
                    if fetched:
                        st.session_state[f"models_{provider_key}"] = fetched
                        st.success(f"Đã tải {len(fetched)} model.")
                    else:
                        st.warning("Không tìm thấy model nào từ API.")
                except Exception as e:
                    st.error(f"Lỗi tải model: {e}")
        
        # Sử dụng danh sách model đã cache hoặc danh sách tĩnh
        active_models = st.session_state.get(f"models_{provider_key}", static_models)
        model_choices = active_models + ["Nhập model khác..."] if active_models else ["Nhập model khác..."]
        
        # Xác định model mặc định
        env_model_name = preset.get("model_env", "AI_MODEL")
        env_model = os.getenv("AI_MODEL") or os.getenv(env_model_name) or preset.get("default_model", "")
        default_model_idx = 0
        if env_model in active_models:
            default_model_idx = active_models.index(env_model)
            
        selected_model_choice = st.selectbox("Model", model_choices, index=default_model_idx)
        if selected_model_choice == "Nhập model khác...":
            selected_model = st.text_input("Nhập tên model tùy chỉnh", value=env_model)
        else:
            selected_model = selected_model_choice
            
        # 5. Cấu hình Timeout
        timeout_val = st.number_input("Tự dừng sau (giây)", min_value=5, value=300)
    else:
        timeout_val = 300
        
    st.divider()
    
    # 6. Cấu hình quy tắc (Rule)
    use_default = st.checkbox("Dùng 2 rule mặc định", value=True)
    mode = st.radio("Chế độ rule import", ["Bổ sung rule mặc định", "Thay thế toàn bộ rule"], horizontal=False)

# --- PHẦN GIAO DIỆN CHÍNH (UPLOADER & BUTTONS) ---
col_rule, col_input = st.columns(2)

with col_rule:
    st.markdown("### 1. File rule bổ sung/thay thế")
    uploaded_rules = st.file_uploader(
        "Tải lên file rule (.xlsx, .csv, .docx, .pdf, .md, .txt)",
        type=["xlsx", "xls", "csv", "docx", "pdf", "md", "txt"],
        accept_multiple_files=True,
        key="rules_uploader"
    )

with col_input:
    st.markdown("### 2. File cần thẩm định")
    input_files = st.file_uploader(
        "Tải lên các file tài liệu hoặc CSDL cần rà soát",
        type=["xlsx", "xls", "csv", "docx", "pdf", "md", "txt"],
        accept_multiple_files=True,
        key="inputs_uploader"
    )

st.write("")
col_a, col_b, _ = st.columns([1, 1, 2])
run_btn = col_a.button("Chạy thẩm định", type="primary", use_container_width=True)
preview_rules = col_b.button("Xem catalog rule", use_container_width=True)

# Xem nhanh mục lục rule
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
            st.markdown("#### Danh mục các quy tắc thẩm định đang có:")
            st.dataframe(parse_rule_catalog(tmp_rule_paths), use_container_width=True)
        else:
            st.warning("Chưa có quy tắc nào để xem. Vui lòng tick dùng mặc định hoặc import thêm.")

# --- XỬ LÝ CHẠY THẨM ĐỊNH ---
if run_btn:
    if not input_files:
        st.error("Bạn cần import ít nhất 1 file cần thẩm định.")
        st.stop()
        
    progress = st.empty()
    progress_bar = st.progress(0)
    
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        
        # Nạp danh sách rule
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
            st.error("Không tìm thấy tệp quy tắc (rule) nào. Vui lòng bật 'Dùng 2 rule mặc định' hoặc nạp file rule.")
            st.stop()
            
        # Nạp danh sách file đầu vào và dịch sang markdown
        input_paths, md_inputs = [], []
        for idx, f in enumerate(input_files, 1):
            progress.text(f"Đang đọc và chuyển đổi: {f.name}...")
            p = tmp / f.name
            p.write_bytes(f.getvalue())
            input_paths.append(str(p))
            
            # Đọc nội dung file dạng markdown (sử dụng Fast Mode nếu có tick chọn)
            md_content = file_to_markdown(str(p), fast=fast_mode)
            md_inputs.append(f"# INPUT FILE: {f.name}\n" + md_content)
            progress_bar.progress(int(idx / len(input_files) * 35))
            
        # Chạy rule engine cứng offline
        progress.text("Đang phân tích bằng Rule Engine cứng offline...")
        progress_bar.progress(45)
        det_result = analyze_all_files(input_paths, rule_paths)
        
        # Chạy AI nếu có cấu hình trực tuyến/local AI
        ai_result = None
        if provider_key != "offline":
            progress.text(f"Đang gửi yêu cầu phân tích tới AI Provider ({selected_label})...")
            progress_bar.progress(65)
            
            rules_md = load_rules(rule_paths)
            joined_md = "\n\n---\n\n".join(md_inputs)
            
            try:
                # Thiết lập biến môi trường timeout tạm thời trong luồng chạy
                os.environ["AI_TIMEOUT_SECONDS"] = str(timeout_val)
                
                ai_result = analyze_with_gpt(
                    markdown_input=joined_md,
                    rules_markdown=rules_md,
                    deterministic_result=det_result,
                    model=selected_model,
                    provider=provider_key,
                    api_key=api_key_val if api_key_val else None,
                    base_url=base_url_val if base_url_val else None
                )
            except Exception as e:
                st.error(f"Lỗi trong quá trình gọi AI: {e}. Kết quả sẽ chỉ hiển thị đánh giá của Rule Engine offline.")
                
        # Tổng hợp kết quả
        progress.text("Đang trích xuất và lưu phiên chạy...")
        progress_bar.progress(90)
        
        result = merge_results(det_result, ai_result)
        
        # Xuất các file báo cáo định dạng Docx, Xlsx, Markdown, JSON
        base = safe_name(input_files[0].name if input_files else "bao_cao")
        paths = export_report(result, "output", base_name=f"bao_cao_{base}")
        
        # Lưu session
        sess = save_session(
            result, 
            [f.name for f in input_files], 
            [Path(x).name for x in rule_paths]
        )
        
        # Ghi kết quả vào Session State để tránh mất dữ liệu khi tương tác giao diện Streamlit
        st.session_state["analysis_result"] = result
        st.session_state["analysis_paths"] = paths
        st.session_state["analysis_sess"] = sess
        
        progress.empty()
        progress_bar.empty()

# --- HIỂN THỊ KẾT QUẢ THẨM ĐỊNH ---
if "analysis_result" in st.session_state:
    result = st.session_state["analysis_result"]
    paths = st.session_state["analysis_paths"]
    sess = st.session_state["analysis_sess"]
    
    st.success(f"Hoàn thành thẩm định! Đã lưu phiên chạy: {sess}")
    
    # Grid tóm tắt chỉ số chính
    s = result.get("summary", {})
    m1, m2, m3 = st.columns(3)
    
    # Hiển thị điểm số kèm màu sắc
    score = s.get("overall_score", 100)
    m1.metric("Điểm tổng hợp", f"{score} / 100")
    
    conclusion = s.get("overall_result", "N/A")
    m2.metric("Kết luận", conclusion)
    
    findings_count = len(result.get("checks", []))
    m3.metric("Số điểm rà soát", findings_count)
    
    # Tổ chức hiển thị dữ liệu dạng Tab cao cấp
    tab_report, tab_table, tab_json = st.tabs(["📄 Báo cáo thẩm định", "📊 Bảng chi tiết lỗi", "🔍 Dữ liệu thô (JSON)"])
    
    with tab_report:
        st.markdown("### Báo cáo chi tiết")
        st.markdown(result.get("report_markdown", ""))
        
        st.divider()
        st.subheader("Tải xuống các báo cáo đã xuất")
        
        # Bố cục nút tải xuống
        col_files = st.columns(len(paths))
        for col_idx, (label, path) in enumerate(paths.items()):
            if Path(path).exists():
                with open(path, "rb") as fp:
                    col_files[col_idx].download_button(
                        label=f"Tải file {label.upper()}",
                        data=fp,
                        file_name=Path(path).name,
                        use_container_width=True,
                        key=f"dl_{label}_{col_idx}"
                    )
                    
    with tab_table:
        st.markdown("### Bảng tổng hợp chi tiết tất cả tiêu chí rà soát")
        st.dataframe(result.get("checks", []), use_container_width=True)
        
    with tab_json:
        st.markdown("### Dữ liệu JSON gốc trả về từ Engine")
        st.json(result)

# --- EXPANDER LỊCH SỬ PHIÊN CHẠY ---
with st.expander("Lịch sử 10 phiên rà soát gần đây nhất"):
    sessions = list_sessions()[:10]
    if not sessions:
        st.caption("Chưa có phiên nào được ghi nhận.")
    else:
        for p in sessions:
            st.write(f"📁 {p.name}")
