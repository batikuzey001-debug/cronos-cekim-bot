import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres123@localhost:5432/cronos_cekim_bot",
)

CRONOS_USERNAME = os.getenv("CRONOS_USERNAME", "")
CRONOS_PASSWORD = os.getenv("CRONOS_PASSWORD", "")
