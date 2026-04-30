from fastapi import FastAPI, Depends
from app.core.auth import verify_token
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Obsidian Portafolio API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {
        "message": "Bienvenid@ a la API de Obsidian Portafolio",
        "status": "running"
    }

@app.get("/protected")
def protected(user = Depends(verify_token)):
    return {
        "message": "Access granted",
        "user_id": user["sub"]
    }