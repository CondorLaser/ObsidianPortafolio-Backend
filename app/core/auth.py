from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
import requests
import os

CLERK_ISSUER = os.getenv("CLERK_ISSUER")
JWKS_URL = f"{CLERK_ISSUER}/.well-known/jwks.json"

security = HTTPBearer()

jwks = requests.get(JWKS_URL).json()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    try:
        header = jwt.get_unverified_header(token)

        key = next(k for k in jwks["keys"] if k["kid"] == header["kid"])

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=CLERK_ISSUER,
        )

        return payload

    except Exception as e:
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