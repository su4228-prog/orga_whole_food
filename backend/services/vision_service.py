"""사진으로 상품 찾기 — YOLO(물체 찾기 모델)로 사진 속 식품을 찾고, 벡터 검색으로 비슷한 상품을 추천합니다.

무료 서버(CPU 0.1개 · 메모리 512MB)에서도 돌도록:
- PyTorch 없이 ONNX Runtime 만 사용 (모델: models/yolo11n_320.onnx, 약 10MB)
- 가장 작은 YOLO11n 을 320px 크기로 변환해 계산량을 줄임
- 처음 사진이 들어올 때 한 번만 모델을 불러오고, 계산은 1개 스레드로만
- 화면에서 사진을 640px 이하로 줄여서 보냄

모델은 COCO 데이터의 일반 물체 80종(사과 · 바나나 · 병 · 그릇 등)을 알아봅니다.
올가 상품 하나하나를 구별하도록 학습한 모델은 아니므로, 찾은 물체 이름으로 비슷한 상품을 검색해 추천합니다.
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

_session = None
_lock = threading.Lock()


def enabled() -> bool:
    return MODEL_FILE.exists()


def _model():
    global _session
    if _session is None:
        with _lock:
            if _session is None:
                import onnxruntime as ort          # 사진 기능을 쓸 때만 불러와 서버 시작 메모리를 아낌
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 1
                opts.inter_op_num_threads = 1
                _session = ort.InferenceSession(str(MODEL_FILE), opts, providers=["CPUExecutionProvider"])
                log.info("YOLO 모델 불러옴: %s", MODEL_FILE.name)
    return _session


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
