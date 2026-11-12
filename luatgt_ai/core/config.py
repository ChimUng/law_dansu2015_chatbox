from decouple import config

class Settings:
  GEMINI_API_KEY = config("GEMINI_API_KEY", default="")
  GEMINI_MODEL_NAME = config("GEMINI_MODEL_NAME", default="gemini-1.5-flash")
  SUPABASE_URL = config("SUPABASE_URL", default="")
  SUPABASE_ROLE_KEY = config("SUPABASE_ROLE_KEY", default="")
  # Must match the model used to build the checked-in FAISS artifacts.
  EMBEDDING_MODEL_NAME = config("EMBEDDING_MODEL_NAME", default="sentence-transformers/all-MiniLM-L6-v2")
  CORS_ORIGINS = config("CORS_ORIGINS", default="http://localhost:3000,http://127.0.0.1:3000")

settings = Settings()
