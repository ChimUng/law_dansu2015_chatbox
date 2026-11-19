"""Retrieval constrained to the legal corpora owned by this application."""

import json
import re
import unicodedata
from functools import lru_cache
from typing import Any

from services.corpus_registry import PROJECT_ROOT, enabled_auxiliary_corpora, get_corpus
from services.legal_taxonomy import enrich_articles, matching_intents


PRIMARY_CORPUS_ID = "bl_ds_2015"
LEGACY_VECTOR_STORE = PROJECT_ROOT / "vector_store"
LEGACY_LAWS_PATH = PROJECT_ROOT / "data" / "laws.json"
EXACT_ARTICLE_RE = re.compile(r"\bđiều\s+(\d+)\b", re.IGNORECASE)
STOP_WORDS = {
    "la", "gi", "va", "voi", "cua", "cho", "nguoi", "nhung", "nhung",
    "dieu", "nhung", "nao", "can", "duoc", "the", "de", "co", "mot",
    "trong", "theo", "khi", "nhu", "ve", "hay", "tai", "den", "tu",
    "ban", "toi", "em", "anh", "chi", "ho", "gio", "nam", "thang", "ngay",
    "cai", "nay", "kia", "thi", "ma", "neu", "mot", "nhieu",
}
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
    return enrich_articles(records)


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
                "retrieval_method": "exact_article",
                **source,
            }]
    return []


def _semantic_search(question: str, corpus_id: str, top_k: int) -> list[dict]:
    vector_store, articles, source = _load_corpus(corpus_id)
    full_content_by_article = {article["article"]: article["content"] for article in articles}
    docs_with_scores = vector_store.similarity_search_with_score(question, k=top_k)

    results: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for rank, (doc, distance) in enumerate(docs_with_scores, start=1):
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
            "retrieval_method": "semantic_faiss",
            "distance": round(float(distance), 4),
            "semantic_rank": rank,
            **source,
        })
    return results


def _normalize_for_keywords(text: str) -> str:
    # Vietnamese đ/Đ is not decomposed by Unicode NFD, so map it explicitly
    # before stripping tone marks. Without this, “để” becomes “e” and misses
    # aliases written as “de”.
    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", text.casefold())
    without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()


def _keyword_search(question: str, corpus_id: str, top_k: int) -> list[dict]:
    """Retrieve legal terms and article titles before relying on embeddings.

    A compact law corpus benefits greatly from exact phrases: "di chúc hợp
    pháp" should select its named article rather than a semantically vague hit.
    """
    _, articles, source = _load_corpus(corpus_id)
    normalized_question = _normalize_for_keywords(question)
    query_terms = [
        term for term in normalized_question.split()
        if len(term) >= 3 and term not in STOP_WORDS
    ]
    if not query_terms:
        return []

    intent_rules = matching_intents(normalized_question)
    intent_boosts: dict[int, float] = {}
    for rule in intent_rules:
        for article_no, boost in rule.article_boosts.items():
            intent_boosts[article_no] = intent_boosts.get(article_no, 0) + boost

    scored: list[tuple[float, float, dict]] = []
    query_phrase = " ".join(query_terms)
    for article in articles:
        title = _normalize_for_keywords(article["article"])
        content = _normalize_for_keywords(article["content"])
        aliases = " ".join(_normalize_for_keywords(item) for item in article.get("keywords", []))
        title_hits = sum(term in title.split() for term in query_terms)
        content_hits = sum(term in content.split() for term in query_terms)
        alias_hits = sum(term in aliases for term in query_terms)
        intent_boost = intent_boosts.get(article.get("article_no"), 0)
        if not title_hits and not content_hits and not alias_hits and not intent_boost:
            continue
        # Titles and curated aliases name a legal concept more reliably than
        # an incidental word in a long article body.
        score = title_hits * 8 + alias_hits * 5 + content_hits
        if len(query_terms) >= 2 and query_phrase in title:
            score += 20
        scored.append((score + intent_boost, intent_boost, article))

    scored.sort(key=lambda item: (item[0], -item[2].get("article_no", 0)), reverse=True)
    return [{
        "article": article["article"],
        "content": article["content"],
        "similarity": None,
        "retrieval_method": "keyword_phrase",
        "keyword_score": round(score - intent_boost, 2),
        "intent_boost": round(intent_boost, 2),
        "matched_intents": [rule.name for rule in intent_rules],
        **source,
    } for score, intent_boost, article in scored[:top_k]]


