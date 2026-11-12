from db.supabase import get_supabase

def save_question(user_id: str, message: str):
    supabase = get_supabase()
    if supabase is None:
        return None
    data = {"user_id": user_id, "message": message}
    try:
        return supabase.table("questions").insert(data).execute()
    except Exception:
        # Persistence must not prevent a legal lookup from completing.
        return None

def save_answer(user_id: str, message: str, relevant_laws):
    supabase = get_supabase()
    if supabase is None:
        return None
    data = {"user_id": user_id, "message": message, "relevant_laws": relevant_laws}
    try:
        return supabase.table("answers").insert(data).execute()
    except Exception:
        return None
