import os
from dotenv import load_dotenv

load_dotenv()

# ===== MODEL =====
MODEL_NAME = "openai/gpt-oss-120b:free"

# ===== OPENROUTER =====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # để trong .env
OPENAI_API_BASE = "https://openrouter.ai/api/v1"

# ===== MEMORY PATH =====
USER_PROFILE_PATH = "data/user_profile.json"
EPISODES_PATH = "data/episodes.json"
CHROMA_DB_DIR = "data/chroma_db"