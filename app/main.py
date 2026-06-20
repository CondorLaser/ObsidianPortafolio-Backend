from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.auth import verify_token
from app.core.config import get_settings
from app.routers import (
    accounts,
    assets,
    dividends,
    heartbeat,
    onboarding,
    pdf,
    portfolio,
    positions,
    preferences,
    prices,
    profile,
    transactions,
    webhooks,
    warnings,
) 

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


# Sin prefijo /api/v1 — el middleware (Zuplo) está configurado para que las
# rutas estén en root, matcheando exactamente lo que diseñó Eduardo.
app.include_router(profile.router)
app.include_router(preferences.router)
app.include_router(onboarding.router)
app.include_router(accounts.router)
app.include_router(assets.router)
app.include_router(prices.router)
app.include_router(transactions.router)
app.include_router(positions.router)
app.include_router(portfolio.router)
app.include_router(dividends.router)
app.include_router(pdf.router)
app.include_router(heartbeat.router)
app.include_router(webhooks.router)
app.include_router(warnings.router)
