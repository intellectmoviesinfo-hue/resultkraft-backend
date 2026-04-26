"""
Lazy-initialized Supabase client using the service role key.
Service role bypasses RLS — only use on backend, never expose to frontend.
"""
import os
from functools import lru_cache
from typing import Optional

from supabase import create_client, Client


@lru_cache
def get_supabase() -> Optional[Client]:
    """
    Returns a Supabase service-role client, or None if env vars are missing.
    Endpoints should treat None as "DB unavailable" and degrade gracefully
    (e.g. extraction still works in-memory; we just don't persist).
    """
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None