def _hybrid_rerank(keyword_results: list[dict], semantic_results: list[dict], top_k: int) -> list[dict]:
    """Merge lexical and semantic candidates into one explainable rank.

    This is deterministic ranking, not a hidden model. It lets a precise legal
    concept match outrank a generic semantic neighbour while preserving semantic
    discovery for wording that has no curated alias.
    """
    candidates: dict[str, dict] = {}
    for hit in keyword_results:
        candidate = dict(hit)
        candidate["semantic_rank"] = None
        candidate["semantic_score"] = 0.0
        candidates[hit["article"]] = candidate

    for hit in semantic_results:
        candidate = candidates.get(hit["article"])
        if candidate is None:
            candidate = dict(hit)
            candidate["keyword_score"] = 0.0
            candidate["intent_boost"] = 0.0
            candidate["matched_intents"] = []
            candidates[hit["article"]] = candidate
        candidate["distance"] = hit.get("distance")
        candidate["semantic_rank"] = hit.get("semantic_rank")
        # Rank-based fusion avoids showing a FAISS distance as legal confidence.
        candidate["semantic_score"] = max(2.0, 18.0 - 2.0 * (hit["semantic_rank"] - 1))

    ranked: list[dict] = []
    for candidate in candidates.values():
        candidate["hybrid_score"] = round(
            candidate.get("keyword_score", 0.0)
            + candidate.get("intent_boost", 0.0)
            + candidate.get("semantic_score", 0.0),
            2,
        )
        candidate["retrieval_method"] = "hybrid_rerank"
        ranked.append(candidate)
    ranked.sort(key=lambda item: (item["hybrid_score"], -item.get("article_no", 0)), reverse=True)
    return ranked[:top_k]


def _trace_item(hit: dict) -> dict:
    return {
        "article": hit["article"],
        "source_name": hit.get("source_name"),
        "method": hit.get("retrieval_method"),
        "keyword_score": hit.get("keyword_score"),
        "distance": hit.get("distance"),
        "intent_boost": hit.get("intent_boost"),
        "hybrid_score": hit.get("hybrid_score"),
        "matched_intents": hit.get("matched_intents", []),
    }


def _search_corpus(question: str, corpus_id: str, top_k: int) -> tuple[list[dict], dict]:
    exact_match = EXACT_ARTICLE_RE.search(question)
    exact_results: list[dict] = []
    if exact_match:
        exact_results = _exact_article(int(exact_match.group(1)), corpus_id)
        if exact_results:
            return exact_results, {
                "exact_article": [_trace_item(hit) for hit in exact_results],
                "keyword_phrase": [],
                "semantic_faiss": [],
                "hybrid_rerank": [],
                "final": [_trace_item(hit) for hit in exact_results],
            }
    candidate_k = max(top_k * 3, 8)
    keyword_results = _keyword_search(question, corpus_id, candidate_k)
    semantic_results = _semantic_search(question, corpus_id, candidate_k)
    matching_rules = matching_intents(_normalize_for_keywords(question))
    intent_limits = [rule.max_results for rule in matching_rules if rule.max_results]
    final_limit = min(intent_limits, default=top_k)
    final_results = _hybrid_rerank(keyword_results, semantic_results, final_limit)
    return final_results, {
        "exact_article": [],
        "keyword_phrase": [_trace_item(hit) for hit in keyword_results],
        "semantic_faiss": [_trace_item(hit) for hit in semantic_results],
        "hybrid_rerank": [_trace_item(hit) for hit in final_results],
        "final": [_trace_item(hit) for hit in final_results],
    }


def find_relevant_laws(
    question: str,
    include_auxiliary_traffic: bool = False,
    top_k: int = 3,
) -> list[dict]:
    """Search the primary corpus plus an enabled auxiliary corpus if appropriate.

    The caller classifies the message; the client never supplies corpus IDs.
    """
    results, _ = _search_corpus(question, PRIMARY_CORPUS_ID, top_k)
    if include_auxiliary_traffic:
        for corpus in enabled_auxiliary_corpora():
            try:
                auxiliary_results, _ = _search_corpus(question, corpus.id, top_k=2)
                results.extend(auxiliary_results)
            except FileNotFoundError:
                # An optional corpus has not been built yet. Civil chat must still work.
                continue
    return results


def retrieve_with_trace(
    question: str,
    include_auxiliary_traffic: bool = False,
    top_k: int = 3,
) -> tuple[list[dict], dict]:
    """Retrieve sources plus a concise, presentation-safe diagnostic trace."""
    results, trace = _search_corpus(question, PRIMARY_CORPUS_ID, top_k)
    if include_auxiliary_traffic:
        for corpus in enabled_auxiliary_corpora():
            try:
                auxiliary_results, auxiliary_trace = _search_corpus(question, corpus.id, top_k=2)
                results.extend(auxiliary_results)
                for stage, candidates in auxiliary_trace.items():
                    trace.setdefault(stage, []).extend(candidates)
            except FileNotFoundError:
                continue
    trace["final"] = [_trace_item(hit) for hit in results[:top_k]]
    return results[:top_k], trace
