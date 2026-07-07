# AI thẩm định phương án PCTT/UCTT trạm BTS - bản full local

Tool local có GUI bằng Streamlit, dùng rule engine cứng + GPT làm lõi phân tích file biểu mẫu/CSDL, phục vụ thẩm định phương án phòng chống thiên tai và ứng cứu thông tin trạm BTS.

## Chức năng chính

- Import file cần thẩm định: `.xlsx`, `.xls`, `.csv`, `.docx`, `.pdf`, `.md`, `.txt`.
- Chuyển nội dung file thành Markdown để agent GPT đọc được.
- Nạp 2 rule mặc định:
  - `rules/rule_csdl.xlsx`
  - `rules/rule_phuongan.xlsx`
- Import rule bổ sung hoặc thay thế toàn bộ rule mặc định.
- Rule engine cứng kiểm tra nhanh CSDL BTS:
  - Trạm UT1/UT1_3321 thiếu nhân sự ém quân.
  - Trạm ngập/chia cắt thiếu phương án ém quân.
  - Logic ATS với phương án chạy máy nổ 3,4,5,6.
  - TGX ắc quy bằng 0 hoặc TGX thấp nhưng tiếp cận xa/khó.
  - Nhận diện thiếu trường dữ liệu tối thiểu.
- GPT phân tích thuyết minh, phụ lục, bằng chứng và khuyến nghị sửa.
- Export báo cáo `.docx`, `.xlsx`, `.md`, `.json`.
- Lưu lịch sử phiên chạy trong thư mục `sessions`.
- Có chế độ `Offline mode` không gọi GPT, chỉ chạy rule engine cứng.

## Cài đặt trên Windows

```bat
cd bts_pctt_ai_tool_full
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Mở file `.env` và điền API key nếu muốn dùng GPT:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1
OFFLINE_MODE=0
```

## Chạy tool

```bat
streamlit run app.py
```

Sau đó trình duyệt sẽ mở giao diện import file.

## Cách dùng nhanh

1. Giữ tick **Dùng 2 rule mặc định**.
2. Import file CSDL hoặc phương án cần thẩm định.
3. Nếu có rule mới, import tại mục **Import file rule bổ sung/thay thế**.
4. Chọn:
   - **Bổ sung rule mặc định**: dùng rule mới cộng với 2 rule gốc.
   - **Thay thế toàn bộ rule**: chỉ dùng rule mới.
5. Bấm **Chạy thẩm định**.
6. Tải báo cáo Word/Excel/Markdown/JSON.

## Gợi ý chuẩn hóa file CSDL để rule engine bắt chính xác hơn

Tool có tự nhận diện header gần đúng, nhưng nên có các nhóm cột sau:

| Nhóm dữ liệu | Ví dụ header |
|---|---|
| Mã trạm | Mã trạm, Site code, Tên trạm |
| Ưu tiên | UT, Ưu tiên, Loại trạm |
| Nhân sự ém quân | Ém quân, Nhân sự, DS ém quân, Người trực |
| Ngập lụt | Ngập, Nguy cơ ngập, Lụt |
| Chia cắt | Chia cắt, Cô lập, Khó tiếp cận |
| ATS | ATS |
| Phương án MPĐ | PA CMN, Phương án chạy máy nổ, MPĐ |
| TGX ắc quy | TGX, Thời gian xả, Ắc quy |
| Khoảng cách | Khoảng cách, km, cự ly |
| Thời gian tiếp cận | Thời gian tiếp cận, tiếp cận |

## Cấu trúc project

```text
bts_pctt_ai_tool_full/
├─ app.py
├─ requirements.txt
├─ .env.example
├─ README.md
├─ rules/
│  ├─ rule_csdl.xlsx
│  └─ rule_phuongan.xlsx
├─ src/
│  ├─ file_reader.py
│  ├─ rule_loader.py
│  ├─ deterministic_engine.py
│  ├─ agent.py
│  ├─ exporter.py
│  ├─ session_store.py
│  └─ utils.py
├─ output/
└─ sessions/
```

## Lưu ý vận hành

- File PDF scan ảnh cần OCR riêng; bản này đọc tốt PDF có text layer.
- GPT không thay thế hoàn toàn kiểm tra nghiệp vụ. Các lỗi CSDL quan trọng đã được rule engine cứng bắt trước, GPT dùng để phân tích ngữ cảnh, thiếu phụ lục và khuyến nghị chỉnh sửa.
- Không đưa dữ liệu mật lên API nếu chính sách nội bộ chưa cho phép. Khi cần, bật Offline mode hoặc triển khai model nội bộ.


## Chạy như app desktop Windows

Không cần mở trình duyệt. Dùng file sau:

```bat
run_desktop.bat
```

App desktop hỗ trợ:

