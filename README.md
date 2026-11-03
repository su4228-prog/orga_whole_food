# 🥬 ORGA Whole Foods — AI 쇼핑몰

**유기농 식품 쇼핑몰에 벡터 RAG 상담봇 · YOLO 사진 상품 찾기 · AI 상품등록 관리자 · JWT 회원 기능을 직접 설계하고 구현한 개인 프로젝트**

🔗 **배포 사이트 →** [https://orga-whole-food.onrender.com](https://orga-whole-food.onrender.com) <sub>(Render 무료 서버 · 잠들어 있으면 첫 접속에 수십 초 걸릴 수 있습니다)</sub>

[![Live Demo](https://img.shields.io/badge/Live_Demo-Render-46E3B7?style=flat-square&logo=render&logoColor=black)](https://orga-whole-food.onrender.com)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-pgvector-3FCF8E?style=flat-square&logo=supabase&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-gpt--4o--mini-412991?style=flat-square&logo=openai&logoColor=white)
![YOLO](https://img.shields.io/badge/YOLO11n-ONNX_Runtime-111F68?style=flat-square)
![JWT](https://img.shields.io/badge/JWT-HttpOnly_Cookie-000000?style=flat-square&logo=jsonwebtokens&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-ES_Modules-F7DF1E?style=flat-square&logo=javascript&logoColor=black)

> 📑 발표 슬라이드 28장은 아래 [슬라이드 펼쳐보기](#-슬라이드-펼쳐보기)에 있습니다. 원본: [`docs/readme/README.html`](./docs/readme/README.html)

| 상품 · 상세 | API | Supabase 표 | RAG 벡터 | 상담봇 점검 | 사진 → 같은 상품 | 공개 코드의 비밀 키 |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **30개** | **20개** | **11개** | **42조각** | **22/22** | **90/90** | **0건** |

---

## 📌 목차

**01 프로젝트 소개** — [개요](#-개요) · [기능 지도](#-기능-지도)
**02 주요 기능** — [쇼핑몰](#1-쇼핑몰--상품-30개-각자의-상세-페이지) · [상담봇 RAG](#2-상담봇--근거를-찾아서-답하는-벡터-rag) · [사진으로 상품 찾기](#3-사진으로-상품-찾기--yolo-두-개--rag) · [관리자](#4-관리자--사진만-올리면-정보가-채워진다) · [회원](#5-회원--jwt--httponly-쿠키--bcrypt)
**03 기술과 문제 해결** — [사용한 도구](#-이-프로그램은-이런-도구로-만들었습니다) · [프로그램 구조](#-프로그램-구조) · [서버 기능](#-서버-기능-목록) · [ERD](#-erd) · [오류 해결](#-실제로-겪은-오류-고치기-전과-후) · [검증](#-검증) · [실행 방법](#-실행-방법)

---

# 01 프로젝트 소개

## 🗂 개요

| 항목 | 내용 |
|---|---|
| **무엇을** | 유기농 식품 쇼핑몰 ORGA를 본뜬 웹사이트 — 상품 30개 · 상세 페이지 30개 |
| **손님에게** | 배송 · 반품 · 적립금을 바로 답하는 상담봇, 사진 한 장으로 같은 상품을 찾는 검색 |
| **관리자에게** | 사진만 올리면 상품명 · 가격 · 분류가 채워지는 등록 화면, 모든 작업 기록 |
| **원칙** | AI는 근거(문서 · DB)로만 답하고, 비밀 키 · 비용 · 권한은 서버가 지킨다 |
| **범위** | 개인 프로젝트 — 기획 · 화면 · 서버 · DB · AI · 배포 전체 |

> 학습과 포트폴리오 목적으로 만든 프로젝트이며, 상호 · 로고 · 상품 이미지와 문구의 권리는 각 권리자에게 있습니다. 상담봇의 이용 안내 문서는 실제 쇼핑몰 FAQ를 참고해 직접 다시 쓴 내용입니다.

## 🧭 기능 지도

| 기능 | 핵심 기술 |
|---|---|
| **쇼핑몰 화면** | 메인 6개 섹션 · 상품별 상세 30개 · 반응형(320~1440px) |
| **상담봇 · 벡터 RAG** | 질문 임베딩 → pgvector 유사도 검색 → 근거 + 서버 계산 사실로 답변 · 출처 표시 |
| **사진으로 상품 찾기** | YOLO 분류 특징으로 같은 상품 · YOLO 탐지로 물체 · 이름으로 벡터 검색 추천 |
| **관리자** | YOLO + OpenAI Vision 자동 입력 · 검색 · 5개씩 페이지 · 수정 · 삭제 · 작업 기록 |
| **회원 · 권한** | 가입 · 로그인(JWT · HttpOnly 쿠키) · bcrypt · role=admin 만 관리자 |

---

# 02 주요 기능

## 1. 쇼핑몰 — 상품 30개, 각자의 상세 페이지

메인 6개 섹션의 카드를 누르면 `sub.html?id=번호`로 그 상품의 상세가 열립니다. 데이터는 **API → 실패 시 예비 JSON** 순서로 읽어, 서버가 잠깐 멈춰도 화면은 유지됩니다.

<p align="center">
  <img src="./docs/readme/shots/main.jpg" alt="메인" width="49%" />
  <img src="./docs/readme/shots/detail.jpg" alt="상세" width="49%" />
</p>

---

## 2. 상담봇 — 근거를 찾아서 답하는 벡터 RAG

질문과 뜻이 가까운 **이용 안내 4조각 · 상품 3개**만 벡터 검색으로 골라 답하고, 근거로 쓴 자료를 "참고: 적립금"처럼 함께 보여줍니다.

<p align="center"><img src="./docs/readme/shots/rag.jpg" alt="상담봇" width="55%" /></p>

| 단계 | 구현 |
|---|---|
| ① 조각 저장 | 이용 안내를 제목 단위 12조각, 상품 30개를 1조각씩 → `text-embedding-3-small`(1536차원) → `rag_chunks` |
| ② 검색 | 질문(+이어지는 질문은 앞 질문까지)을 임베딩 → `match_rag_chunks`가 코사인 유사도 순으로 반환 · HNSW 색인 |
| ③ 답변 | 찾은 조각 + **서버가 계산한 사실**(가격 · 베스트 순위 · 무료배송 · 상온/냉장 반품 기준) → `gpt-4o-mini` |
| 안전장치 | 문서 밖 질문은 "확인되지 않는 내용" · 한 사람당 10분 10회 · 검색 실패 시 문서 전체 방식으로 자동 전환 |

```python
# backend/services/chat_service.py
def _retrieve(question, recent_user):
    query = f"{recent_user} {question}".strip()[-500:]   # 이어지는 질문은 앞 질문까지 함께 검색
    vec = rag_service.embed([query])[0]
    policy = rag_service.search(query, "policy", POLICY_K, vec)      # 안내 4조각
    products = rag_service.search(query, "product", PRODUCT_K, vec)  # 상품 3개
```

```sql
-- backend/sql/002_vector_rag.sql
create function match_rag_chunks(query_embedding vector(1536), match_count int, filter_source text)
returns table (id bigint, title text, content text, similarity float) as $$
  select id, title, content, 1 - (embedding <=> query_embedding) as similarity
  from rag_chunks where filter_source is null or source = filter_source
  order by embedding <=> query_embedding limit match_count;
$$;
```

질문 22개(배송 · 반품 · 적립금 · 쿠폰 · 결제 · 가격 · 순위 · 이어지는 질문 · 문서 밖 · 규칙 무시)를 **모두 통과**했습니다.

---

## 3. 사진으로 상품 찾기 — YOLO 두 개 + RAG

상담봇의 📷 버튼으로 사진을 올리면 세 가지가 함께 동작합니다.

| 단계 | 모델 | 하는 일 |
|---|---|---|
| ① 같은 상품 찾기 | **YOLO11n 분류** (특징 1280개) | 상품 30개 사진의 특징과 코사인 비교 → 일치도 0.75 이상이면 같은 상품 |
| ② 물체 찾기 | **YOLO11n 탐지** (320px) | 사진 속 식품(사과 · 병 · 그릇 …)의 위치와 이름 · 사진 위에 네모 표시 |
| ③ 추천 | **벡터 검색(RAG)** | 찾은 이름으로 상품 검색 · 1등과 비슷한 것만 |

<p align="center"><img src="./docs/readme/shots/vision.jpg" alt="사진 검색" width="45%" /></p>

- **무료 서버에서 동작** — PyTorch 없이 **ONNX Runtime**만 사용 · 메모리 약 150MB (Render 무료 512MB 안)
- **정확도** — 잘라내고 밝기를 바꾼 상품 사진 **90/90**, 다른 섹션의 같은 상품 사진 **3/3** 정답 · 배너 · 아이콘처럼 상품이 아닌 사진은 최고 0.70이라 같은 상품으로 잘못 판단하지 않음

```python
# backend/services/vision_service.py
def match_product(img):
    ids, matrix = _product_vectors()          # 상품 30개 사진 특징 (product_photo_vectors)
    scores = matrix @ photo_vector(img)        # 코사인 유사도
    best = int(scores.argmax())
    if scores[best] < SAME_PRODUCT:            # 0.75 미만이면 같은 상품 아님
        return None
    return {"product_id": ids[best], "similarity": round(float(scores[best]), 3)}
```

---

## 4. 관리자 — 사진만 올리면 정보가 채워진다

`admin.html` — **role=admin 계정만** 들어갈 수 있고, 헤더의 "관리자" 메뉴도 관리자에게만 보입니다.

<p align="center">
  <img src="./docs/readme/shots/admin_ai.jpg" alt="관리자 AI 상품등록" width="49%" />
  <img src="./docs/readme/shots/admin_list.jpg" alt="관리자 상품 관리" width="49%" />
</p>

```text
상품 사진 업로드
→ YOLO 물체 위치 + OpenAI Vision 상품명 · 가격 · 분류 · 보관 추천 (ai_analysis_logs)
→ 입력칸 자동 채움 → 관리자가 확인 · 수정 후 등록
→ products 저장 · 사진은 Supabase Storage · product_images 경로
→ admin_action_logs 작업 기록 (작업자 아이디)
→ 상세 페이지 · 검색 · 상담봇 RAG 조각 · 사진 검색 특징에 바로 반영
```

- **YOLO 결과를 Vision의 힌트로** — "사과(84%)"와 쇼핑몰 가격 예시를 프롬프트에 넣고, `response_format=json_object`로 받아 분류 · 가격 범위를 검사
- 상품명 · 분류 **검색**, **5개씩 페이지**(`count="exact"` + `range()`), 표에서 바로 **수정(PATCH, 바뀐 칸만)** · **삭제(DELETE)**
- 메인에 진열된 원본 상품은 삭제할 수 없게 보호 · 수정 기록에는 **전 → 후** 값

```python
# backend/app.py — 모든 관리자 API 의 공통 검사
def admin_user(request: Request) -> dict:
    if (request.method not in ("GET", "HEAD") and request.cookies.get(SESSION_COOKIE)
            and request.headers.get("x-requested-with") != "orga"):
        raise ForbiddenError("허용되지 않은 요청이에요.")       # 다른 사이트의 위조 요청 차단
    return auth_service.require_admin(session_token(request))    # DB 의 현재 역할이 admin 일 때만
```

---

## 5. 회원 — JWT · HttpOnly 쿠키 · bcrypt

<p align="center">
  <img src="./docs/readme/shots/login.jpg" alt="로그인" width="49%" />
  <img src="./docs/readme/shots/signup.jpg" alt="회원가입" width="39%" />
</p>

| 단계 | 구현 |
|---|---|
| 가입 | 아이디 중복 확인 · 비밀번호 규칙 · 약관 → **bcrypt 해시**로 `users` 저장 → 바로 로그인 |
| 로그인 유지 | JWT(회원 번호 · 역할 · 2시간)를 **HttpOnly 쿠키**로 발급 — 화면의 스크립트가 읽을 수 없음 · `SameSite=Lax` · HTTPS에서 `Secure` |
| 권한 | 요청마다 출입증을 확인하고 **DB의 현재 역할**로 다시 확인 → 권한을 빼면 즉시 반영 |
| 추측 막기 | 없는 아이디도 같은 시간이 걸리게 해시 비교 · 로그인 10분 5회 제한 |

```python
# backend/app.py — 출입증은 HttpOnly 쿠키로만, 화면에는 회원 정보만
response = JSONResponse({"user": issued["user"], "expires_at": issued["expires_at"]})
response.set_cookie("orga_session", issued["token"], max_age=JWT_EXPIRE_SEC,
                    httponly=True, secure=https, samesite="lax", path="/")
```

---

# 03 기술과 문제 해결

## 🧰 이 프로그램은 이런 도구로 만들었습니다

| Frontend | Backend | AI | 인프라 · 점검 |
|---|---|---|---|
| HTML5 · CSS3 (Grid · Flex · 반응형) | FastAPI 0.146 · Uvicorn | OpenAI `gpt-4o-mini` (상담 · Vision) | GitHub · Render (자동 배포) |
| JavaScript ES Modules · fetch | Pydantic (입력 검사) | `text-embedding-3-small` | GitHub Actions (3일마다 서버 · DB 깨우기) |
| Canvas (사진 축소 전송) | Supabase PostgreSQL · RLS · Storage | pgvector (HNSW) | Playwright (자동 점검) |
| HttpOnly 쿠키 로그인 | PyJWT · bcrypt · supabase-py | YOLO11n 탐지 · 분류 · ONNX Runtime | Claude Code (AI 개발 도구 · 결과는 직접 실행해 확인) |

## 🏗 프로그램 구조

```text
브라우저 (HTML · CSS · JS)
   │  fetch · 쿠키
   ▼
FastAPI on Render ───────────▶ Supabase (PostgreSQL · pgvector · Storage · RLS)
   │  상품 · 회원 · 상담봇 · 사진 · 관리자 · 권한 · 횟수 제한 · 오류 처리
   ├─▶ YOLO11n (서버 안 ONNX) — 탐지 320px · 분류 특징 1280
   └─▶ OpenAI API — gpt-4o-mini · 임베딩 · Vision
```

| 영역 | 파일 |
|---|---|
| 화면 | `index.html` · `sub.html` · `login.html` · `signup.html` · `admin.html` |
| 화면 동작 | `js/api.js` · `auth.js` · `chat.js` · `admin.js` · `01~06_fetch_*.js` · `sub.js` |
| 서버 입구 | `backend/app.py` — 주소 · 권한 검사 · 오류 → 상태 코드 |
| 기능 | `backend/services/` — product · auth · chat · rag · vision · admin · rate_limit |
| DB · 모델 | `backend/sql/001~005` · `backend/models/` (YOLO ONNX 2개) |

## 🔌 서버 기능 목록

| 묶음 | 주소 |
|---|---|
| 상품 | `GET /api/sections` · `/api/sections/{key}` · `/api/products?q=` · `/api/products/{id}` |
| 회원 | `GET /api/auth/check-id` · `POST /api/auth/signup` · `/login` · `/logout` · `GET /api/auth/me` |
| 상담봇 | `GET /api/chat/status` · `POST /api/chat` · `POST /api/vision` |
| 관리자 | `GET /api/admin/status` · `GET·POST /api/admin/products` · `PATCH·DELETE /api/admin/products/{id}` · `POST /api/admin/analyze` · `GET /api/admin/logs` |
| 상태 | `GET /health` |

오류는 한 곳에서 상태 코드로 바꿉니다 — 없음 404 · 로그인 필요 401 · 권한 없음 403 · 횟수 초과 429 · 입력 오류 400.

## 🗄 ERD

| 묶음 | 표 |
|---|---|
| 상품 · 화면 | `products` · `sections` · `section_products` · `product_details` · `product_images` |
| AI | `rag_chunks` (vector 1536) · `product_photo_vectors` (특징 1280) · `ai_analysis_logs` |
| 회원 · 기록 | `users` · `admin_action_logs` · `rate_limit_hits` (+ `rate_limit_hit()` 함수) |

모든 표에 RLS를 켜고 서버(`service_role`)만 읽고 쓰게 했습니다. 상품을 지우면 상세 · 사진 · 사진 특징이 함께 삭제됩니다(cascade).

## 🧯 실제로 겪은 오류, 고치기 전과 후

| # | 증상 | 원인 | 해결 |
|---|---|---|---|
| 01 | 상담봇 로봇이 화면을 덮을 만큼 크게 보임 | 예전 CSS가 남은 상태에서 스타일 적용 전에 버튼을 그림 | `chat.css` 분리 · 불러온 뒤에만 그림 · 버전 · `no-cache` |
| 02 | 메인의 모든 상품이 복숭아 상세로 연결 | 섹션 6개 동시 요청 시 DB 연결 1개를 여러 스레드가 공유 | 스레드별 연결 (`threading.local`) · 20번 연속 실패 0 |
| 03 | 관리자 사진 칸에 깨진 글자 | 직접 쓴 `display`가 `hidden`을 덮어씀 | `[hidden]{display:none!important}` |
| 04 | 로그인 말풍선이 카카오 버튼을 가림 | `absolute` + 숫자 여백 → 화면 폭마다 겹침 | 문서 흐름에 넣어 차례로 배치 |
| 05 | 새 아이디도 "이미 사용 중" | 503 오류 응답을 '사용 불가'로 읽음 | `res.ok` 먼저 확인 |
| 06 | 상담봇이 순위 · 반품 기한을 틀림 | 긴 목록을 모델이 직접 세고 추측 | 서버가 계산한 사실을 함께 전달 |

| 01 고치기 전 → 후 | 03 고치기 전 → 후 | 04 고치기 전 → 후 |
|:---:|:---:|:---:|
| <img src="./docs/readme/img/fix_robot_before.jpg" width="100%" /><br><img src="./docs/readme/img/fix_robot_after.jpg" width="100%" /> | <img src="./docs/readme/img/fix_admin_before.jpg" width="100%" /><br><img src="./docs/readme/img/fix_admin_after.jpg" width="100%" /> | <img src="./docs/readme/img/fix_bubble_before.png" width="100%" /><br><img src="./docs/readme/img/fix_bubble_after.png" width="100%" /> |

```python
# 02 · backend/db.py — 수정 전: @lru_cache 로 연결 1개를 모든 요청이 공유
_local = threading.local()

def get_client() -> Client:
    client = getattr(_local, "client", None)
    if client is None:
        client = _local.client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return client
```

## ✅ 검증

점검 스크립트를 함께 만들어, 고칠 때마다 같은 기준으로 로컬과 배포 주소(Render)를 다시 확인했습니다.

| 영역 | 확인한 내용 | 결과 | 도구 |
|---|---|---|---|
| 상담봇 RAG | 질문 22개 (배송 · 반품 · 가격 · 순위 · 이어지는 질문 · 문서 밖 · 규칙 무시) | 22/22 | `test_chat.py` |
| 사진 → 같은 상품 | 잘라내고 밝기를 바꾼 상품 사진 · 다른 섹션 사진 | 90/90 · 3/3 | 직접 시험 |
| 화면 | 메인 카드 33 · 상세 30 · JS · HTTP 오류 0 · 11가지 폭 가로 넘침 0 | 통과 | `check_site.py` |
| 회원 · 관리자 | 가입 · 쿠키 · 유지 · 권한 차단 · 위조 요청 403 · 로그아웃 | 13/13 | `check_auth.py` |
| DB · API | 원본과 DB 일치 · 섹션 · 검색 · 상세 · 잘못된 입력 | 통과 | `verify_seed.py` · `verify_api.py` |
| 안정성 · 보안 | 메인 20번 연속 · `.env` · 코드 · `.git` 접근 404 · 공개 코드의 키 0 | 통과 | `check_site.py` |

## 🚀 실행 방법

```powershell
git clone https://github.com/su4228-prog/orga_whole_food.git
cd orga_whole_food\backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env          # 메모장으로 열어 키 입력 (GitHub에 올리지 않음)

# Supabase SQL Editor 에서 sql/001 → 002 → 003 → 004 → 005 순서로 실행한 뒤
.venv\Scripts\python scripts\seed.py
.venv\Scripts\python scripts\build_details.py
.venv\Scripts\python scripts\backfill_products.py
.venv\Scripts\python scripts\build_rag.py
.venv\Scripts\python scripts\build_photo_vectors.py

.venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 8000
# 가입 후 관리자 지정: .venv\Scripts\python scripts\set_admin.py 아이디
```

자세한 설명은 [`backend/README.md`](./backend/README.md)에 있습니다. Render 환경 변수: `SUPABASE_URL` · `SUPABASE_SERVICE_ROLE_KEY` · `OPENAI_API_KEY` · `JWT_SECRET` · `PYTHON_VERSION` · `TRUST_PROXY`.

---

## 📊 슬라이드 펼쳐보기

<details open>
<summary><b>📂 슬라이드 28장</b> — 01 프로젝트 소개 · 02 주요 기능 · 03 기술과 문제 해결</summary>
<br />

<p align="center">
  <img src="./docs/readme/slides/01.png" alt="01" width="95%" /><br /><sub>01 · 표지</sub><br /><br />
  <img src="./docs/readme/slides/02.png" alt="02" width="95%" /><br /><sub>02 · 오늘 이야기할 세 가지</sub><br /><br />
  <img src="./docs/readme/slides/03.png" alt="03" width="95%" /><br /><sub>03 · 프로젝트 개요</sub><br /><br />
  <img src="./docs/readme/slides/04.png" alt="04" width="95%" /><br /><sub>04 · 기능 지도</sub><br /><br />
  <img src="./docs/readme/slides/05.png" alt="05" width="95%" /><br /><sub>05 · 숫자로 보는 ORGA</sub><br /><br />
  <img src="./docs/readme/slides/06.png" alt="06" width="95%" /><br /><sub>06 · 쇼핑몰 — 상품별 상세 페이지</sub><br /><br />
  <img src="./docs/readme/slides/07.png" alt="07" width="95%" /><br /><sub>07 · 상담봇 — 화면</sub><br /><br />
  <img src="./docs/readme/slides/08.png" alt="08" width="95%" /><br /><sub>08 · 상담봇 — RAG 구현</sub><br /><br />
  <img src="./docs/readme/slides/09.png" alt="09" width="95%" /><br /><sub>09 · 사진으로 상품 찾기 — 화면</sub><br /><br />
  <img src="./docs/readme/slides/10.png" alt="10" width="95%" /><br /><sub>10 · 사진으로 상품 찾기 — YOLO 구현</sub><br /><br />
  <img src="./docs/readme/slides/11.png" alt="11" width="95%" /><br /><sub>11 · 관리자 AI 상품등록 — 화면</sub><br /><br />
  <img src="./docs/readme/slides/12.png" alt="12" width="95%" /><br /><sub>12 · 관리자 AI 상품등록 — 구현</sub><br /><br />
  <img src="./docs/readme/slides/13.png" alt="13" width="95%" /><br /><sub>13 · 관리자 상품 관리 · 기록 — 화면</sub><br /><br />
  <img src="./docs/readme/slides/14.png" alt="14" width="95%" /><br /><sub>14 · 관리자 — 권한 · 검색 · 기록 구현</sub><br /><br />
  <img src="./docs/readme/slides/15.png" alt="15" width="95%" /><br /><sub>15 · 회원 — 화면</sub><br /><br />
  <img src="./docs/readme/slides/16.png" alt="16" width="95%" /><br /><sub>16 · 회원 — JWT · HttpOnly 쿠키 · bcrypt 구현</sub><br /><br />
  <img src="./docs/readme/slides/17.png" alt="17" width="95%" /><br /><sub>17 · 이 프로그램은 이런 도구로 만들었습니다</sub><br /><br />
  <img src="./docs/readme/slides/18.png" alt="18" width="95%" /><br /><sub>18 · 프로그램 구조</sub><br /><br />
  <img src="./docs/readme/slides/19.png" alt="19" width="95%" /><br /><sub>19 · 서버 기능 20가지</sub><br /><br />
  <img src="./docs/readme/slides/20.png" alt="20" width="95%" /><br /><sub>20 · ERD</sub><br /><br />
  <img src="./docs/readme/slides/21.png" alt="21" width="95%" /><br /><sub>21 · 사진 한 장이 지나가는 길</sub><br /><br />
  <img src="./docs/readme/slides/22.png" alt="22" width="95%" /><br /><sub>22 · 오류 01 — 상담봇 CSS</sub><br /><br />
  <img src="./docs/readme/slides/23.png" alt="23" width="95%" /><br /><sub>23 · 오류 02 — DB 연결</sub><br /><br />
  <img src="./docs/readme/slides/24.png" alt="24" width="95%" /><br /><sub>24 · 오류 03 — hidden</sub><br /><br />
  <img src="./docs/readme/slides/25.png" alt="25" width="95%" /><br /><sub>25 · 오류 04 — 말풍선</sub><br /><br />
  <img src="./docs/readme/slides/26.png" alt="26" width="95%" /><br /><sub>26 · 오류 05 · 06</sub><br /><br />
  <img src="./docs/readme/slides/27.png" alt="27" width="95%" /><br /><sub>27 · 검증</sub><br /><br />
  <img src="./docs/readme/slides/28.png" alt="28" width="95%" /><br /><sub>28 · 이 프로젝트에서 배운 것</sub><br /><br />
</p>

</details>

---

<sub>ORGA Whole Foods · su4228-prog</sub>
