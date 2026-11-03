"""회원가입 · 로그인 · 로그인 유지 (JWT)

- 비밀번호는 bcrypt 해시로만 저장합니다. 같은 비밀번호도 저장할 때마다 다른 값이 되고(소금),
  일부러 계산이 느려서 유출되더라도 비밀번호를 하나씩 맞혀 보는 공격이 어렵습니다.
- 로그인하면 2시간짜리 출입증(JWT)을 줍니다. 안에는 회원 번호 · 아이디 · 이름 · 역할 · 만료 시각이 들어 있고,
  서버만 아는 열쇠(JWT_SECRET)로 도장을 찍어 위조할 수 없습니다.
- 서버는 로그인 상태를 따로 기억하지 않고, 요청마다 출입증을 확인합니다.
"""
import re
import time
from datetime import datetime, timezone

import bcrypt
import jwt

from config import JWT_EXPIRE_SEC, JWT_SECRET
from db import get_client

ALGORITHM = "HS256"
LOGIN_ID = re.compile(r"^[a-z0-9]{4,20}$")
PASSWORD = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,64}$")


class AuthError(Exception):
    """로그인이 필요하거나 실패했을 때 (401) — 메시지는 사용자에게 그대로 보여줍니다."""


class SignupError(ValueError):
    """가입 정보가 맞지 않을 때 (400) — 메시지는 사용자에게 그대로 보여줍니다."""


class ForbiddenError(Exception):
    """로그인은 했지만 권한이 없을 때 (403)"""


def enabled() -> bool:
    return bool(JWT_SECRET)


def _require_enabled() -> None:
    if not enabled():
        raise AuthError("로그인 기능이 꺼져 있어요. 서버에 JWT_SECRET 을 설정해 주세요.")


# ───────────────────────── 비밀번호 ─────────────────────────
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


_DUMMY_HASH = hash_password("timing-guard-0")   # 없는 아이디도 같은 시간이 걸리게 (아이디 존재 여부 노출 방지)


# ───────────────────────── 출입증 (JWT) ─────────────────────────
def _issue(user: dict) -> dict:
    now = int(time.time())
    exp = now + JWT_EXPIRE_SEC
    claims = {"sub": str(user["id"]), "login_id": user["login_id"], "name": user["name"],
              "role": user["role"], "iat": now, "exp": exp}
    return {"token": jwt.encode(claims, JWT_SECRET, algorithm=ALGORITHM), "expires_at": exp, "user": public(user)}


def public(user: dict) -> dict:
    """화면에 보내도 되는 회원 정보 (비밀번호 해시 제외)"""
    return {"id": user["id"], "login_id": user["login_id"], "name": user["name"], "role": user["role"]}


def _find(login_id: str) -> dict | None:
    rows = get_client().table("users").select("*").eq("login_id", login_id).limit(1).execute().data
    return rows[0] if rows else None


# ───────────────────────── 가입 · 로그인 ─────────────────────────
def id_available(login_id: str) -> bool:
    return bool(LOGIN_ID.match(login_id or "")) and _find(login_id) is None


def signup(login_id: str, password: str, name: str) -> dict:
    _require_enabled()
    login_id, name = (login_id or "").strip().lower(), (name or "").strip()
    if not LOGIN_ID.match(login_id):
        raise SignupError("아이디는 영문 소문자와 숫자로 4~20자로 입력해 주세요.")
    if not PASSWORD.match(password or "") or len(password.encode()) > 72:     # bcrypt 는 72바이트까지만 씀
        raise SignupError("비밀번호는 영문과 숫자를 섞어 8자 이상으로 입력해 주세요.")
    if login_id in password.lower():
        raise SignupError("비밀번호에 아이디를 넣을 수 없어요.")
    if not 1 <= len(name) <= 20:
        raise SignupError("이름은 1~20자로 입력해 주세요.")
    if _find(login_id):
        raise SignupError("이미 사용 중인 아이디예요.")
    try:
        row = get_client().table("users").insert(
            {"login_id": login_id, "password_hash": hash_password(password), "name": name}).execute().data[0]
    except Exception as e:                          # 동시에 같은 아이디로 가입한 경우
        if "duplicate" in str(e).lower() or "23505" in str(e):
            raise SignupError("이미 사용 중인 아이디예요.")
        raise
    return _issue(row)


def login(login_id: str, password: str) -> dict:
    _require_enabled()
    user = _find((login_id or "").strip().lower())
    ok = check_password(password or "", user["password_hash"] if user else _DUMMY_HASH)
    if not user or not ok:
        raise AuthError("아이디 또는 비밀번호가 맞지 않아요.")
    get_client().table("users").update({"last_login_at": datetime.now(timezone.utc).isoformat()}) \
        .eq("id", user["id"]).execute()
    return _issue(user)


# ───────────────────────── 출입증 확인 ─────────────────────────
def current_user(authorization: str | None) -> dict:
    """'Authorization: Bearer 출입증' 을 확인하고, 지금 DB 의 회원 정보를 돌려줍니다.
    (탈퇴했거나 관리자 권한이 빠졌으면 출입증이 남아 있어도 바로 반영)"""
    _require_enabled()
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token:
        raise AuthError("로그인이 필요해요.")
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
    except jwt.ExpiredSignatureError:
        raise AuthError("로그인 시간이 끝났어요. 다시 로그인해 주세요.")
    except jwt.InvalidTokenError:
        raise AuthError("로그인 정보가 올바르지 않아요. 다시 로그인해 주세요.")
    rows = get_client().table("users").select("*").eq("id", int(claims["sub"])).limit(1).execute().data
    if not rows:
        raise AuthError("회원 정보를 찾을 수 없어요. 다시 로그인해 주세요.")
    return public(rows[0])


def require_admin(authorization: str | None) -> dict:
    user = current_user(authorization)
    if user["role"] != "admin":
        raise ForbiddenError("관리자 계정만 들어올 수 있어요.")
    return user
