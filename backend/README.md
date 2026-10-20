# 올가 쇼핑몰 서버 — 처음 켜는 방법

상품 정보(Supabase)와 상담봇(OpenAI)을 화면에 전달하는 서버입니다.
서버를 켜지 않아도 사이트는 열리지만, 그때는 `json/` 폴더의 예비 데이터로 보이고 상담봇은 나타나지 않습니다.

## 준비물

- Python 3.11 이상
- Supabase 프로젝트 (표 만들기: `sql/001_create_tables.sql` 을 Supabase **SQL Editor** 에서 실행)
- OpenAI API 키 (상담봇용 · 없으면 상담봇만 꺼짐)

## 처음 한 번만

`backend` 폴더에서 차례대로 실행합니다.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

그다음 메모장으로 `.env` 를 열어 `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY` 를 채웁니다.
`.env` 는 비밀 파일이라 GitHub에 올라가지 않도록 막혀 있습니다. 키를 다른 파일이나 채팅에 붙여 넣지 마세요.

DB가 비어 있다면 상품을 넣습니다.

```powershell
.venv\Scripts\python scripts\check_connection.py
.venv\Scripts\python scripts\seed.py
.venv\Scripts\python scripts\build_details.py
```

## 매번 켤 때

```powershell
.venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

| 주소 | 내용 |
|---|---|
| http://127.0.0.1:8000/ | 사이트 (서버 데이터 + 상담봇) |
| http://127.0.0.1:8000/docs | 서버 기능 목록 (직접 눌러 보며 시험 가능) |
| http://127.0.0.1:8000/health | 서버 상태 확인 |

끌 때는 실행 창에서 `Ctrl + C` 를 누릅니다.

## 점검 도구 (`scripts/`)

| 파일 | 하는 일 |
|---|---|
| `check_connection.py` | Supabase 연결 확인 |
| `seed.py` | 상품·섹션 데이터 넣기 (`--dry-run` 미리보기, `--reset` 지우고 다시) |
| `build_details.py` | 상품 30개의 상세 페이지 내용 만들기 |
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
│  ├─ chat_service.py     상담봇 (이용 안내 + 상품 정보로 답변)
│  └─ rate_limit.py       질문 횟수 제한
├─ rag_docs/policy.md  상담봇이 참고하는 쇼핑몰 이용 안내
├─ data/               상세 페이지 문구
├─ sql/                Supabase 표 만들기
└─ scripts/            데이터 넣기 · 점검 도구
```

## 안전장치

- 비밀 키는 `.env` 에만 두고, 서버는 `.env` · 코드 · `.git` 파일을 주소로 열어 주지 않습니다.
- 상담봇 질문은 한 사람당 10분에 10번, 사이트 전체 하루 300번까지입니다 (`.env` 에서 조절).
- 서버 오류가 나도 화면에는 짧은 안내 문구만 보이고 내부 정보는 드러나지 않습니다.
