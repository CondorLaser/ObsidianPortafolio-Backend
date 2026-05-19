from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
import requests
import os

CLERK_ISSUER = os.getenv("CLERK_ISSUER")
JWKS_URL = f"{CLERK_ISSUER}/.well-known/jwks.json"

security = HTTPBearer()


def get_jwks():
    """Obtiene las keys de Clerk (JWKS)"""
    return requests.get(JWKS_URL).json()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    try:
        jwks = get_jwks()

        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        print("🔑 TOKEN KID:", kid)

        key = next(
            (k for k in jwks["keys"] if k["kid"] == kid),
            None
        )

        if not key:
            print("❌ KEY NOT FOUND FOR KID")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token (kid not found)"
            )

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=CLERK_ISSUER,
        )

        print("👤 TOKEN SUB:", payload.get("sub"))

        return payload

    except HTTPException:
        raise

    except Exception as e:
        print("❌ AUTH ERROR:", str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


def get_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No credentials provided"
        )

    return credentials.credentials