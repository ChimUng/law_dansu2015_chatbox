# Legal corpus pipeline

The chat UI sends only `{ "message": "..." }`. It does not select a corpus.
The backend keeps `bl_ds_2015` as the active corpus. The 2008 traffic corpus is
kept only as an ingestion/index test fixture and is disabled for user answers.

## Build an index from the terminal

Run these commands from `luatgt_ai` after setting `.env` from `.env.example`:

```powershell
python scripts/ingest_corpus.py --corpus bl_ds_2015
python scripts/build_index.py --corpus bl_ds_2015

python scripts/ingest_corpus.py --corpus giao_thong_2008
python scripts/build_index.py --corpus giao_thong_2008
```

The generated corpus is isolated under `data/corpora/<corpus-id>/`; rebuilding
traffic data cannot overwrite the civil-law data.

## OCR demonstration

`road_traffic_law_2024.pdf` is an image-only PDF. It is intentionally disabled
as a legal source and is used only to demonstrate OCR ingestion:

```powershell
python scripts/ingest_corpus.py --corpus giao_thong_2024_ocr_demo --ocr auto
python scripts/build_index.py --corpus giao_thong_2024_ocr_demo
```

Install Tesseract with Vietnamese language data (`vie`) before running the OCR
command. The Docker image includes `tesseract-ocr-vie`; Windows needs a local
Tesseract installation in addition to the Python packages.

Every import records the PDF SHA-256, number of pages, extraction method and
article count in `manifest.json`. The import stops if the expected number of
articles is wrong.
