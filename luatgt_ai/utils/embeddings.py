import torch
from transformers import AutoTokenizer, AutoModel
from langchain_core.embeddings import Embeddings
from typing import List
import numpy as np
from core.config import settings

class TransformersEmbeddings(Embeddings):
  def __init__(self, model_name: str = settings.EMBEDDING_MODEL_NAME, batch_size: int = 16):
    self.tokenizer = AutoTokenizer.from_pretrained(model_name)
    self.model = AutoModel.from_pretrained(model_name)
    self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    self.model.to(self.device)
    self.batch_size = batch_size
    
  def _embed(self, texts: List[str]) -> np.ndarray:
    instructed_texts = [f"Represent this sentence for retrieval: {text}" for text in texts]
    all_embeddings = []
    
    for i in range(0, len(instructed_texts), self.batch_size):
      batch_texts = instructed_texts[i:i + self.batch_size]
      inputs = self.tokenizer(
        batch_texts,
        max_length=256, 
        padding=True,
        truncation=True,
        return_tensors="pt"
      ).to(self.device)
        
      with torch.no_grad():
        outputs = self.model(**inputs)
        token_embeddings = outputs.last_hidden_state
        attention_mask = inputs["attention_mask"].unsqueeze(-1).expand(token_embeddings.size()).float()
        embeddings = (token_embeddings * attention_mask).sum(dim=1) / attention_mask.sum(dim=1).clamp(min=1e-9)
        embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
      all_embeddings.append(embeddings.cpu().numpy())
      del inputs, outputs, embeddings
      torch.cuda.empty_cache() if self.device.type == "cuda" else None
    
    return np.vstack(all_embeddings)
    
  def embed_documents(self, texts: List[str]) -> List[List[float]]:
    return self._embed(texts).tolist()
    
  def embed_query(self, text: str) -> List[float]:
    return self._embed([text])[0].tolist()
