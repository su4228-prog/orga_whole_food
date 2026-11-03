"""사진으로 상품 찾기 — YOLO 두 가지로 사진을 봅니다.

1) 같은 상품 찾기 — YOLO11n 분류 모델로 사진의 특징(숫자 1280개)을 뽑아 올가 상품 사진들의 특징과 비교
   (일치도 0.75 이상이면 같은 상품으로 판단 · 상품 사진 특징은 product_photo_vectors 표)
2) 물체 찾기 — YOLO11n 탐지 모델로 사진 속 식품(사과 · 병 · 그릇 …)의 위치와 이름을 찾고,
   그 이름으로 상품 이름 검색 + 벡터 검색(RAG)을 해 비슷한 상품을 추천

무료 서버(CPU 0.1개 · 메모리 512MB)에서도 돌도록:
- PyTorch 없이 ONNX Runtime 만 사용 (models/yolo11n_320.onnx 10MB · yolo11n_cls_features.onnx 6MB)
- 가장 작은 YOLO11n 을 320px 크기로 변환해 계산량을 줄임
- 처음 사진이 들어올 때 한 번만 모델을 불러오고, 계산은 1개 스레드로만
- 화면에서 사진을 640px 이하로 줄여서 보냄

흐름: decode(사진) → match_product(같은 상품) + detect(물체) → search_terms → photo_search(추천 · 안내 문장)
"""
import base64
import io
import logging
import threading
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

log = logging.getLogger("olga.vision")

MODEL_FILE = Path(__file__).resolve().parents[1] / "models" / "yolo11n_320.onnx"
SIZE = 320
CONF = 0.25
IOU = 0.45
MAX_BYTES = 2_000_000                  # 줄인 사진 기준 2MB 까지
SIMILAR_GAP = 0.08                     # 벡터 검색 추천은 1등과 유사도 차이가 이 안쪽인 상품만
FEATURE_FILE = MODEL_FILE.with_name("yolo11n_cls_features.onnx")
FEATURE_SIZE = 224
SAME_PRODUCT = 0.75                    # 사진 특징 일치도가 이 이상이면 같은 상품 (배너 · 아이콘 등 상품이 아닌 사진은 최고 0.70)
Image.MAX_IMAGE_PIXELS = 25_000_000    # 지나치게 큰 사진(압축 폭탄) 거부

COCO = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light",
        "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
        "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
        "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
        "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
        "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
        "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard",
        "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
        "scissors", "teddy bear", "hair drier", "toothbrush"]

# 찾은 물체 → (한국어 이름, 상품 검색에 쓸 말). 검색어가 없는 물체는 상품을 찾지 않습니다.
FOOD = {
    "apple": ("사과", "사과 과일"),
    "orange": ("오렌지", "과일 사과 배"),
    "banana": ("바나나", "과일 간식"),
    "broccoli": ("브로콜리", "채소 버섯 신선식품"),
    "carrot": ("당근", "채소 버섯 신선식품"),
    "sandwich": ("샌드위치", "간식 웨이퍼 과자"),
    "hot dog": ("핫도그", "간편식 만두"),
    "pizza": ("피자", "간편식 만두"),
    "donut": ("도넛", "달콤한 간식 디저트 과자"),
    "cake": ("케이크", "달콤한 간식 디저트 모나카"),
    "bottle": ("병", "병에 담긴 청 병조림 음료"),
    "wine glass": ("와인잔", "음료 청 선물세트"),
    "cup": ("컵", "차 음료 홍삼"),
    "bowl": ("그릇", "밥반찬 김자반 국"),
}
COCO_KO = ["사람", "자전거", "자동차", "오토바이", "비행기", "버스", "기차", "트럭", "배", "신호등",
           "소화전", "정지 표지판", "주차 미터기", "벤치", "새", "고양이", "개", "말", "양", "소",
           "코끼리", "곰", "얼룩말", "기린", "배낭", "우산", "핸드백", "넥타이", "여행 가방", "원반",
           "스키", "스노보드", "공", "연", "야구 방망이", "야구 글러브", "스케이트보드", "서핑보드",
           "테니스 라켓", "병", "와인잔", "컵", "포크", "칼", "숟가락", "그릇", "바나나", "사과",
           "샌드위치", "오렌지", "브로콜리", "당근", "핫도그", "피자", "도넛", "케이크", "의자", "소파",
           "화분", "침대", "식탁", "변기", "TV", "노트북", "마우스", "리모컨", "키보드",
           "휴대폰", "전자레인지", "오븐", "토스터", "싱크대", "냉장고", "책", "시계", "꽃병",
           "가위", "곰 인형", "헤어드라이어", "칫솔"]
