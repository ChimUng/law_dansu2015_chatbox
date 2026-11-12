"""Retrieval constrained to the legal corpora owned by this application."""

import json
import re
from functools import lru_cache
from typing import Any

from services.corpus_registry import PROJECT_ROOT, enabled_auxiliary_corpora, get_corpus


PRIMARY_CORPUS_ID = "bl_ds_2015"
LEGACY_VECTOR_STORE = PROJECT_ROOT / "vector_store"
LEGACY_LAWS_PATH = PROJECT_ROOT / "data" / "laws.json"
EXACT_ARTICLE_RE = re.compile(r"\bđiều\s+(\d+)\b", re.IGNORECASE)

@lru_cache(maxsize=1)
def get_embedding() -> Any:
    """Load the transformer only when the first chat query needs retrieval.

    This keeps API startup and `/api/health` responsive on a fresh machine.
    """
    from utils.embeddings import TransformersEmbeddings
    return TransformersEmbeddings()


def _legacy_articles() -> list[dict]:
    with LEGACY_LAWS_PATH.open(encoding="utf-8") as file:
        laws = json.load(file)
    records = []
    for law in laws:
        number_match = re.search(r"Điều\s+(\d+)\.", law["article"], re.IGNORECASE)
        records.append({
            "article_no": int(number_match.group(1)) if number_match else None,
            "article": law["article"],
            "content": law["content"],
        })
    return records


@lru_cache(maxsize=4)
def _load_corpus(corpus_id: str) -> tuple[Any, list[dict], dict]:
    corpus = get_corpus(corpus_id)
    vector_path = corpus.vector_store_path
    articles_path = corpus.articles_path

    # Existing deployments continue working until the new ingestion commands run.
    if corpus_id == PRIMARY_CORPUS_ID and not vector_path.exists():
        vector_path = LEGACY_VECTOR_STORE
        articles = _legacy_articles()
    else:
        if not vector_path.exists() or not articles_path.exists():
            raise FileNotFoundError(f"Corpus '{corpus_id}' has not been built.")
        articles = json.loads(articles_path.read_text(encoding="utf-8"))

    from langchain_community.vectorstores import FAISS
    vector_store = FAISS.load_local(
        str(vector_path), get_embedding(), allow_dangerous_deserialization=True
    )
    return vector_store, articles, {
        "corpus_id": corpus.id,
        "source_name": corpus.name,
        "document_id": corpus.document_id,
    }


def _exact_article(article_number: int, corpus_id: str) -> list[dict]:
    _, articles, source = _load_corpus(corpus_id)
    for article in articles:
        if article.get("article_no") == article_number:
            return [{
                "article": article["article"],
                "content": article["content"],
                "similarity": None,
                **source,
            }]
    return []


def _semantic_search(question: str, corpus_id: str, top_k: int) -> list[dict]:
    vector_store, articles, source = _load_corpus(corpus_id)
    full_content_by_article = {article["article"]: article["content"] for article in articles}
    docs_with_scores = vector_store.similarity_search_with_score(question, k=top_k)

    results: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for doc, _distance in docs_with_scores:
        article = doc.metadata.get("article", "Không xác định điều luật")
        key = (corpus_id, article)
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "article": article,
            "content": full_content_by_article.get(article, doc.page_content),
            # A FAISS distance is not an accuracy percentage and is not shown to users.
            "similarity": None,
            **source,
        })
    return results


def _search_corpus(question: str, corpus_id: str, top_k: int) -> list[dict]:
    exact_match = EXACT_ARTICLE_RE.search(question)
    if exact_match:
        exact = _exact_article(int(exact_match.group(1)), corpus_id)
        if exact:
            return exact
    return _semantic_search(question, corpus_id, top_k)


def find_relevant_laws(
    question: str,
    include_auxiliary_traffic: bool = False,
    top_k: int = 3,
) -> list[dict]:
    """Search the primary corpus plus an enabled auxiliary corpus if appropriate.

    The caller classifies the message; the client never supplies corpus IDs.
    """
    results = _search_corpus(question, PRIMARY_CORPUS_ID, top_k)
    if include_auxiliary_traffic:
        for corpus in enabled_auxiliary_corpora():
            try:
                results.extend(_search_corpus(question, corpus.id, top_k=2))
            except FileNotFoundError:
                # An optional corpus has not been built yet. Civil chat must still work.
                continue
    return results
