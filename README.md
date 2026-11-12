# Luật Minh Bạch — Trợ lý tra cứu BLDS 2015

Chatbot RAG tra cứu **Bộ luật Dân sự 2015**. Mỗi câu trả lời được sinh từ các
Điều/Khoản đã truy xuất và hiển thị nguồn để người dùng tự kiểm tra. Giao diện
chỉ có một ô chat; người dùng không chọn corpus.

## Luồng hoạt động

```text
PDF luật → ingest (Điều/Khoản + metadata) → chunks → FAISS index
                                                ↓
User nhập câu hỏi → scope gate → retrieval → Gemini diễn giải + citations
```

- `bl_ds_2015` là corpus chính (689 Điều).
- `giao_thong_2008` được giữ làm dữ liệu kiểm thử ingest/index, nhưng bị tắt
  khi phục vụ người dùng vì văn bản này đã hết hiệu lực từ 01/01/2025.
- Câu hỏi giao thông thuần hoặc câu hỏi ngoài phạm vi sẽ bị từ chối lịch sự.

## Chạy lần đầu trên Windows

### 1. Điều kiện cần

- Python 3.11 trở lên
- Node.js 18 trở lên
- Một Gemini API key nếu muốn có phần diễn giải AI. Không có key, hệ thống vẫn
  trả các nguồn điều luật liên quan.

### 2. Backend

Mở PowerShell tại thư mục dự án:

```powershell
cd D:\law_dansu2015_chatbox\luatgt_ai
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Mở `.env`, điền ít nhất:

```env
GEMINI_API_KEY=your_key_here
```

`SUPABASE_URL` và `SUPABASE_ROLE_KEY` là tùy chọn. Nếu chưa cấu hình, chat vẫn
chạy ở chế độ khách, chỉ không lưu lịch sử vào Supabase.

Nếu máy chưa có các artifact đã tạo sẵn hoặc bạn vừa thay PDF, build lại index:

```powershell
python scripts/ingest_corpus.py --corpus bl_ds_2015
python scripts/build_index.py --corpus bl_ds_2015
python scripts/ingest_corpus.py --corpus giao_thong_2008
python scripts/build_index.py --corpus giao_thong_2008
```

Khởi động API:

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Kiểm tra API tại `http://127.0.0.1:8000/api/health`. Lần truy vấn đầu có thể
chậm do model embedding được nạp vào RAM.

### 3. Frontend

Mở **một cửa sổ PowerShell khác**:

```powershell
cd D:\law_dansu2015_chatbox\law_dansu2015_frontend
npm ci
npm start
```

Mở `http://localhost:3000`. Frontend mặc định gọi API tại
`http://127.0.0.1:8000`. Nếu backend đặt ở nơi khác, tạo file `.env.local`:

```env
REACT_APP_API_URL=http://your-api-host:8000
```

## OCR PDF ảnh

`road_traffic_law_2024.pdf` là file ảnh, dùng để demo pipeline OCR và không
được bật làm nguồn trả lời pháp lý. Cài Tesseract có dữ liệu tiếng Việt trước:

```powershell
winget install --id UB-Mannheim.TesseractOCR --exact
```

Sau đó đảm bảo `vie.traineddata` có trong thư mục `tessdata`, rồi chạy:

```powershell
cd D:\law_dansu2015_chatbox\luatgt_ai
python scripts/ingest_corpus.py --corpus giao_thong_2024_ocr_demo --ocr auto
python scripts/build_index.py --corpus giao_thong_2024_ocr_demo
```

Tài liệu chi tiết về corpus nằm tại
[`luatgt_ai/docs/corpus-pipeline.md`](luatgt_ai/docs/corpus-pipeline.md).
