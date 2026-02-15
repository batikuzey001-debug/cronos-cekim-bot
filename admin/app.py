from contextlib import asynccontextmanager

from fastapi import FastAPI

from database.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
def root():
    return {"message": "Bot çalışıyor"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("admin.app:app", host="127.0.0.1", port=8001, reload=True)
