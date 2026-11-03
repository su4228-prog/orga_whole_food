# 올가 쇼핑몰 서버 — 처음 켜는 방법

상품 정보(Supabase), 상담봇(OpenAI + 벡터 검색 RAG), 사진으로 상품 찾기(YOLO), 회원 로그인(JWT), 관리자 AI 상품등록을 화면에 전달하는 서버입니다.
서버를 켜지 않아도 사이트는 열리지만, 그때는 `json/` 폴더의 예비 데이터로 보이고 상담봇은 나타나지 않습니다.

## 준비물

- Python 3.11 이상
- Supabase 프로젝트 (Supabase **SQL Editor** 에서 `sql/001_create_tables.sql` → `002_vector_rag.sql` → `003_admin.sql` → `004_users.sql` → `005_rate_limit_and_photo.sql` 순서로 실행)
- OpenAI API 키 (상담봇용 · 없으면 상담봇만 꺼짐)

## 처음 한 번만

`backend` 폴더에서 차례대로 실행합니다.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

그다음 메모장으로 `.env` 를 열어 `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY`, `JWT_SECRET`(길고 무작위인 글자) 를 채웁니다.
`.env` 는 비밀 파일이라 GitHub에 올라가지 않도록 막혀 있습니다. 키를 다른 파일이나 채팅에 붙여 넣지 마세요.

DB가 비어 있다면 상품을 넣습니다.

```powershell
.venv\Scripts\python scripts\check_connection.py
.venv\Scripts\python scripts\seed.py
.venv\Scripts\python scripts\build_details.py
.venv\Scripts\python scripts\backfill_products.py
.venv\Scripts\python scripts\build_rag.py
.venv\Scripts\python scripts\build_photo_vectors.py
```

`build_rag.py` 는 이용 안내 · 상품 설명을 조각내 벡터 검색 보관함에 넣습니다. 안내 문서나 상품 설명을 고치면 다시 실행합니다.

사이트에서 회원가입한 뒤 그 계정을 관리자로 지정합니다 (관리자 권한은 화면에서 줄 수 없습니다).

```powershell
.venv\Scripts\python scripts\set_admin.py 아이디
```

## 매번 켤 때