- Chọn nhiều file cần thẩm định
- Thêm rule bổ sung hoặc thay thế rule mặc định
- Bật/tắt Offline mode ngay trong app
- Xem kết luận, báo cáo Markdown và JSON trực tiếp trong cửa sổ phần mềm
- Export báo cáo Word, Excel, Markdown, JSON vào thư mục `output`

### Chạy offline hoàn toàn

Trong app, tick chọn **Chạy offline, không gọi GPT**. Khi đó phần mềm chỉ dùng rule engine cứng, không cần `OPENAI_API_KEY`.

### Đóng gói thành file .exe

Muốn biến thành file chạy độc lập dạng phần mềm Windows:

```bat
build_exe.bat
```

Sau khi chạy xong, file nằm tại:

```text
dist\BTS_PCTT_ThamDinh.exe
```

## Sua loi exe thieu pandas

Neu chay file `.exe` gap loi:

```text
ModuleNotFoundError: No module named 'pandas'
```

Hay chay lai file:

```bat
fix_pandas_and_rebuild.bat
```

Hoac chay truc tiep ban source khong can build exe:

```bat
run_desktop.bat
```


## Vá lỗi tabulate trong bản EXE
Nếu gặp lỗi `Import tabulate failed`, chạy:

```bat
fix_tabulate_and_rebuild.bat
```

Bản này cũng đã có fallback: nếu EXE vẫn thiếu tabulate thì app sẽ tự chuyển bảng sang dạng text để không bị crash.


## Chạy app desktop không hiện CMD

- Double click `run_desktop.bat` hoặc `run_desktop_silent.vbs` để mở app ở chế độ ẩn cửa sổ lệnh.
- Nếu cần xem lỗi/debug, chạy `run_desktop_debug.bat`.
- Chế độ silent dùng `pythonw.exe`, nên giao diện app vẫn mở nhưng log CMD sẽ không hiện.

## Bản Fast Mode

Bản này đã tối ưu tốc độ chạy desktop:

- Offline mode sẽ bỏ qua hoàn toàn bước chuyển Markdown và GPT, chỉ chạy rule engine.
- Thêm nút **Fast mode - chạy nhanh, chỉ preview dữ liệu lớn**.
- Excel/PDF lớn chỉ chuyển phần preview sang Markdown khi gọi GPT; rule engine vẫn đọc file để kiểm tra logic.
- Có cache Markdown trong thư mục `.cache`, chạy lại cùng file sẽ nhanh hơn.
- Sửa lỗi `to_markdown()` gây chậm/crash khi thiếu `tabulate`.

Khuyến nghị: với CSDL BTS lớn, bật **Chạy offline** + **Fast mode**.


## Chức năng Stop / tự dừng

- Trong app desktop có nút **DỪNG / STOP** để yêu cầu hủy phiên thẩm định đang chạy.
- Có ô **Tự dừng sau (giây)**, mặc định 300 giây. Nhập `0` để tắt tự dừng.
- Khi đang gọi GPT, app sẽ đặt timeout theo số giây này. Nếu bấm STOP giữa lúc GPT đang phản hồi, app sẽ bỏ qua kết quả GPT sau khi tác vụ hiện tại kết thúc.
- Khuyến nghị CSDL lớn: bật **Chạy offline** + **Fast mode** và đặt tự dừng 120-300 giây.

## Chọn AI Provider thay GPT

Bản này đã thêm mục **AI Provider** trong app desktop:

- `Offline Rule Engine`: không gọi AI, chạy nhanh nhất.
- `OpenAI GPT`: dùng `OPENAI_API_KEY`.
- `Google Gemini`: dùng `GEMINI_API_KEY`.
- `Groq`: dùng `GROQ_API_KEY`.
- `OpenRouter`: dùng `OPENROUTER_API_KEY`, có thể chọn model free nếu tài khoản hỗ trợ.
- `Ollama Local`: chạy AI local qua `http://localhost:11434/v1`.
- `LM Studio Local`: chạy AI local qua `http://localhost:1234/v1`.

### Cấu hình nhanh Ollama local

Cài Ollama, sau đó chạy model:

```bat
ollama pull qwen2.5:7b
ollama run qwen2.5:7b
```

Trong app chọn:

```text
AI Provider: ollama|Ollama Local
Model: qwen2.5:7b
Base URL: http://localhost:11434/v1
API key: để trống hoặc nhập local
```

### Cấu hình nhanh LM Studio

Mở LM Studio, bật **Local Server / OpenAI Compatible Server**, sau đó trong app chọn:

```text
AI Provider: lmstudio|LM Studio Local
Model: local-model hoặc đúng tên model trong LM Studio
Base URL: http://localhost:1234/v1
API key: để trống hoặc nhập local
```

### Cấu hình API online

Có thể nhập API key trực tiếp trong app, hoặc khai báo trong file `.env` theo mẫu `.env.example`.

## Bản vá export báo cáo chi tiết theo từng mục rule

