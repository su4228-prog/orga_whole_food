"""API 요청 · 응답 모양 — 상품 응답은 사이트가 읽던 JSON과 같은 모양을 유지하고, 입력은 길이 · 형식을 검사합니다."""
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class SectionSummary(BaseModel):
    key: str
    title: str
    subtitle: Optional[str] = None


class CardItem(BaseModel):
    """섹션의 상품 카드 1개 (값이 없는 항목은 응답에서 빠집니다)"""
    model_config = ConfigDict(extra="allow")

    id: int                                   # 상품 번호 (전체에서 유일)
    name: str
    brand: Optional[str] = None
    image: Optional[str] = None               # 신상품(new)은 main_image / thumb 을 씁니다
    price: Optional[str] = None               # "4,200원"
    discount: Optional[str] = None            # "35%"
    unit_price: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    badge: Optional[str] = None
    delivery_badge: Optional[str] = None
    extra_badge: Optional[str] = None


class SectionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    section_title: str
    subtitle: Optional[str] = None
    items: list[CardItem]


class ProductSummary(BaseModel):
    """검색 결과 1건"""
    id: int
    name: str
    brand: Optional[str] = None
    image: Optional[str] = None
    price: Optional[str] = None
    discount: Optional[str] = None
    unit_price: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None


class ProductDetailResponse(BaseModel):
    """상세 페이지 데이터 — sub.json 과 같은 모양(product · aiRecommend · infoTabs · detailContent)"""
    id: int
    hasFullDetail: bool                       # 긴 상세 설명이 준비된 상품이면 true
    product: dict[str, Any]
    aiRecommend: list[dict[str, Any]]
    infoTabs: list[dict[str, Any]]
    detailContent: list[dict[str, Any]]


class ChatTurn(BaseModel):
    """이전 대화 한 줄 (흐름을 이어가기 위해 최근 6개까지만 받음)"""
    role: Literal["user", "assistant"]
    content: str = Field(max_length=600)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=300, description="질문 (300자까지)")
    history: list[ChatTurn] = Field(default_factory=list, max_length=6)


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list, description="벡터 검색으로 찾아 참고한 자료 이름")


class VisionRequest(BaseModel):
    image: str = Field(min_length=100, max_length=2_800_000,
                       description="사진 (data:image/jpeg;base64,... 형식, 화면에서 640px 이하로 줄여서 보냄)")


class Detection(BaseModel):
    label: str                                # YOLO 이름 (apple)
    label_ko: str                             # 한국어 이름 (사과)
    score: float                              # 확신도 0~1
    box: list[float]                          # [x1, y1, x2, y2] 사진 크기 대비 비율 0~1
    food: bool                                # 상품 검색에 쓰는 식품 · 용기인지


class LoginRequest(BaseModel):
    login_id: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=200)


class SignupRequest(BaseModel):
    login_id: str = Field(min_length=1, max_length=40, description="영문 소문자 · 숫자 4~20자")
    password: str = Field(min_length=1, max_length=200, description="영문 + 숫자 8자 이상")
    name: str = Field(min_length=1, max_length=40)


class AdminAnalyzeRequest(BaseModel):
    image: str = Field(min_length=100, max_length=2_800_000, description="상품 사진 (data URL)")
    file_name: Optional[str] = Field(None, max_length=200)


class AdminProductPatch(BaseModel):
    """상품 수정 — 보낸 칸만 바뀝니다"""
    name: Optional[str] = Field(None, max_length=100)
    price: Optional[int] = None
    discount_rate: Optional[int] = None
    category: Optional[str] = Field(None, max_length=30)
    storage: Optional[str] = Field(None, max_length=30)
    description: Optional[str] = Field(None, max_length=200)


class AdminProductCreate(AdminProductPatch):
    image: str = Field(min_length=100, max_length=2_800_000, description="상품 사진 (data URL)")
    analysis_id: Optional[int] = Field(None, description="이 사진을 분석한 AI 분석 기록 번호")


class PhotoMatch(BaseModel):
    product_id: int
    similarity: float                         # 사진 특징 일치도 0~1


class VisionResponse(BaseModel):
    message: str
    detections: list[Detection]
    products: list[ProductSummary]
    match: Optional[PhotoMatch] = None        # 같은 상품을 찾았을 때
