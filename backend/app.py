"""올가 푸드 상품 API 서버

실행 (backend 폴더에서):
    .venv\\Scripts\\python -m uvicorn app:app --host 127.0.0.1 --port 8000
확인:
    http://127.0.0.1:8000/docs      ← 자동으로 만들어지는 창구 목록 (직접 눌러 시험 가능)
"""
import logging

from fastapi import FastAPI, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import (ALLOWED_ORIGINS, CHAT_LIMIT_PER_DAY, CHAT_LIMIT_PER_USER,
                    CHAT_LIMIT_WINDOW_SEC, SITE_DIR, TRUST_PROXY,
                    VISION_LIMIT_PER_DAY, VISION_LIMIT_PER_USER)
from schemas import (AdminAnalyzeRequest, AdminProductCreate, AdminProductPatch, LoginRequest, SignupRequest,
                     ChatRequest, ChatResponse, ProductDetailResponse, ProductSummary,
                     SectionResponse, SectionSummary, VisionRequest, VisionResponse)
from services import admin_service, auth_service, chat_service, rag_service, vision_service
from services.rate_limit import ChatRateLimiter, RateLimitExceeded
from services import product_service as svc

log = logging.getLogger("olga")

app = FastAPI(title="ORGA Whole Foods API", version="0.1.0",
              description="올가 푸드 상품 · 섹션 · 상세 · 검색 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,          # "*" 대신 필요한 주소만 허용
    allow_methods=["GET", "POST", "PATCH", "DELETE"],   # 조회 · 챗봇 + 관리자 수정 · 삭제
    allow_headers=["*"],
)


