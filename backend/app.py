"""ORGA Whole Foods 서버 — 사이트 화면 + 상품 · 회원 · 상담봇 · 관리자 API

실행 (backend 폴더에서):
    .venv\\Scripts\\python -m uvicorn app:app --host 127.0.0.1 --port 8000
확인:
    http://127.0.0.1:8000/       사이트
    http://127.0.0.1:8000/docs   API 목록 (직접 눌러 시험 가능)

주소 구성
    /api/sections · /api/products   상품 (Supabase)
    /api/auth/*                     회원가입 · 로그인 (JWT)
    /api/chat · /api/vision         상담봇 (벡터 RAG) · 사진으로 상품 찾기 (YOLO)
    /api/admin/*                    관리자 (role=admin 계정만)
"""
import logging

from fastapi import Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import (ALLOWED_ORIGINS, CHAT_LIMIT_PER_DAY, CHAT_LIMIT_PER_USER, CHAT_LIMIT_WINDOW_SEC, JWT_EXPIRE_SEC,
                    SITE_DIR, TRUST_PROXY, VISION_LIMIT_PER_DAY, VISION_LIMIT_PER_USER)
from schemas import (AdminAnalyzeRequest, AdminProductCreate, AdminProductPatch, ChatRequest, ChatResponse,
                     LoginRequest, ProductDetailResponse, ProductSummary, SectionResponse, SectionSummary,
                     SignupRequest, VisionRequest, VisionResponse)
from services import admin_service, auth_service, chat_service, product_service, vision_service
from services.rate_limit import RateLimiter, RateLimitExceeded

log = logging.getLogger("olga")

app = FastAPI(title="ORGA Whole Foods API", version="1.0.0",
              description="올가 푸드 상품 · 회원 · 상담봇(벡터 RAG) · 사진 검색(YOLO) · 관리자 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,                       # "*" 대신 사이트 주소만 허용
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
    allow_credentials=True,                              # 로그인 쿠키
)


@app.middleware("http")
async def no_stale_cache(request: Request, call_next):
    """사이트 파일(html · css · js · json)은 브라우저가 매번 바뀌었는지 확인하게 함 (예전 버전이 남지 않도록)"""
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith(".html") or path.startswith(("/css/", "/js/", "/json/")):
        response.headers["Cache-Control"] = "no-cache"
    return response


# ───────────────────────── 오류 → 응답 ─────────────────────────
# 서비스에서 정한 오류는 메시지를 그대로 화면에 보여주고, 그 밖의 오류는 일반 문구만 돌려줍니다.
ERROR_STATUS = {
    product_service.NotFound: 404,
    RateLimitExceeded: 429,
    auth_service.AuthError: 401,
    auth_service.ForbiddenError: 403,
    auth_service.SignupError: 400,
    admin_service.AdminError: 400,
    vision_service.BadImage: 400,
}


def _error_handler(status: int):
    async def handler(_request: Request, exc: Exception):
        return JSONResponse(status_code=status, content={"detail": str(exc)})
    return handler


for _error, _status in ERROR_STATUS.items():
    app.add_exception_handler(_error, _error_handler(_status))


@app.exception_handler(Exception)
async def server_error_handler(_request: Request, exc: Exception):
    log.exception("처리 중 오류")                        # 키 · 주소 같은 내부 정보는 로그에만
    return JSONResponse(status_code=503, content={"detail": "일시적인 오류입니다. 잠시 후 다시 시도해 주세요."})


# ───────────────────────── 공통 도구 ─────────────────────────
# 사용 횟수 제한 (한 사람당 · 사이트 전체 하루, Supabase 에 기록) — OpenAI 요금과 무료 서버 CPU 를 지킵니다.
chat_limiter = RateLimiter("chat", CHAT_LIMIT_PER_USER, CHAT_LIMIT_WINDOW_SEC, CHAT_LIMIT_PER_DAY)
vision_limiter = RateLimiter("vision", VISION_LIMIT_PER_USER, CHAT_LIMIT_WINDOW_SEC, VISION_LIMIT_PER_DAY)
login_limiter = RateLimiter("login", 5, 600, 500)             # 비밀번호 맞히기 시도: 10분에 5번
signup_limiter = RateLimiter("signup", 5, 600, 200)            # 가입 남용: 10분에 5번
analyze_limiter = RateLimiter("analyze", 20, 600, 300)          # 관리자 AI 분석: 10분에 20번


def visitor(request: Request) -> str:
    """횟수를 셀 방문자 주소. 호스팅(프록시) 뒤에서는 X-Forwarded-For 의 첫 주소를 씁니다."""
    if TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "unknown"


