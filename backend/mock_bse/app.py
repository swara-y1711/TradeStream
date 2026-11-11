from fastapi import FastAPI

app = FastAPI(title="Mock BSE")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
