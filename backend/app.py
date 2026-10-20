"""올가 푸드 상품 API 서버

실행 (backend 폴더에서):
    .venv\\Scripts\\python -m uvicorn app:app --host 127.0.0.1 --port 8000
확인:
    http://127.0.0.1:8000/docs      ← 자동으로 만들어지는 창구 목록 (직접 눌러 시험 가능)
"""
import logging

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import (ALLOWED_ORIGINS, CHAT_LIMIT_PER_DAY, CHAT_LIMIT_PER_USER,
                    CHAT_LIMIT_WINDOW_SEC, SITE_DIR)
from schemas import (ChatRequest, ChatResponse, ProductDetailResponse, ProductSummary,
                     SectionResponse, SectionSummary)
from services import chat_service
from services.rate_limit import ChatRateLimiter, RateLimitExceeded
from services import product_service as svc

log = logging.getLogger("olga")

app = FastAPI(title="ORGA Whole Foods API", version="0.1.0",
              description="올가 푸드 상품 · 섹션 · 상세 · 검색 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,          # "*" 대신 필요한 주소만 허용
    allow_methods=["GET", "POST"],          # 조회 + 챗봇 질문
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


@app.get("/api/chat/status", tags=["챗봇"], summary="챗봇을 쓸 수 있는지 (화면에서 버튼 표시 여부 판단)")
def chat_status():
    return {"enabled": chat_service.chat_enabled()}


@app.post("/api/chat", response_model=ChatResponse, tags=["챗봇"],
          summary="쇼핑몰 상담 챗봇 (이용 안내 · 상품 목록 기반, 사용 횟수 제한)")
def chat(req: ChatRequest, request: Request):
    if not chat_service.chat_enabled():
        return JSONResponse(status_code=503, content={"detail": "지금은 상담봇을 이용할 수 없어요."})
    user_key = request.client.host if request.client else "unknown"
    limiter.check(user_key)                 # 넘으면 429 (OpenAI 를 부르기 전에 막음)
    answer = chat_service.ask(req.question.strip(), [t.model_dump() for t in req.history])
    return {"answer": answer}


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


for _folder in ("css", "js", "json", "img"):
    app.mount(f"/{_folder}", StaticFiles(directory=SITE_DIR / _folder), name=_folder)