SESSION_COOKIE = "orga_session"
CSRF_HEADER = "x-requested-with"                         # 사이트 화면만 붙이는 머리말 (다른 사이트는 붙일 수 없음)


def session_token(request: Request) -> str | None:
    """로그인 출입증 — HttpOnly 쿠키, 없으면 Authorization: Bearer (점검 스크립트용)"""
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        return token
    bearer = request.headers.get("authorization", "")
    return bearer.removeprefix("Bearer ").strip() or None


def admin_user(request: Request) -> dict:
    """관리자 API 공통 — 출입증을 확인하고 role=admin 이 아니면 막습니다.
    쿠키로 로그인한 요청이 데이터를 바꿀 때는 사이트 화면이 붙이는 머리말이 있어야 합니다 (다른 사이트의 위조 요청 차단)."""
    if (request.method not in ("GET", "HEAD") and request.cookies.get(SESSION_COOKIE)
            and request.headers.get(CSRF_HEADER) != "orga"):
        raise auth_service.ForbiddenError("허용되지 않은 요청이에요. 페이지를 새로고침해 주세요.")
    return auth_service.require_admin(session_token(request))


def _with_session(request: Request, issued: dict) -> JSONResponse:
    """로그인 · 가입 응답 — 출입증은 HttpOnly 쿠키로만 보내고, 화면에는 회원 정보와 만료 시각만 줍니다."""
    response = JSONResponse({"user": issued["user"], "expires_at": issued["expires_at"]})
    https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(SESSION_COOKIE, issued["token"], max_age=JWT_EXPIRE_SEC, httponly=True,
                        secure=https, samesite="lax", path="/")
    return response


# ───────────────────────── 상태 ─────────────────────────
@app.get("/health", tags=["상태"], summary="서버가 켜져 있는지 확인")
def health():
    return {"status": "ok"}


# ───────────────────────── 상품 ─────────────────────────
@app.get("/api/sections", response_model=list[SectionSummary], response_model_exclude_none=True,
         tags=["상품"], summary="섹션 목록 (추천 · 할인 · 선물세트 · MD · 신상품 · 베스트)")
def sections():
    return product_service.list_sections()


@app.get("/api/sections/{key}", response_model=SectionResponse, response_model_exclude_none=True,
         tags=["상품"], summary="섹션 1개의 제목과 상품 카드 목록")
def section(key: str):
    return product_service.get_section(key)


@app.get("/api/products", response_model=list[ProductSummary], response_model_exclude_none=True,
         tags=["상품"], summary="상품 검색 (이름 · 브랜드)")
def products(q: str = Query("", max_length=50, description="검색어 (비우면 전체)"),
             limit: int = Query(20, ge=1, le=50)):
    return product_service.search_products(q, limit)


@app.get("/api/products/{product_id}", response_model=ProductDetailResponse,
         tags=["상품"], summary="상품 상세 (상세 글이 없으면 카드 정보로 기본 상세를 구성)")
def product(product_id: int):
    return product_service.get_product(product_id)


# ───────────────────────── 회원 (JWT) ─────────────────────────
@app.get("/api/auth/check-id", tags=["회원"], summary="아이디 중복 확인")
def auth_check_id(login_id: str = Query(..., min_length=1, max_length=40)):
    return {"available": auth_service.id_available(login_id.strip().lower())}


@app.post("/api/auth/signup", tags=["회원"], summary="회원가입 (가입 후 바로 로그인 · HttpOnly 쿠키)")
def auth_signup(req: SignupRequest, request: Request, who: str = Depends(visitor)):
    signup_limiter.check(who)
    return _with_session(request, auth_service.signup(req.login_id, req.password, req.name))


@app.post("/api/auth/login", tags=["회원"], summary="로그인 → JWT 출입증 (HttpOnly 쿠키 · 2시간)")
def auth_login(req: LoginRequest, request: Request, who: str = Depends(visitor)):
    login_limiter.check(who)
    return _with_session(request, auth_service.login(req.login_id, req.password))


@app.post("/api/auth/logout", tags=["회원"], summary="로그아웃 (쿠키 삭제)")
def auth_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@app.get("/api/auth/me", tags=["회원"], summary="내 정보 (출입증 확인)")
def auth_me(request: Request):
    return auth_service.current_user(session_token(request))


# ───────────────────────── 상담봇 · 사진으로 상품 찾기 ─────────────────────────
@app.get("/api/chat/status", tags=["상담봇"], summary="상담봇 · 사진 검색을 쓸 수 있는지 (화면의 버튼 표시용)")
def chat_status():
    return {"enabled": chat_service.chat_enabled(), "vision": vision_service.enabled()}


