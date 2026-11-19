from pydantic import BaseModel
from typing import List

class Law(BaseModel):
  article: str
  content: str
  similarity_score: float | None = None
  corpus_id: str | None = None
  source_name: str | None = None
  document_id: str | None = None

class Response(BaseModel):
  question: str
  answer: str
  relevant_laws: List[Law]
  scope: str = "civil"
  retrieval_trace: dict | None = None
