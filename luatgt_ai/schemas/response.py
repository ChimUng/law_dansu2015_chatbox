from pydantic import BaseModel
from typing import List

class Law(BaseModel):
  article: str
  content: str
  similarity_score: float

class Response(BaseModel):
  question: str
  answer: str
  relevant_laws: List[Law]