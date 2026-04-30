from fastapi import FastAPI, Depends
from app.core.auth import get_token

app = FastAPI(
    title="Obsidian Portafolio API"
)

@app.get("/")
def read_root():
    return {
        "message": "Bienvenid@ a la API de Obsidian Portafolio",
        "status": "running"
    }

@app.get("/protected")
def protected(token: str = Depends(get_token)):
    return {
        "message": "Access granted",
        "token_preview": token[:20]
    }