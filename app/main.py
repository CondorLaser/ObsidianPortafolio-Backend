from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Depends
from app.core.auth import verify_token
from fastapi.middleware.cors import CORSMiddleware
import os

from app.routes.webhooks import router as webhook_router
from app.routes.assets import router as assets_router

app = FastAPI(
    title="Obsidian Portafolio API"
)

origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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

app.include_router(webhook_router)
app.include_router(assets_router)