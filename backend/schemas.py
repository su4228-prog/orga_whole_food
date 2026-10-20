"""API 응답 모양 정의 — 지금 사이트가 읽는 JSON과 같은 모양을 유지합니다."""
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
