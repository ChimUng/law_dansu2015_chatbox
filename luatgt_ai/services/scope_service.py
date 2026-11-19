"""Keep corpus selection inside the backend, never in the chat UI."""

from dataclasses import dataclass
from enum import Enum


class QueryScope(str, Enum):
    CIVIL = "civil"
    CIVIL_TRAFFIC = "civil_traffic"
    OUT_OF_SCOPE = "out_of_scope"


TRAFFIC_TERMS = (
    "giao thông", "tai nạn", "xe máy", "ô tô", "vượt đèn", "đèn đỏ",
    "giấy phép lái xe", "bằng lái", "làn đường", "nồng độ cồn", "phạt nguội",
)
CIVIL_REMEDY_TERMS = (
    "bồi thường", "thiệt hại", "trách nhiệm dân sự", "bồi hoàn", "khởi kiện",
    "nghĩa vụ", "tài sản", "hợp đồng", "thừa kế", "di chúc", "giao dịch",
)
CLEARLY_NON_LEGAL_TERMS = (
    "thời tiết", "trời mưa", "nấu ăn", "công thức", "bóng đá", "ca sĩ",
    "phim", "game", "lập trình", "python", "javascript",
)
FAMILY_AND_PROCEDURE_TERMS = (
    "ly hôn", "ly hon", "đơn phương ly hôn", "don phuong ly hon",
    "kết hôn", "ket hon", "nuôi con", "nuoi con", "cấp dưỡng", "cap duong",
    "chia tài sản khi ly hôn", "chia tai san khi ly hon",
)


@dataclass(frozen=True)
class ScopeDecision:
    scope: QueryScope
    use_auxiliary_traffic: bool = False


def classify_query(message: str) -> ScopeDecision:
    """Route only a narrow civil/traffic intersection to an auxiliary corpus.

    This is intentionally conservative. A traffic penalty question must never be
    answered from a civil-law chatbot just because an auxiliary index exists.
    """
    normalized = message.casefold()
    if any(term in normalized for term in CLEARLY_NON_LEGAL_TERMS):
        return ScopeDecision(QueryScope.OUT_OF_SCOPE)
    # These questions need the Marriage and Family Law and/or procedural law.
    # Do not make BLDS sources look like legal grounds for the answer.
    if any(term in normalized for term in FAMILY_AND_PROCEDURE_TERMS):
        return ScopeDecision(QueryScope.OUT_OF_SCOPE)
    has_traffic = any(term in normalized for term in TRAFFIC_TERMS)
    has_civil_remedy = any(term in normalized for term in CIVIL_REMEDY_TERMS)

    if has_traffic and has_civil_remedy:
        return ScopeDecision(QueryScope.CIVIL_TRAFFIC, use_auxiliary_traffic=True)
    if has_traffic:
        return ScopeDecision(QueryScope.OUT_OF_SCOPE)
    return ScopeDecision(QueryScope.CIVIL)


def out_of_scope_message() -> str:
    return (
        "Trợ lý hiện tra cứu Bộ luật Dân sự 2015. Câu hỏi này thuộc lĩnh vực "
        "khác nên tôi không có đủ căn cứ để trả lời chính xác."
    )
