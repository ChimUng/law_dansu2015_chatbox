from services.scope_service import QueryScope, classify_query


def test_civil_question_stays_in_primary_corpus():
    decision = classify_query("Điều kiện để di chúc hợp pháp là gì?")
    assert decision.scope == QueryScope.CIVIL
    assert not decision.use_auxiliary_traffic


def test_traffic_accident_with_compensation_can_use_auxiliary_corpus():
    decision = classify_query("Tai nạn giao thông gây thiệt hại thì bồi thường thế nào?")
    assert decision.scope == QueryScope.CIVIL_TRAFFIC
    assert decision.use_auxiliary_traffic


def test_traffic_penalty_is_outside_civil_assistant_scope():
    decision = classify_query("Vượt đèn đỏ bị phạt bao nhiêu?")
    assert decision.scope == QueryScope.OUT_OF_SCOPE


def test_clearly_non_legal_question_is_rejected_before_retrieval():
    decision = classify_query("Thời tiết hôm nay thế nào?")
    assert decision.scope == QueryScope.OUT_OF_SCOPE


def test_divorce_procedure_is_rejected_before_civil_retrieval():
    decision = classify_query("Muốn đơn phương ly hôn thì cần chuẩn bị giấy tờ gì?")
    assert decision.scope == QueryScope.OUT_OF_SCOPE
