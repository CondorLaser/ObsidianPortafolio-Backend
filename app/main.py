from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.auth import verify_token
from app.core.config import get_settings
from app.routers import accounts, assets, positions, prices, transactions, users, heartbeat

settings = get_settings()

app = FastAPI(title="Obsidian Portafolio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {
        "message": "Bienvenid@ a la API de Obsidian Portafolio",
        "status": "running",
    }


@app.get("/protected")
def protected(user=Depends(verify_token)):
    return {"message": "Access granted", "user_id": user["sub"]}


API_PREFIX = "/api/v1"
app.include_router(accounts.router, prefix=API_PREFIX)
app.include_router(assets.router, prefix=API_PREFIX)
app.include_router(prices.router, prefix=API_PREFIX)
app.include_router(transactions.router, prefix=API_PREFIX)
app.include_router(positions.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(heartbeat.router, prefix=API_PREFIX)
