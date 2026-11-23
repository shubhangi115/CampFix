"""Registration, role-specific login, and revocable JWT sessions."""

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from mysql.connector import IntegrityError, errorcode

from .database import db
from .schemas import Login, Registration

router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer = HTTPBearer(auto_error=False)
hasher = PasswordHasher()
dummy_hash = hasher.hash(uuid4().hex)
issuer = "campfix"


def jwt_secret():
    secret = os.getenv("JWT_SECRET", "")
    if len(secret) < 32 or secret == "replace-with-a-random-secret":
        raise RuntimeError("Set JWT_SECRET to a random value of at least 32 characters.")
    return secret


def sign_in(data, role):
    table, id_column = accounts[role]
    with db() as cursor:
        cursor.execute(
            f"SELECT {id_column}, password_hash FROM {table} WHERE email = %s",
            (data.email.lower(),),
        )
        account = cursor.fetchone()

    try:
        hasher.verify(account["password_hash"] if account else dummy_hash, data.password)
    except VerificationError:
        raise HTTPException(401, "Invalid email or password.") from None
    if not account:
        raise HTTPException(401, "Invalid email or password.")

    account_id = account[id_column]
    session_id = uuid4().hex
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"iss": issuer, "sub": str(account_id), "role": role, "jti": session_id,
         "iat": now, "exp": now + timedelta(minutes=int(os.getenv("JWT_MINUTES", "60")))},
        jwt_secret(),
        algorithm="HS256",
    )
    with db() as cursor:
        cursor.execute(
            f"UPDATE {table} SET session_id = %s WHERE {id_column} = %s",
            (session_id, account_id),
        )
    return {"access_token": token, "token_type": "bearer"}


# SQL identifiers only come from this fixed mapping.
accounts = {"student": ("students", "student_id"), "admin": ("admins", "admin_id")}


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    unauthorized = HTTPException(
        401, "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = jwt.decode(
            credentials.credentials, jwt_secret(), algorithms=["HS256"], issuer=issuer,
            options={"require": ["exp", "iat", "sub", "role", "jti"]},
        )
        role = claims["role"]
        table, id_column = accounts[role]
        account_id = int(claims["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError):
        raise unauthorized from None

    fields = "email, created_at"
    if role == "student":
        fields += ", full_name, roll_number, department"
    with db() as cursor:
        cursor.execute(
            f"SELECT {fields} FROM {table} WHERE {id_column} = %s AND session_id = %s",
            (account_id, claims["jti"]),
        )
        account = cursor.fetchone()
    if account is None:
        raise unauthorized
    return {**account, "id": account_id, "role": role, "session_id": claims["jti"]}


def student(user=Depends(current_user)):
    if user["role"] != "student":
        raise HTTPException(403, "Student access required.")
    return user


def admin(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator access required.")
    return user


@router.post("/student/register", status_code=201)
def register(data: Registration):
    password_hash = hasher.hash(data.password)
    try:
        with db() as cursor:
            cursor.execute(
                """INSERT INTO students (full_name, roll_number, department, email, password_hash)
                   VALUES (%s, %s, %s, %s, %s)""",
                (data.full_name, data.roll_number, data.department, data.email.lower(), password_hash),
            )
            return {"student_id": cursor.lastrowid}
    except IntegrityError as exc:
        if exc.errno == errorcode.ER_DUP_ENTRY:
            raise HTTPException(409, "That email address or roll number is already registered.") from None
        raise


@router.post("/student/login")
def student_login(data: Login, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return sign_in(data, "student")


@router.post("/admin/login")
def admin_login(data: Login, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return sign_in(data, "admin")


@router.get("/me")
def profile(response: Response, user=Depends(current_user)):
    response.headers["Cache-Control"] = "no-store"
    return {key: value for key, value in user.items() if key != "session_id"}


@router.post("/logout", status_code=204)
def logout(user=Depends(current_user)):
    table, id_column = accounts[user["role"]]
    with db() as cursor:
        cursor.execute(
            f"UPDATE {table} SET session_id = NULL WHERE {id_column} = %s AND session_id = %s",
            (user["id"], user["session_id"]),
        )