```powershell
.venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

| 주소 | 내용 |
|---|---|
| http://127.0.0.1:8000/ | 사이트 (서버 데이터 + 상담봇) |
| http://127.0.0.1:8000/login.html | 로그인 · 회원가입 |
| http://127.0.0.1:8000/admin.html | 관리자 (role=admin 계정만) |
| http://127.0.0.1:8000/docs | 서버 기능 목록 (직접 눌러 보며 시험 가능) |
| http://127.0.0.1:8000/health | 서버 상태 확인 |

끌 때는 실행 창에서 `Ctrl + C` 를 누릅니다.

## 점검 도구 (`scripts/`)

| 파일 | 하는 일 |
|---|---|
| `check_connection.py` | Supabase 연결 확인 |
| `seed.py` | 상품·섹션 데이터 넣기 (`--dry-run` 미리보기, `--reset` 지우고 다시) |
| `build_details.py` | 상품 30개의 상세 페이지 내용 만들기 |
| `build_rag.py` | 상담봇 벡터 검색 보관함 채우기 (`--dry-run` 조각만 미리보기) |
| `backfill_products.py` | 원본 상품의 분류 · 보관 · 설명 칸 채우기 (관리자 검색용) |
| `set_admin.py` | 회원에게 관리자 권한 주기 · 빼기 (`--remove`) |
| `build_photo_vectors.py` | 상품 사진 특징 만들기 (사진으로 같은 상품 찾기용) |
| `check_auth.py` | 가입 · 로그인 유지(쿠키) · 권한 · 위조 요청 차단 · 로그아웃 점검 (시험 계정은 자동 삭제) |
| `verify_seed.py` | DB 데이터가 원본과 같은지 확인 |
| `verify_api.py` | 서버 기능 확인 (서버를 켠 상태에서) |
| `test_chat.py` | 상담봇에 질문 22개를 보내 답 확인 (OpenAI 사용료 발생) |
| `check_site.py` | 메인·상세 30개·상담봇 위치·보안까지 화면 전체 점검 (`pip install playwright` 필요) |

## 폴더 구성

```
backend/
├─ app.py              서버 입구 (주소별 기능 연결)
├─ config.py           .env 설정 읽기
├─ db.py               Supabase 연결
├─ schemas.py          주고받는 데이터 모양
├─ services/
│  ├─ product_service.py  상품 · 섹션 · 상세
│  ├─ chat_service.py     상담봇 (벡터 검색으로 찾은 근거로 답변)
│  ├─ rag_service.py      벡터 검색 (조각 만들기 · 임베딩 · 비슷한 조각 찾기)
│  ├─ vision_service.py   사진 속 식품 찾기 (YOLO11n · ONNX Runtime)
│  ├─ auth_service.py     회원가입 · 로그인 (bcrypt · JWT)
│  ├─ admin_service.py    관리자 상품 관리 · AI 상품등록 · 기록
│  └─ rate_limit.py       사용 횟수 제한
├─ rag_docs/policy.md  상담봇이 참고하는 쇼핑몰 이용 안내
├─ models/             YOLO 모델 (탐지 yolo11n_320.onnx 10MB · 분류 특징 yolo11n_cls_features.onnx 6MB)
├─ data/               상세 페이지 문구
├─ sql/                Supabase 표 만들기
└─ scripts/            데이터 넣기 · 점검 도구
```

## 안전장치

- 비밀 키는 `.env` 에만 두고, 서버는 `.env` · 코드 · `.git` 파일을 주소로 열어 주지 않습니다.
- 상담봇 질문은 한 사람당 10분에 10번, 사이트 전체 하루 300번까지입니다 (`.env` 에서 조절). 횟수는 Supabase 에 기록해 서버가 다시 켜져도 유지됩니다.
- 비밀번호는 bcrypt 해시로만 저장하고, 로그인 출입증(JWT)은 HttpOnly 쿠키로 보내 화면의 스크립트가 읽을 수 없습니다 (2시간 뒤 만료). 로그인 시도는 10분에 5번까지입니다.
- 쿠키로 로그인한 상태에서 데이터를 바꾸는 관리자 요청은 사이트 화면이 붙이는 머리말(`X-Requested-With`)이 있어야 해 다른 사이트의 위조 요청을 막습니다.
- 관리자 API 는 출입증을 확인한 뒤 DB 의 현재 역할이 admin 일 때만 동작합니다.
- 사진 검색은 한 사람당 10분에 6번, 하루 200번까지입니다. 사진은 화면에서 640px 이하로 줄여 보내고, 서버에 저장하지 않습니다.
- 서버 오류가 나도 화면에는 짧은 안내 문구만 보이고 내부 정보는 드러나지 않습니다.

## 사진으로 상품 찾기 (YOLO) — 무료 서버용 설계

- 탐지 모델: Ultralytics **YOLO11n**을 320px 입력의 **ONNX** 로 변환 — 사진 속 물체의 위치와 이름
- 분류 모델: **YOLO11n-cls** 의 마지막 층 전 **특징 1280개**만 꺼내도록 변환 — 상품 30개 사진 특징(`product_photo_vectors`)과 비교해 같은 상품 찾기 (일치도 0.75 이상)
- 서버에서는 PyTorch 없이 **ONNX Runtime**(CPU, 스레드 1개)만 씁니다. 사진 검색을 처음 쓸 때 모델을 불러오며, 메모리는 약 150MB 입니다 (Render 무료 512MB 안).
- 같은 상품이 없으면 탐지한 식품 이름으로 **상품 이름 검색 + 벡터 검색**을 해 비슷한 상품을 추천합니다.
- 모델을 다시 만들 때 (PyTorch 가 필요해 서버와 다른 임시 환경에서 실행):

```powershell
pip install ultralytics onnx onnxslim onnxscript
yolo export model=yolo11n.pt format=onnx imgsz=320 opset=17 simplify=True
# 분류 특징 모델은 yolo11n-cls.pt 의 마지막 Linear 전까지를 torch.onnx.export 로 내보냄 (입력 224px · 출력 1280)
```

> YOLO11 · Ultralytics 는 AGPL-3.0 라이선스입니다. 이 저장소는 공개 저장소로 소스를 함께 공개합니다.