Bản này bổ sung báo cáo thẩm định theo đúng yêu cầu rà soát dữ liệu:

- Sheet `Danh gia tung muc`: tổng hợp từng rule/mục, kết luận `DAT`, `CAN_BO_SUNG`, `KHONG_DAT`.
- Sheet `Diem bat thuong`: chỉ liệt kê các điểm bất thường, có đủ file, sheet, dòng, cột, ô dữ liệu và giá trị gốc.
- Sheet `Chi tiet tat ca rule`: toàn bộ kết quả rule engine và AI.
- Báo cáo Word có thêm phần `Đánh giá theo từng mục rule` và `Điểm bất thường và vị trí ô dữ liệu`.
- Markdown cũng có bảng tổng hợp theo từng mục rule.

Các cột quan trọng trong file Excel xuất ra:

- `result/status`: Đạt/Không đạt/Cần bổ sung.
- `source_file`: file phát sinh lỗi.
- `source_sheet`: sheet phát sinh lỗi.
- `source_row`: dòng dữ liệu.
- `source_column`: cột Excel.
- `source_cell`: vị trí ô, ví dụ `C2`, `AP15`.
- `source_value`: giá trị đang bất thường trong ô đó.
- `abnormal_type`: loại bất thường.
- `gap`: nội dung chưa đạt.
- `recommendation`: hướng xử lý.

## Chay desktop - ban gop 1 file

Tu ban nay chi can double click:

```bat
run_desktop.bat
```

File nay tu dong tao `.venv`, cai thu vien neu thieu, sau do mo app desktop. Khong can chay rieng `setup_once.bat` nua.

Neu can xem loi chi tiet, chay:

```bat
run_desktop_debug.bat
```


## Bản vá thẩm định phương án theo file rule

Bản này đã bổ sung rule engine offline cho file phương án `.docx/.txt/.md`:

- Mỗi dòng trong sheet rule thuyết minh/phương án được coi là một mục thẩm định riêng.
- Báo cáo export đánh giá `DAT`, `CAN_BO_SUNG`, `KHONG_DAT` theo từng mục rule.
- Sheet `Diem bat thuong` chỉ ra file, đoạn/bảng gần nhất, nội dung bằng chứng và phần còn thiếu.
- Sheet rule dữ liệu/CSDL vẫn do rule engine CSDL xử lý với vị trí ô Excel khi đầu vào là file `.xlsx/.csv`.

Lưu ý: Nếu muốn kiểm tra CSDL và chỉ ra ô Excel chính xác, cần import thêm file CSDL `.xlsx/.csv` đầu vào; file phương án Word chỉ có thể chỉ ra vị trí đoạn/bảng gần nhất.

## Bản rule-all v4

Bản này thay đổi logic thẩm định rule:

- Tất cả file rule được gán trong danh sách Rule đều được đọc, không bỏ qua sheet CSDL/phương án/thuyết minh.
- Mỗi dòng có nội dung trong Excel rule, hoặc mỗi bullet/dòng yêu cầu trong DOCX/PDF/TXT rule, được chuyển thành một mục thẩm định riêng.
- Tool quét toàn bộ file cần thẩm định gồm DOCX, PDF text, Excel, CSV, TXT, Markdown.
- Báo cáo Excel/Word chỉ rõ từng rule ĐẠT / CẦN BỔ SUNG / KHÔNG ĐẠT, bằng chứng gần nhất và vị trí: đoạn, bảng, dòng Excel/sheet.
- Chế độ Offline + Fast vẫn hoạt động, không cần GPT để chạy rule-all.

Lưu ý: PDF scan ảnh chưa OCR thì cần chuyển OCR trước, vì app chỉ đọc PDF text.


## Chọn model AI theo danh sách

Bản này có mục **AI Provider** và **Model** dạng danh sách chọn. Khi đổi Provider, tool tự gợi ý các model phổ biến/phù hợp. Nếu muốn lấy danh sách thật theo tài khoản hoặc máy local, nhập API key/Base URL rồi bấm **Làm mới model**.

- OpenAI/Groq/OpenRouter/LM Studio dùng endpoint OpenAI-compatible `GET /models`.
- Gemini dùng endpoint Google `models`.
- Ollama dùng endpoint local `GET /api/tags`, chỉ hiện các model đã `ollama pull` trên máy.
- Offline Rule Engine không cần chọn model.

Ví dụ Ollama local:

```bat
ollama pull qwen2.5:7b
```

Sau đó trong app chọn **Ollama Local** và bấm **Làm mới model**.

## Cập nhật bảo mật API Key

- Ô API Key trên app desktop đã được che bằng dấu `*` ngay khi nhập.
- API Key không được đưa vào báo cáo export.
- Lỗi/traceback hiển thị trong app sẽ tự che API Key, kể cả trường hợp provider trả lỗi kèm URL hoặc Bearer token.
