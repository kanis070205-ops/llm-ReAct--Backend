import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
if not ENCRYPTION_KEY:
    raise RuntimeError("ENCRYPTION_KEY must be set in .env")
