"""LifeData REST API: FastAPI layer over the Snowflake stored procedures.

Run:  uvicorn main:app --reload
Docs: http://localhost:8000/docs
"""
import os
import time

import bcrypt
import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field

import db

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_TTL_SECONDS = 60 * 60

app = FastAPI(title="LifeData API", version="1.0.0")
bearer = HTTPBearer()


# --- schemas -----------------------------------------------------------------

class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=72)  # bcrypt limit is 72 bytes


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    user_id: int
    name: str | None
    email: str | None
    username: str | None


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    major: str | None = None
    bio: str | None = None


class ProfileOut(BaseModel):
    profile_id: int
    user_id: int
    name: str | None
    major: str | None
    bio: str | None


# --- helpers -----------------------------------------------------------------

def _user_out(row: dict) -> UserOut:
    # Never include the password hash in responses.
    return UserOut(
        user_id=row["USER_ID"], name=row["NAME"], email=row["EMAIL"], username=row["USERNAME"]
    )


def _profile_out(row: dict) -> ProfileOut:
    return ProfileOut(
        profile_id=row["PROFILE_ID"], user_id=row["USER_ID"],
        name=row["NAME"], major=row["MAJOR"], bio=row["BIO"],
    )


def _raise_for_result(result: str) -> None:
    """Map the procedures' 'SUCCESS:/ERROR:' strings onto HTTP errors."""
    if result.startswith("SUCCESS"):
        return
    msg = result.removeprefix("ERROR:").strip()
    code = status.HTTP_404_NOT_FOUND if "does not exist" in msg else status.HTTP_409_CONFLICT
    raise HTTPException(code, msg)


def _make_token(user_id: int) -> str:
    now = int(time.time())
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + JWT_TTL_SECONDS},
                      JWT_SECRET, algorithm="HS256")


def current_user_id(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> int:
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")


# --- auth & users ------------------------------------------------------------

@app.post("/users", status_code=201, tags=["users"])
def signup(body: SignupRequest):
    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    _raise_for_result(db.create_user(body.name, body.email, body.username, pw_hash))
    return {"message": "User created"}


@app.post("/auth/login", response_model=TokenResponse, tags=["auth"])
def login(body: LoginRequest):
    rows = db.get_user(body.email)
    # Same error for unknown email and wrong password, to avoid leaking which emails exist.
    if not rows or not bcrypt.checkpw(body.password.encode(), rows[0]["PASSWORD"].encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return TokenResponse(access_token=_make_token(rows[0]["USER_ID"]))


@app.get("/users/me", response_model=UserOut, tags=["users"])
def get_me(user_id: int = Depends(current_user_id)):
    rows = db.get_user_by_id(user_id)
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return _user_out(rows[0])


# --- profiles ----------------------------------------------------------------

@app.post("/profiles", status_code=201, tags=["profiles"])
def create_my_profile(body: ProfileCreate, user_id: int = Depends(current_user_id)):
    _raise_for_result(db.create_profile(user_id, body.name, body.major, body.bio))
    return {"message": "Profile created"}


@app.get("/profiles/me", response_model=ProfileOut, tags=["profiles"])
def get_my_profile(user_id: int = Depends(current_user_id)):
    rows = db.get_profile(user_id)
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    return _profile_out(rows[0])


@app.get("/profiles/{user_id}", response_model=ProfileOut, tags=["profiles"])
def get_profile(user_id: int, _: int = Depends(current_user_id)):
    rows = db.get_profile(user_id)
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    return _profile_out(rows[0])
