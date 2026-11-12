"""Registry and paths for isolated legal corpora."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
REGISTRY_PATH = DATA_DIR / "corpora.json"
GENERATED_CORPORA_DIR = DATA_DIR / "corpora"


@dataclass(frozen=True)
class Corpus:
    id: str
    name: str
    document_id: str
    source_file: str
    expected_articles: int | None
    role: str
    enabled: bool
    ocr_mode: str
    activation_note: str | None = None

    @property
    def source_path(self) -> Path:
        return DATA_DIR / self.source_file

    @property
    def generated_dir(self) -> Path:
        return GENERATED_CORPORA_DIR / self.id

    @property
    def articles_path(self) -> Path:
        return self.generated_dir / "articles.json"

    @property
    def vector_store_path(self) -> Path:
        return self.generated_dir / "vector_store"


def all_corpora() -> list[Corpus]:
    with REGISTRY_PATH.open(encoding="utf-8") as file:
        payload = json.load(file)
    return [Corpus(**item) for item in payload["corpora"]]


def get_corpus(corpus_id: str) -> Corpus:
    for corpus in all_corpora():
        if corpus.id == corpus_id:
            return corpus
    raise ValueError(f"Unknown corpus: {corpus_id}")


def enabled_auxiliary_corpora() -> Iterable[Corpus]:
    return (
        corpus for corpus in all_corpora()
        if corpus.enabled and corpus.role == "auxiliary"
    )
