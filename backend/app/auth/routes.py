"""Signup / login / logout / me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select

from app.auth.deps import current_user
from app.auth.security import COOKIE_NAME, create_session_token, hash_password, verify_password
from app.config import get_settings
from app.db import get_session
from app.models import Company, SnowflakeConnection, User
from app.schemas.api import CompanyOut, LoginIn, Me, SignupIn

router = APIRouter(prefix="/auth", tags=["auth"])


def build_me(session: Session, user: User) -> Me:
    company = session.get(Company, user.company_id)
    connected = session.exec(
        select(SnowflakeConnection).where(SnowflakeConnection.company_id == user.company_id)
    ).first() is not None
    return Me(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,  # type: ignore[arg-type]
        company=CompanyOut(id=company.id, name=company.name, domain=company.domain),
        snowflake_connected=connected,
    )


def _set_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        COOKIE_NAME,
        create_session_token(user.id, user.company_id),
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=get_settings().jwt_ttl_hours * 3600,
        path="/",
    )


@router.post("/signup", response_model=Me)
def signup(body: SignupIn, response: Response, session: Session = Depends(get_session)) -> Me:
    email = body.email.lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(409, "An account with this email already exists")
    domain = email.split("@", 1)[1]
    company = session.exec(select(Company).where(Company.domain == domain)).first()
    new_company = company is None
    if company is None:
        company = Company(name=body.company_name.strip(), domain=domain)
        session.add(company)
        session.flush()
    user = User(
        company_id=company.id,
        email=email,
        full_name=body.full_name.strip(),
        password_hash=hash_password(body.password),
        role=body.role,
    )
    session.add(user)
    session.flush()
    if new_company and get_settings().demo_mode:
        from app.seed import provision_demo_content

        provision_demo_content(session, company.id, user.id)
    session.commit()
    session.refresh(user)
    _set_cookie(response, user)
    return build_me(session, user)


@router.post("/login", response_model=Me)
def login(body: LoginIn, response: Response, session: Session = Depends(get_session)) -> Me:
    user = session.exec(select(User).where(User.email == body.email.lower())).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    _set_cookie(response, user)
    return build_me(session, user)


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me", response_model=Me)
def me(user: User = Depends(current_user), session: Session = Depends(get_session)) -> Me:
    return build_me(session, user)