@app.middleware("http")
async def no_stale_cache(request, call_next):
    """사이트 파일(html·css·js·json)은 브라우저가 예전 버전을 그대로 쓰지 않도록 매번 바뀌었는지 확인하게 함"""
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith(".html") or path.startswith(("/css/", "/js/", "/json/")):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.exception_handler(svc.NotFound)
async def not_found_handler(_request, exc: svc.NotFound):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(_request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": str(exc)})


@app.exception_handler(auth_service.AuthError)
async def auth_error_handler(_request, exc: auth_service.AuthError):
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(auth_service.ForbiddenError)
async def forbidden_handler(_request, exc: auth_service.ForbiddenError):
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(auth_service.SignupError)
async def signup_error_handler(_request, exc: auth_service.SignupError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(admin_service.AdminError)
async def admin_error_handler(_request, exc: admin_service.AdminError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(vision_service.BadImage)
async def bad_image_handler(_request, exc: vision_service.BadImage):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def server_error_handler(_request, exc: Exception):
    # 내부 오류 내용(키·주소 등)이 응답에 새지 않도록 로그에만 남기고 일반 문구만 돌려줌
    log.exception("처리 중 오류")
    return JSONResponse(status_code=503, content={"detail": "일시적인 오류입니다. 잠시 후 다시 시도해 주세요."})


@app.get("/health", tags=["상태"], summary="서버가 켜져 있는지 확인")
def health():
    return {"status": "ok"}


@app.get("/api/sections", response_model=list[SectionSummary], response_model_exclude_none=True,
         tags=["섹션"], summary="섹션 목록 (추천 · 할인 · 선물세트 · MD · 신상품 · 베스트)")
def sections():
    return svc.list_sections()


@app.get("/api/sections/{key}", response_model=SectionResponse, response_model_exclude_none=True,
         tags=["섹션"], summary="섹션 1개의 제목과 상품 카드 목록")
def section(key: str):
    return svc.get_section(key)


@app.get("/api/products", response_model=list[ProductSummary], response_model_exclude_none=True,
         tags=["상품"], summary="상품 검색 (이름 · 브랜드)")
def products(q: str = Query("", max_length=50, description="검색어 (비우면 전체)"),
             limit: int = Query(20, ge=1, le=50)):
    return svc.search_products(q, limit)


@app.get("/api/products/{product_id}", response_model=ProductDetailResponse,
         tags=["상품"], summary="상품 상세 (상세 글이 없으면 카드 정보로 기본 상세를 구성)")
def product(product_id: int):
    return svc.get_product(product_id)


# ───────────────────────── 챗봇 ─────────────────────────
limiter = ChatRateLimiter(CHAT_LIMIT_PER_USER, CHAT_LIMIT_WINDOW_SEC, CHAT_LIMIT_PER_DAY)


def _visitor(request: Request) -> str:
    """질문 횟수를 셀 방문자 주소. 호스팅(프록시) 뒤에서는 X-Forwarded-For 의 첫 주소를 씁니다."""
    if TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "unknown"


@app.get("/api/chat/status", tags=["챗봇"], summary="챗봇을 쓸 수 있는지 (화면에서 버튼 표시 여부 판단)")
def chat_status():
    return {"enabled": chat_service.chat_enabled(), "vision": vision_service.enabled()}


@app.post("/api/chat", response_model=ChatResponse, tags=["챗봇"],
          summary="쇼핑몰 상담 챗봇 (이용 안내 · 상품 목록 기반, 사용 횟수 제한)")
def chat(req: ChatRequest, request: Request):
    if not chat_service.chat_enabled():
        return JSONResponse(status_code=503, content={"detail": "지금은 상담봇을 이용할 수 없어요."})
    limiter.check(_visitor(request))                 # 넘으면 429 (OpenAI 를 부르기 전에 막음)
    answer, sources = chat_service.ask(req.question.strip(), [t.model_dump() for t in req.history])
    return {"answer": answer, "sources": sources}


# ───────────────────────── 사진으로 상품 찾기 (YOLO + 벡터 검색) ─────────────────────────
vision_limiter = ChatRateLimiter(VISION_LIMIT_PER_USER, CHAT_LIMIT_WINDOW_SEC, VISION_LIMIT_PER_DAY)


def _josa(word: str, with_final: str, without_final: str) -> str:
    """한글 받침에 맞는 조사 (사과를 / 당근을)"""
    last = word[-1]
    has_final = "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28 > 0
    return word + (with_final if has_final else without_final)


def _vision_products(names: list[str], query: str, k: int = 3) -> list[dict]:
    """이름이 그대로 들어간 상품을 먼저, 모자라면 벡터 검색으로 의미가 비슷한 상품을 채움"""
    ids: list[int] = []
    for name in names:
        ids += [p["id"] for p in svc.search_products(name, k)]
    if len(ids) < k and query:
        if rag_service.available():
            ids += [c["metadata"]["product_id"] for c in rag_service.search(query, "product", k + 2)]
        else:                                          # 벡터 검색을 못 쓰면 검색어 낱말로 이름 검색
            for word in (w for w in query.split() if len(w) >= 2):     # '청'·'국' 같은 한 글자는 엉뚱한 상품이 걸려 제외
                ids += [p["id"] for p in svc.search_products(word, k)]
    return svc.products_by_ids(list(dict.fromkeys(ids))[:k])


@app.post("/api/vision", response_model=VisionResponse, response_model_exclude_none=True, tags=["챗봇"],
          summary="사진 속 식품을 YOLO로 찾고 비슷한 상품 추천 (사용 횟수 제한)")
def vision(req: VisionRequest, request: Request):
    if not vision_service.enabled():
        return JSONResponse(status_code=503, content={"detail": "지금은 사진 검색을 이용할 수 없어요."})
    vision_limiter.check(_visitor(request))
    detections = vision_service.detect(vision_service.decode(req.image))
    names, query = vision_service.search_terms(detections)
    products = _vision_products(names, query) if names else []

    if names:
        message = f"사진에서 {_josa(', '.join(names), '을', '를')} 찾았어요. "
        message += "비슷한 올가 상품을 골라 봤어요." if products else "아쉽게도 비슷한 상품은 찾지 못했어요."
    elif detections:
        seen = ", ".join(dict.fromkeys(d["label_ko"] for d in detections))
        message = f"사진에서 {_josa(seen, '은', '는')} 보이지만 식품은 찾지 못했어요. 과일이나 음식이 크게 보이게 찍어 주세요."
    else:
        message = "사진에서 알아볼 수 있는 물체를 찾지 못했어요. 식품이 크게 보이게 찍어 주세요."
    return {"message": message, "detections": detections, "products": products}


# ───────────────────────── 회원가입 · 로그인 (JWT) ─────────────────────────
login_limiter = ChatRateLimiter(5, 600, 500)          # 비밀번호 맞히기 시도 막기: 10분에 5번
signup_limiter = ChatRateLimiter(5, 600, 200)         # 가입 남용 막기: 10분에 5번


@app.get("/api/auth/check-id", tags=["회원"], summary="아이디 중복 확인")
def auth_check_id(login_id: str = Query(..., min_length=1, max_length=40)):
    return {"available": auth_service.id_available(login_id.strip().lower())}


@app.post("/api/auth/signup", tags=["회원"], summary="회원가입 (가입 후 바로 로그인 출입증 발급)")
def auth_signup(req: SignupRequest, request: Request):
    signup_limiter.check(_visitor(request))
    return auth_service.signup(req.login_id, req.password, req.name)


@app.post("/api/auth/login", tags=["회원"], summary="로그인 → JWT 출입증 (2시간)")
def auth_login(req: LoginRequest, request: Request):
    login_limiter.check(_visitor(request))
    return auth_service.login(req.login_id, req.password)


@app.get("/api/auth/me", tags=["회원"], summary="내 정보 (출입증 확인)")
def auth_me(authorization: str | None = Header(None)):
    return auth_service.current_user(authorization)


# ───────────────────────── 관리자 (role=admin 계정만) ─────────────────────────
analyze_limiter = ChatRateLimiter(20, 600, 300)       # AI 분석(OpenAI Vision) 요금 보호


@app.get("/api/admin/status", tags=["관리자"], summary="관리자 기능 사용 가능 여부")
def admin_status():
    return {"enabled": auth_service.enabled(), "categories": admin_service.CATEGORIES,
            "storages": admin_service.STORAGES, "page_size": admin_service.PAGE_SIZE}


@app.get("/api/admin/products", tags=["관리자"], summary="상품 목록 (상품명 · 분류 검색, 5개씩 페이지)")
def admin_products(q: str = Query("", max_length=50), page: int = Query(1, ge=1, le=1000),
                   authorization: str | None = Header(None)):
    admin = auth_service.require_admin(authorization)
    return admin_service.list_products(q, page)


@app.post("/api/admin/analyze", tags=["관리자"], summary="상품 사진 AI 분석 (YOLO + OpenAI Vision)")
def admin_analyze(req: AdminAnalyzeRequest, request: Request, authorization: str | None = Header(None)):
    admin = auth_service.require_admin(authorization)
    analyze_limiter.check(_visitor(request))
    return admin_service.analyze(req.image, req.file_name)


@app.post("/api/admin/products", tags=["관리자"], summary="상품 등록 (사진 저장 · 기록 · 상담봇 반영)")
def admin_create(req: AdminProductCreate, request: Request, authorization: str | None = Header(None)):
    admin = auth_service.require_admin(authorization)
    data = req.model_dump(exclude={"image", "analysis_id"})
    return admin_service.create_product(data, req.image, req.analysis_id, _visitor(request), admin["login_id"])


@app.patch("/api/admin/products/{product_id}", tags=["관리자"], summary="상품 수정 (보낸 칸만)")
def admin_update(product_id: int, req: AdminProductPatch, request: Request,
                 authorization: str | None = Header(None)):
    admin = auth_service.require_admin(authorization)
    return admin_service.update_product(product_id, req.model_dump(exclude_unset=True), _visitor(request),
                                        admin["login_id"])


@app.delete("/api/admin/products/{product_id}", tags=["관리자"], summary="상품 삭제 (관리자가 등록한 상품만)")
def admin_delete(product_id: int, request: Request, authorization: str | None = Header(None)):
    admin = auth_service.require_admin(authorization)
    return admin_service.delete_product(product_id, _visitor(request), admin["login_id"])


@app.get("/api/admin/logs", tags=["관리자"], summary="최근 관리자 작업 · AI 분석 기록")
def admin_logs(authorization: str | None = Header(None)):
    admin = auth_service.require_admin(authorization)
    return admin_service.logs()


# ───────────────────────── 사이트 화면 함께 보여주기 ─────────────────────────
# 서버 하나만 켜면 사이트와 API가 같은 주소(8000번)에서 동작합니다.
# 폴더 전체를 열지 않고 사이트에 필요한 파일·폴더만 허용합니다 (backend/.env 같은 비밀 파일은 열리지 않음).
@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
def site_index():
    return FileResponse(SITE_DIR / "index.html")


@app.get("/sub.html", include_in_schema=False)
def site_sub():
    return FileResponse(SITE_DIR / "sub.html")


@app.get("/admin.html", include_in_schema=False)
def site_admin():
    return FileResponse(SITE_DIR / "admin.html")


@app.get("/login.html", include_in_schema=False)
def site_login():
    return FileResponse(SITE_DIR / "login.html")


@app.get("/signup.html", include_in_schema=False)
def site_signup():
    return FileResponse(SITE_DIR / "signup.html")


for _folder in ("css", "js", "json", "img"):
    app.mount(f"/{_folder}", StaticFiles(directory=SITE_DIR / _folder), name=_folder)
