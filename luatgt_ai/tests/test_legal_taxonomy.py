from services.legal_taxonomy import enrich_article, matching_intents
from services.rag_service import _hybrid_rerank, _normalize_for_keywords


def test_article_enrichment_adds_search_aliases_without_changing_source_content():
    source = {
        "article_no": 466,
        "title": "Nghĩa vụ trả nợ của bên vay.",
        "content": "Nguồn pháp luật gốc.",
    }
    enriched = enrich_article(source)
    assert enriched["content"] == source["content"]
    assert "quá hạn" in enriched["keywords"]


def test_overdue_loan_intent_requires_borrowing_due_date_and_interest():
    matched = matching_intents(_normalize_for_keywords(
        "Cho bạn mượn tiền không lãi, quá hạn mà không trả thì tính lãi thế nào?"
    ))
    assert [rule.name for rule in matched] == ["loan_overdue_interest"]


def test_vietnamese_d_stroke_is_normalized_for_inheritance_intent():
    matched = matching_intents(_normalize_for_keywords(
        "Bố tôi mất không để lại di chúc thì ai được hưởng thừa kế?"
    ))
    assert [rule.name for rule in matched] == ["inheritance_without_will"]


def test_hybrid_rank_prefers_precise_intent_candidate_over_generic_semantic_hit():
    result = _hybrid_rerank(
        [{
            "article": "Điều 466.", "article_no": 466, "keyword_score": 8,
            "intent_boost": 120, "matched_intents": ["loan_overdue_interest"],
        }],
        [{
            "article": "Điều 167.", "article_no": 167, "semantic_rank": 1,
            "distance": 0.15,
        }],
        top_k=2,
    )
    assert [item["article_no"] for item in result] == [466, 167]
