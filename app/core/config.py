import os
from dotenv import load_dotenv
from urllib.parse import quote_plus  # <--- IMPORT THIS

load_dotenv()

class Settings:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "OneBullEx")
    VERSION: str = os.getenv("VERSION", "1.0.0")
    
    # 1. Get Raw Values
    RAW_USER: str = os.getenv("DB_USER")
    RAW_PASS: str = os.getenv("DB_PASS")
    DB_HOST: str = os.getenv("DB_HOST")
    DB_PORT: str = os.getenv("DB_PORT")
    DB_NAME: str = os.getenv("DB_NAME")

    # 2. Encode them to handle special chars like '@' or '$'
    # If variables are None (local dev), default to empty string to avoid crash
    DB_USER_ENC = quote_plus(RAW_USER) if RAW_USER else ""
    DB_PASS_ENC = quote_plus(RAW_PASS) if RAW_PASS else ""

    # 3. Construct URL with ENCODED credentials
    DATABASE_URL: str = f"postgresql+asyncpg://{DB_USER_ENC}:{DB_PASS_ENC}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    # Debug print (Optional: Check logs to see %40 instead of @)
    #print(f"DEBUG: Final URL: {DATABASE_URL}")

    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")

settings = Settings()