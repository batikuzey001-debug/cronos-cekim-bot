import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres123@localhost:5432/cronos_cekim_bot",
)

# Cronos giris bilgileri
CRONOS_USERNAME = os.getenv("CRONOS_USERNAME", "")
CRONOS_PASSWORD = os.getenv("CRONOS_PASSWORD", "")

# 2FA - Google Authenticator TOTP secret key
# Authenticator uygulamasinda QR kod tararken gelen secret key
CRONOS_2FA_SECRET = os.getenv("CRONOS_2FA_SECRET", "")

# Bot ayarlari
BOT_SCAN_INTERVAL = int(os.getenv("BOT_SCAN_INTERVAL", "10"))
CRONOS_BASE_URL = os.getenv("CRONOS_BASE_URL", "https://cronos.redlanegaming.com")
