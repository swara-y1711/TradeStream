import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

MOCK_BSE_URL = os.getenv("MOCK_BSE_URL", "http://localhost:8001")

app = FastAPI(title="Arham Fintech Main Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
