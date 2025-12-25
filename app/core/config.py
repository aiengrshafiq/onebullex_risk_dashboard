# import os
# from dotenv import load_dotenv
# from urllib.parse import quote_plus

# load_dotenv()  # reads .env

# class Settings:
#     def __init__(self):
#         self.PROJECT_NAME: str = os.getenv("PROJECT_NAME", "OneBullEx")
#         self.VERSION: str = os.getenv("VERSION", "1.0.0")

#         # 1) Prefer full DATABASE_URL if present (local dev)
#         env_db_url = os.getenv("DATABASE_URL")
#         if env_db_url and env_db_url.strip():
#             self.DATABASE_URL: str = env_db_url.strip()
#         else:
#             # 2) Otherwise build from parts (prod/VPC)
#             db_user = os.getenv("DB_USER")
#             db_pass = os.getenv("DB_PASS")
#             db_host = os.getenv("DB_HOST")
#             db_port = os.getenv("DB_PORT")
#             db_name = os.getenv("DB_NAME")

#             missing = [k for k, v in {
#                 "DB_USER": db_user,
#                 "DB_PASS": db_pass,
#                 "DB_HOST": db_host,
#                 "DB_PORT": db_port,
#                 "DB_NAME": db_name
#             }.items() if not v]

#             if missing:
#                 raise ValueError(
#                     f"Missing DB env vars: {', '.join(missing)}. "
#                     f"Either set DATABASE_URL or set DB_USER/DB_PASS/DB_HOST/DB_PORT/DB_NAME."
#                 )

#             # URL-encode user/pass to handle special chars like @, $
#             db_user_enc = quote_plus(db_user)
#             db_pass_enc = quote_plus(db_pass)

#             self.DATABASE_URL = (
#                 f"postgresql+asyncpg://{db_user_enc}:{db_pass_enc}@{db_host}:{db_port}/{db_name}"
#             )

#         self.SECRET_KEY: str = os.getenv("SECRET_KEY", "change_me")
#         self.ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
#         self.ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# settings = Settings()



#------------------------------------------------------
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
    
    # Async Connection String for asyncpg
    DATABASE_URL: str = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

settings = Settings()