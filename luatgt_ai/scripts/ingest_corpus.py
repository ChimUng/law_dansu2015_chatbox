"""Create a structured, auditable corpus from a registered PDF.

Usage:
    python scripts/ingest_corpus.py --corpus bl_ds_2015
    python scripts/ingest_corpus.py --corpus giao_thong_2024_ocr_demo --ocr auto
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import fitz

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from services.corpus_registry import get_corpus  # noqa: E402


ARTICLE_RE = re.compile(r"^Điều\s+(\d+)\.\s*(.*)$", re.IGNORECASE)
CLAUSE_RE = re.compile(r"^(\d+)\.\s+(.+)$")


def normalize_line(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u00ad", "")).strip()


def ocr_page(page: fitz.Page, language: str) -> tuple[str, float]:
    """OCR one page only when its native text layer is missing."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as error:
        raise RuntimeError(
            "OCR requires pytesseract, Pillow and the Tesseract executable with "
            "Vietnamese language data. Install them before importing a scan PDF."
        ) from error

    pixmap = page.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72), alpha=False)
    image = Image.open(BytesIO(pixmap.tobytes("png")))
    data = pytesseract.image_to_data(
        image, lang=language, output_type=pytesseract.Output.DICT
    )
    confidences = [float(value) for value in data["conf"] if float(value) >= 0]
    text = " ".join(word for word in data["text"] if word.strip())
    return text, (sum(confidences) / len(confidences) if confidences else 0.0)


def extract_pages(pdf_path: Path, ocr_mode: str, language: str) -> list[dict]:
    document = fitz.open(pdf_path)
    records: list[dict] = []
    for page_number, page in enumerate(document, start=1):
        native_text = page.get_text("text").strip()
        needs_ocr = ocr_mode == "always" or (ocr_mode == "auto" and len(native_text) < 40)
        if needs_ocr:
            text, confidence = ocr_page(page, language)
            extraction_method = "ocr"
        else:
            text, confidence = native_text, None
            extraction_method = "native_text"
        records.append({
            "page": page_number,
            "text": text,
            "extraction_method": extraction_method,
            "ocr_confidence": confidence,
        })
    return records


def parse_articles(page_records: list[dict]) -> list[dict]:
    articles: list[dict] = []
    current: dict | None = None

    def flush() -> None:
        if current is None:
            return
        content = "\n".join(current.pop("content_lines")).strip()
        if content:
            current["content"] = content
            current["clauses"] = parse_clauses(content)
            articles.append(current.copy())

    for page in page_records:
        for raw_line in page["text"].splitlines():
            line = normalize_line(raw_line)
            if not line:
                continue
            match = ARTICLE_RE.match(line)
            if match:
                flush()
                current = {
                    "article_no": int(match.group(1)),
                    "article": f"Điều {match.group(1)}. {match.group(2)}".strip(),
                    "title": match.group(2).strip(),
                    "page_start": page["page"],
                    "page_end": page["page"],
                    "content_lines": [],
                }
            elif current is not None:
                current["content_lines"].append(line)
                current["page_end"] = page["page"]
    flush()
    return articles


def parse_clauses(content: str) -> list[dict]:
    clauses: list[dict] = []
    current: dict | None = None
    for line in content.splitlines():
        match = CLAUSE_RE.match(line)
        if match:
            if current:
                clauses.append(current)
            current = {"clause_no": int(match.group(1)), "content": match.group(2)}
        elif current:
            current["content"] += " " + line
    if current:
        clauses.append(current)
    return clauses


def validate_articles(articles: list[dict], expected_articles: int | None) -> list[str]:
    errors: list[str] = []
    article_numbers = [article["article_no"] for article in articles]
    if len(article_numbers) != len(set(article_numbers)):
        errors.append("Có số Điều bị trùng.")
    if expected_articles is not None and len(articles) != expected_articles:
        errors.append(f"Cần {expected_articles} Điều nhưng parser tách được {len(articles)}.")
    if article_numbers and article_numbers != list(range(1, max(article_numbers) + 1)):
        errors.append("Dãy số Điều bị thiếu hoặc không liên tục.")
    return errors


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--ocr", choices=("auto", "always", "never"), default=None)
    parser.add_argument("--ocr-language", default="vie+eng")
    args = parser.parse_args()

    corpus = get_corpus(args.corpus)
    ocr_mode = args.ocr or corpus.ocr_mode
    if not corpus.source_path.exists():
        raise FileNotFoundError(f"Không thấy file nguồn: {corpus.source_path}")

    try:
        page_records = extract_pages(corpus.source_path, ocr_mode, args.ocr_language)
    except RuntimeError as error:
        print(f"Import stopped: {error}")
        raise SystemExit(2) from None
    articles = parse_articles(page_records)
    validation_errors = validate_articles(articles, corpus.expected_articles)
    if validation_errors:
        raise RuntimeError("Import bị dừng: " + " ".join(validation_errors))

    corpus.generated_dir.mkdir(parents=True, exist_ok=True)
    (corpus.generated_dir / "articles.json").write_text(
        json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = {
        "corpus_id": corpus.id,
        "name": corpus.name,
        "document_id": corpus.document_id,
        "source_file": corpus.source_file,
        "source_sha256": sha256(corpus.source_path),
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "article_count": len(articles),
        "page_count": len(page_records),
        "native_text_pages": sum(p["extraction_method"] == "native_text" for p in page_records),
        "ocr_pages": sum(p["extraction_method"] == "ocr" for p in page_records),
    }
    (corpus.generated_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # ASCII keeps PowerShell consoles configured with legacy encodings from failing.
    print(json.dumps(manifest, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