@app.post("/api/chat", response_model=ChatResponse, tags=["상담봇"],
          summary="쇼핑몰 상담 (벡터 검색으로 찾은 안내 · 상품 정보로 답변)")
def chat(req: ChatRequest, who: str = Depends(visitor)):
    if not chat_service.chat_enabled():
        return JSONResponse(status_code=503, content={"detail": "지금은 상담봇을 이용할 수 없어요."})
    chat_limiter.check(who)                              # OpenAI 를 부르기 전에 횟수부터 확인
    answer, sources = chat_service.ask(req.question.strip(), [t.model_dump() for t in req.history])
    return {"answer": answer, "sources": sources}


@app.post("/api/vision", response_model=VisionResponse, response_model_exclude_none=True, tags=["상담봇"],
          summary="사진 속 식품을 YOLO로 찾고 비슷한 상품 추천")
def vision(req: VisionRequest, who: str = Depends(visitor)):
    if not vision_service.enabled():
        return JSONResponse(status_code=503, content={"detail": "지금은 사진 검색을 이용할 수 없어요."})
    vision_limiter.check(who)
    return vision_service.photo_search(req.image)


# ───────────────────────── 관리자 (role=admin) ─────────────────────────
@app.get("/api/admin/status", tags=["관리자"], summary="관리자 화면 설정 (분류 · 보관 목록)")
def admin_status():
    return {"enabled": auth_service.enabled(), "categories": admin_service.CATEGORIES,
            "storages": admin_service.STORAGES, "page_size": admin_service.PAGE_SIZE}


@app.get("/api/admin/products", tags=["관리자"], summary="상품 목록 (상품명 · 분류 검색, 5개씩 페이지)")
def admin_products(q: str = Query("", max_length=50), page: int = Query(1, ge=1, le=1000),
                   _admin: dict = Depends(admin_user)):
    return admin_service.list_products(q, page)


@app.post("/api/admin/analyze", tags=["관리자"], summary="상품 사진 AI 분석 (YOLO + OpenAI Vision)")
def admin_analyze(req: AdminAnalyzeRequest, who: str = Depends(visitor), _admin: dict = Depends(admin_user)):
    analyze_limiter.check(who)
    return admin_service.analyze(req.image, req.file_name)


@app.post("/api/admin/products", tags=["관리자"], summary="상품 등록 (사진 저장 · 기록 · 상담봇 반영)")
def admin_create(req: AdminProductCreate, who: str = Depends(visitor), admin: dict = Depends(admin_user)):
    data = req.model_dump(exclude={"image", "analysis_id"})
    return admin_service.create_product(data, req.image, req.analysis_id, who, admin["login_id"])


@app.patch("/api/admin/products/{product_id}", tags=["관리자"], summary="상품 수정 (보낸 칸만)")
def admin_update(product_id: int, req: AdminProductPatch, who: str = Depends(visitor),
                 admin: dict = Depends(admin_user)):
    return admin_service.update_product(product_id, req.model_dump(exclude_unset=True), who, admin["login_id"])


@app.delete("/api/admin/products/{product_id}", tags=["관리자"], summary="상품 삭제 (관리자가 등록한 상품만)")
def admin_delete(product_id: int, who: str = Depends(visitor), admin: dict = Depends(admin_user)):
    return admin_service.delete_product(product_id, who, admin["login_id"])


@app.get("/api/admin/logs", tags=["관리자"], summary="최근 관리자 작업 · AI 분석 기록")
def admin_logs(_admin: dict = Depends(admin_user)):
    return admin_service.logs()


# ───────────────────────── 사이트 화면 ─────────────────────────
# 서버 하나로 사이트와 API를 같은 주소에서 제공합니다.
# 폴더 전체를 열지 않고 필요한 페이지 · 폴더만 허용합니다 (backend/.env 같은 비밀 파일은 열리지 않음).
PAGES = ("index.html", "sub.html", "login.html", "signup.html", "admin.html")


def _page_route(name: str):
    def page():
        return FileResponse(SITE_DIR / name)
    return page


app.get("/", include_in_schema=False)(_page_route("index.html"))
for _page in PAGES:
    app.get(f"/{_page}", include_in_schema=False)(_page_route(_page))

for _folder in ("css", "js", "json", "img"):
    app.mount(f"/{_folder}", StaticFiles(directory=SITE_DIR / _folder), name=_folder)
