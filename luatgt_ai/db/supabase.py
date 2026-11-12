from functools import lru_cache

from typing import Any
from core.config import settings


@lru_cache(maxsize=1)
def get_supabase() -> Any | None:
    """Create Supabase only when a deployment intentionally configures it.

    A local demo can answer questions without authentication or persistence.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_ROLE_KEY:
        return None
    from supabase import create_client
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ROLE_KEY)
