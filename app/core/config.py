
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "OneBullEx")
    VERSION: str = os.getenv("VERSION", "1.0.0")
    
    # DB Construction
    DB_USER: str = os.getenv("DB_USER")
    DB_PASS: str = os.getenv("DB_PASS")
    DB_HOST: str = os.getenv("DB_HOST")
    DB_PORT: str = os.getenv("DB_PORT")
    DB_NAME: str = os.getenv("DB_NAME")

    # --- DEBUGGING BLOCK (Add this) ---
    print(f"DEBUG: DB_HOST is '{DB_HOST}'") # Note the quotes to see spaces
    print(f"DEBUG: DB_PORT is '{DB_PORT}'")
    # ----------------------------------
    
    # Async Connection String for asyncpg
    DATABASE_URL: str = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    print(f"DEBUG: DATABASE_URL is '{DATABASE_URL}'")

    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

settings = Settings()