NAMES_KO = dict(zip(COCO, COCO_KO))

_sessions: dict = {}
_lock = threading.Lock()
_vectors = {"at": 0.0, "ids": [], "matrix": None}


def enabled() -> bool:
    return MODEL_FILE.exists()


def _load(path: Path):
    """ONNX 모델을 처음 쓸 때 한 번만 불러옴 (서버 시작 메모리 절약 · 계산은 1개 스레드)"""
    if path not in _sessions:
        with _lock:
            if path not in _sessions:
                import onnxruntime as ort
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 1
                opts.inter_op_num_threads = 1
                _sessions[path] = ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])
                log.info("모델 불러옴: %s", path.name)
    return _sessions[path]


def _model():
    return _load(MODEL_FILE)


class BadImage(ValueError):
    """사진을 읽을 수 없을 때 — 메시지는 사용자에게 그대로 보여줍니다."""


def decode(data_url: str) -> Image.Image:
    raw = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    try:
        blob = base64.b64decode(raw, validate=True)
    except Exception:
        raise BadImage("사진 데이터를 읽을 수 없어요.")
    if len(blob) > MAX_BYTES:
        raise BadImage("사진이 너무 커요. 2MB 이하로 올려 주세요.")
    try:
        img = Image.open(io.BytesIO(blob))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception:
        raise BadImage("사진 파일이 아니거나 손상된 파일이에요.")
    return img


def _letterbox(img: Image.Image):
    """비율을 유지한 채 320×320 안에 넣고 남는 곳은 회색으로 채움 (YOLO 학습 방식과 동일)"""
    w, h = img.size
    r = min(SIZE / w, SIZE / h)
    nw, nh = round(w * r), round(h * r)
    canvas = Image.new("RGB", (SIZE, SIZE), (114, 114, 114))
    dx, dy = (SIZE - nw) // 2, (SIZE - nh) // 2
    canvas.paste(img.resize((nw, nh), Image.BILINEAR), (dx, dy))
    x = np.asarray(canvas, dtype=np.float32).transpose(2, 0, 1)[None] / 255.0
    return x, r, dx, dy


