# Web: Admin panel (FastAPI)
web: uvicorn admin.app:app --host 0.0.0.0 --port ${PORT:-8000}

# Worker: Bot sürekli çalışır, finansal işlemleri tarar
worker: python -m bot.runner
