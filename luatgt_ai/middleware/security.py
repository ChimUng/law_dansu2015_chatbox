from fastapi import HTTPException
from db.supabase import get_supabase

def verify_token(token: str):
  supabase = get_supabase()
  if supabase is None:
    raise HTTPException(status_code=503, detail="Authentication is not configured")
  try:
    response = supabase.auth.get_user(token)
    return response.user
  except Exception as e:
    print("Error:", str(e))  
    raise HTTPException(status_code=401, detail="Invalid token")