def _nms(boxes: np.ndarray, scores: np.ndarray) -> list[int]:
    order, keep = scores.argsort()[::-1], []
    while order.size:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(boxes[i, 0], boxes[order[1:], 0])
        yy1 = np.maximum(boxes[i, 1], boxes[order[1:], 1])
        xx2 = np.minimum(boxes[i, 2], boxes[order[1:], 2])
        yy2 = np.minimum(boxes[i, 3], boxes[order[1:], 3])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        area = lambda b: (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
        iou = inter / (area(boxes[[i]]) + area(boxes[order[1:]]) - inter + 1e-9)
        order = order[1:][iou < IOU]
    return keep


def detect(img: Image.Image, max_det: int = 10) -> list[dict]:
    """사진 속 물체 목록. box 는 사진 크기 대비 비율(0~1)이라 화면에서 바로 그릴 수 있음."""
    w, h = img.size
    x, r, dx, dy = _letterbox(img)
    sess = _model()
    out = sess.run(None, {sess.get_inputs()[0].name: x})[0][0].T      # (후보 수, 4 + 80)
    scores_all = out[:, 4:]
    cls = scores_all.argmax(1)
    conf = scores_all[np.arange(len(cls)), cls]
    m = conf >= CONF
    if not m.any():
        return []
    cxcywh, cls, conf = out[m, :4], cls[m], conf[m]
    boxes = np.stack([cxcywh[:, 0] - cxcywh[:, 2] / 2, cxcywh[:, 1] - cxcywh[:, 3] / 2,
                      cxcywh[:, 0] + cxcywh[:, 2] / 2, cxcywh[:, 1] + cxcywh[:, 3] / 2], 1)
    boxes = (boxes - [dx, dy, dx, dy]) / r                              # 원래 사진 좌표로 되돌림
    keep = _nms(boxes + cls[:, None] * 4096, conf)[:max_det]           # 같은 종류끼리만 겹침 제거
    result = []
    for i in keep:
        label = COCO[int(cls[i])]
        x1, y1, x2, y2 = boxes[i]
        result.append({
            "label": label,
            "label_ko": FOOD.get(label, (NAMES_KO.get(label, label),))[0],
            "score": round(float(conf[i]), 3),
            "box": [round(float(np.clip(v, 0, s)) / s, 4) for v, s in ((x1, w), (y1, h), (x2, w), (y2, h))],
            "food": label in FOOD,
        })
    return result


def search_terms(detections: list[dict]) -> tuple[list[str], str]:
    """(찾은 식품 이름들, 상품 검색어). 점수 높은 식품 순, 같은 종류는 한 번만."""
    names, terms = [], []
    for d in sorted(detections, key=lambda d: -d["score"]):
        if d["food"] and d["label_ko"] not in names:
            names.append(d["label_ko"])
            terms.append(FOOD[d["label"]][1])
    return names, " ".join(terms[:2])


# ───────────────────────── 같은 상품 찾기 (사진 특징 비교) ─────────────────────────
def photo_vector(img: Image.Image) -> np.ndarray:
    """사진 → 특징 1280개 (짧은 변 224px 로 맞추고 가운데를 잘라 YOLO 분류 모델에 넣음 · 길이 1로 맞춤)"""
    img = img.convert("RGB")
    w, h = img.size
    r = FEATURE_SIZE / min(w, h)
    img = img.resize((max(FEATURE_SIZE, round(w * r)), max(FEATURE_SIZE, round(h * r))), Image.BILINEAR)
    w, h = img.size
    left, top = (w - FEATURE_SIZE) // 2, (h - FEATURE_SIZE) // 2
    x = np.asarray(img.crop((left, top, left + FEATURE_SIZE, top + FEATURE_SIZE)), dtype=np.float32)
    sess = _load(FEATURE_FILE)
    v = sess.run(None, {sess.get_inputs()[0].name: x.transpose(2, 0, 1)[None] / 255.0})[0][0]
    return v / (np.linalg.norm(v) + 1e-9)


def _product_vectors():
    """상품 사진 특징 (5분 동안 재사용) → (상품 번호 목록, 행렬)"""
    import time
    from db import get_client
    if time.time() - _vectors["at"] > 300 or _vectors["matrix"] is None:
        rows = get_client().table("product_photo_vectors").select("product_id,vector").execute().data
        _vectors.update(at=time.time(), ids=[r["product_id"] for r in rows],
                        matrix=np.array([r["vector"] for r in rows], dtype=np.float32) if rows else None)
    return _vectors["ids"], _vectors["matrix"]


def refresh_vectors() -> None:
    _vectors["at"] = 0.0


def match_product(img: Image.Image) -> dict | None:
    """올린 사진과 가장 닮은 올가 상품 {product_id, similarity} — 일치도가 기준보다 낮으면 None"""
    if not FEATURE_FILE.exists():
        return None
    try:
        ids, matrix = _product_vectors()
    except Exception as e:                                 # 표가 아직 없으면 물체 찾기만
        log.warning("상품 사진 특징을 읽지 못했습니다: %s", e)
        return None
    if matrix is None:
        return None
    scores = matrix @ photo_vector(img)
    best = int(scores.argmax())
    if scores[best] < SAME_PRODUCT:
        return None
    return {"product_id": ids[best], "similarity": round(float(scores[best]), 3)}


def load_image(path_or_url: str) -> Image.Image:
    """상품 사진 경로(./img/…) 또는 Storage 주소 → 사진"""
    if path_or_url.startswith("http"):
        import httpx
        return Image.open(io.BytesIO(httpx.get(path_or_url, timeout=30).content))
    return Image.open(Path(__file__).resolve().parents[2] / path_or_url.lstrip("./"))


def save_product_vector(product_id: int, image: str) -> None:
    """상품 1개의 사진 특징 저장 (scripts/build_photo_vectors.py · 관리자 등록 직후)"""
    from db import get_client
    vector = photo_vector(load_image(image))
    get_client().table("product_photo_vectors").upsert(
        {"product_id": product_id, "image": image, "vector": [round(float(x), 6) for x in vector]}).execute()
    refresh_vectors()


# ───────────────────────── 사진 → 추천 상품 ─────────────────────────
def _josa(word: str, with_final: str, without_final: str) -> str:
    """한글 받침에 맞는 조사 (사과를 / 당근을)"""
    last = word[-1]
    has_final = "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28 > 0
    return word + (with_final if has_final else without_final)


def _recommend(names: list[str], query: str, k: int = 3) -> list[dict]:
    """이름이 그대로 들어간 상품을 먼저, 모자라면 벡터 검색으로 뜻이 비슷한 상품을 채움"""
    from services import product_service, rag_service      # 사진 기능을 쓸 때만 불러옴

    ids: list[int] = []
    for name in names:
        ids += [p["id"] for p in product_service.search_products(name, k)]
    if len(ids) < k and query:
        if rag_service.available():
            hits = rag_service.search(query, "product", k + 2)
            top = hits[0]["similarity"] if hits else 0
            ids += [c["metadata"]["product_id"] for c in hits if c["similarity"] >= top - SIMILAR_GAP]
        else:                                               # 벡터 검색을 못 쓰면 검색어 낱말로 이름 검색
            for word in (w for w in query.split() if len(w) >= 2):     # 한 글자('청'·'국')는 엉뚱한 상품이 걸려 제외
                ids += [p["id"] for p in product_service.search_products(word, k)]
    return product_service.products_by_ids(list(dict.fromkeys(ids))[:k])


def photo_search(data_url: str) -> dict:
    """사진 1장 → {안내 문장, 찾은 물체, 같은 상품, 추천 상품}"""
    from services import product_service

    img = decode(data_url)
    match = match_product(img)
    detections = detect(img)
    names, query = search_terms(detections)
    products = _recommend(names, query) if names else []

    if match:                                              # 같은 상품을 찾았으면 맨 앞에
        same = product_service.products_by_ids([match["product_id"]])
        if same:
            products = same + [p for p in products if p["id"] != match["product_id"]][:2]
            name = same[0]["name"]
            message = (f"사진 속 상품은 '{name}' 같아요 (일치도 {round(match['similarity'] * 100)}%). "
                       + ("함께 볼 만한 상품도 골라 봤어요." if len(products) > 1 else ""))
            return {"message": message.strip(), "detections": detections, "products": products, "match": match}

    if names:
        message = f"사진에서 {_josa(', '.join(names), '을', '를')} 찾았어요. "
        message += "비슷한 올가 상품을 골라 봤어요." if products else "아쉽게도 비슷한 상품은 찾지 못했어요."
    elif detections:
        seen = ", ".join(dict.fromkeys(d["label_ko"] for d in detections))
        message = f"사진에서 {_josa(seen, '은', '는')} 보이지만 식품은 찾지 못했어요. 과일이나 음식이 크게 보이게 찍어 주세요."
    else:
        message = "사진에서 알아볼 수 있는 물체를 찾지 못했어요. 식품이 크게 보이게 찍어 주세요."
    return {"message": message, "detections": detections, "products": products}
