# backend/config.py

import os
from dotenv import load_dotenv

load_dotenv()

def _bool(val) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}

class Config:
    # Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBtnF3AeybydhSU-6G4HPSfTYqPWMNuvrY")
    LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY", "llx-z0flAnJztnZQmWrpCxKh7riYMYadV2XvOLOjEOPMBplYBf6e")

    # Email
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    EMAIL_USER = os.getenv("EMAIL_USER", "teamhrms.2025@gmail.com")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "umqiidutggpxepsb")
    EMAIL_DISABLE_SEND = _bool(os.getenv("EMAIL_DISABLE_SEND", "false"))  # default: False (emails will send)

    # DB
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hr_employees.db")
    DB_PATH = os.getenv("DB_PATH", "hr_employees.db")

    # Embeddings / FAISS
    EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
    FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "./policy_faiss_index")

    # Uploads
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
    MAX_FILE_SIZE = 10 * 1024 * 1024

    # Chunking
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1500"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "400"))

    # Agents
    MAX_AGENT_ITERATIONS = int(os.getenv("MAX_AGENT_ITERATIONS", "5"))
    AGENT_VERBOSE = _bool(os.getenv("AGENT_VERBOSE", "true"))

config = Config()
