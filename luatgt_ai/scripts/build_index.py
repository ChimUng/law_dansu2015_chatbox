"""Build one FAISS index from a previously ingested corpus.

Usage:
    python scripts/build_index.py --corpus bl_ds_2015
"""

import argparse
import json
import sys
from pathlib import Path

from langchain_community.vectorstores import FAISS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from services.corpus_registry import get_corpus  # noqa: E402
from utils.embeddings import TransformersEmbeddings  # noqa: E402


def split_long_text(text: str, max_chars: int = 1200) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    current = ""
    for sentence in text.split(". "):
        candidate = f"{current}. {sentence}".strip(". ")
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def build_chunks(corpus, articles: list[dict]) -> list[dict]:
    chunks: list[dict] = []
    for article in articles:
        clauses = article.get("clauses") or []
        units = clauses or [{"clause_no": None, "content": article["content"]}]
        for unit in units:
            prefix = article["article"]
            if unit["clause_no"] is not None:
                prefix += f" Khoản {unit['clause_no']}."
            for part_number, part in enumerate(split_long_text(unit["content"]), start=1):
                chunks.append({
                    "text": f"{prefix}\n{part}",
                    "metadata": {
                        "corpus_id": corpus.id,
                        "source_name": corpus.name,
                        "document_id": corpus.document_id,
                        "article": article["article"],
                        "article_no": article["article_no"],
                        "clause_no": unit["clause_no"],
                        "page_start": article["page_start"],
                        "page_end": article["page_end"],
                        "chunk_part": part_number,
                    },
                })
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True)
    args = parser.parse_args()

    corpus = get_corpus(args.corpus)
    if not corpus.articles_path.exists():
        raise FileNotFoundError(
            f"Chưa có dữ liệu đã parse cho {corpus.id}. Chạy ingest_corpus.py trước."
        )
    articles = json.loads(corpus.articles_path.read_text(encoding="utf-8"))
    chunks = build_chunks(corpus, articles)
    if not chunks:
        raise RuntimeError("Không có chunk hợp lệ để tạo index.")

    embedding = TransformersEmbeddings()
    texts = [chunk["text"] for chunk in chunks]
    vectors = embedding.embed_documents(texts)
    vector_store = FAISS.from_embeddings(
        text_embeddings=list(zip(texts, vectors)),
        embedding=embedding,
        metadatas=[chunk["metadata"] for chunk in chunks],
    )
    corpus.vector_store_path.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(corpus.vector_store_path))
    (corpus.generated_dir / "chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Đã tạo {len(chunks)} vector chunks cho corpus '{corpus.id}'.")


if __name__ == "__main__":
    main()
