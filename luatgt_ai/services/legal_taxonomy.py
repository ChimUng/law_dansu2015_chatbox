"""Small, auditable legal vocabulary used by ingestion and hybrid retrieval.

The source text remains untouched.  These are search aliases and relationships
for high-signal legal concepts, not a second copy of the law.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


# Aliases make a user's natural phrasing discoverable even when the official
# article title uses different vocabulary.  They should only be added after a
# regression question demonstrates a recurring gap.
ARTICLE_ALIASES: dict[int, tuple[str, ...]] = {
    466: ("vay", "mượn", "cho mượn", "khoản vay", "trả nợ", "quá hạn", "chậm trả", "không lãi"),
    468: ("lãi", "tiền lãi", "lãi suất", "lãi chậm trả", "lãi quá hạn"),
    627: ("di chúc", "hình thức di chúc"),
    630: ("di chúc hợp pháp", "điều kiện di chúc", "hiệu lực di chúc"),
    650: ("thừa kế theo pháp luật", "không có di chúc", "không để lại di chúc"),
    651: ("hàng thừa kế", "người thừa kế", "vợ chồng", "cha mẹ", "con nuôi"),
    660: ("chia di sản", "phân chia di sản", "chia thừa kế"),
}


@dataclass(frozen=True)
class LegalIntent:
    """A conservative rule for a legal scenario with an unambiguous anchor."""

    name: str
    required_phrase_groups: tuple[tuple[str, ...], ...]
    article_boosts: dict[int, float]
    max_results: int | None = None

    def matches(self, normalized_message: str) -> bool:
        return all(
            any(phrase in normalized_message for phrase in group)
            for group in self.required_phrase_groups
        )


INTENT_RULES: tuple[LegalIntent, ...] = (
    LegalIntent(
        name="loan_overdue_interest",
        required_phrase_groups=(
            ("vay", "muon", "cho vay", "cho muon", "khoan vay"),
            ("qua han", "den han", "cham tra", "khong tra"),
            ("lai", "tien lai", "lai suat"),
        ),
        article_boosts={466: 120, 468: 100},
        max_results=2,
    ),
    LegalIntent(
        name="inheritance_without_will",
        required_phrase_groups=(
            ("di chuc",),
            ("khong de lai", "khong co di chuc"),
        ),
        # Preserve the legal explanation order: trigger → eligible heirs → division.
        article_boosts={650: 200, 651: 160, 660: 100},
        max_results=3,
    ),
    LegalIntent(
        name="valid_will",
        required_phrase_groups=(
            ("di chuc",),
            ("hop phap", "hieu luc"),
        ),
        article_boosts={630: 120, 627: 45},
        max_results=2,
    ),
)


def enrich_article(article: dict) -> dict:
    """Return source data plus non-authoritative retrieval metadata."""
    enriched = dict(article)
    aliases = ARTICLE_ALIASES.get(article["article_no"], ())
    enriched["keywords"] = list(dict.fromkeys((*aliases, article.get("title", ""))))
    return enriched


def enrich_articles(articles: Iterable[dict]) -> list[dict]:
    return [enrich_article(article) for article in articles]


def matching_intents(normalized_message: str) -> list[LegalIntent]:
    return [rule for rule in INTENT_RULES if rule.matches(normalized_message)]
