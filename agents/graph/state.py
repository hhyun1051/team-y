"""
State definitions for Office Automation Graph

LangGraph의 TypedDict 기반 상태 정의
"""

from typing import Annotated, Literal, Optional, TypedDict, Union
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages


class OfficeAutomationState(TypedDict):
    """
    사무 자동화 그래프 상태

    워크플로우: 입력 → 의도분류 → 파싱 → 승인 → 문서생성
    """
    # 메시지 히스토리
    messages: Annotated[list, add_messages]

    # 입력 정보
    raw_input: Optional[str]  # 원본 입력
    input_type: Literal["text", "voice"]  # 입력 타입

    # 분류 결과
    scenario: Optional[Literal["delivery", "product_order", "aluminum_calculation", "help"]]  # 시나리오
    confidence: Optional[float]  # 분류 신뢰도
    active_scenario: Optional[Literal["delivery", "product_order", "aluminum_calculation"]]  # 진행 중인 시나리오 (멀티턴 유지)
    active_scenario_timestamp: Optional[float]  # active_scenario 설정 시간 (Unix timestamp)

    # 파싱 결과 (시나리오별로 다른 타입)
    delivery_info: Optional["DeliveryInfo"]  # 운송장 정보
    product_order_info: Optional["ProductOrderInfo"]  # 제품 주문 정보
    aluminum_calculation_info: Optional["AluminumCalculationInfo"]  # 알루미늄 계산 정보
    parsing_error: Optional[str]  # 파싱 에러 메시지

    # HITL 상태 (Human-in-the-Loop)
    awaiting_approval: bool  # 승인 대기 중
    approval_decision: Optional[Literal["approve", "reject"]]  # 승인 결정 (approve/reject)
    approval_message: Optional[str]  # 사용자에게 보여줄 승인 요청 메시지
    reject_message: Optional[str]  # 거절 시 사용자 메시지

    # 인쇄 HITL 상태
    awaiting_print_approval: bool  # 인쇄 승인 대기 중
    print_approval_decision: Optional[Literal["approve", "reject"]]  # 인쇄 승인 결정
    print_approval_message: Optional[str]  # 인쇄 승인 요청 메시지
    print_status: Optional[Literal["success", "failed", "error"]]  # 인쇄 상태

    # 문서 생성 결과
    docx_path: Optional[str]  # DOCX 파일 경로
    pdf_path: Optional[str]  # PDF 파일 경로
    image_paths: Optional[list]  # 이미지 파일 경로 리스트 (PNG)

    # 워크플로우 제어
    current_step: Literal[
        "classify",    # 의도 분류
        "parse",       # 파싱
        "approve",     # 승인 대기
        "generate",    # 문서 생성
        "complete",    # 완료
        "help",        # 도움말
        "error"        # 에러
    ]

    # 메타데이터
    discord_user_id: Optional[str]
    discord_channel_id: Optional[str]
    thread_id: Optional[str]


class IntentClassification(BaseModel):
    """의도 분류 결과"""
    scenario: Literal["delivery", "product_order", "aluminum_calculation", "help"] = Field(
        description="시나리오 구분: delivery(운송장), product_order(거래명세서), aluminum_calculation(알루미늄 계산), help(도움말)"
    )
    confidence: float = Field(description="분류 신뢰도 (0.0~1.0)")
    reasoning: Optional[str] = Field(None, description="분류 근거")


class DeliveryInfo(BaseModel):
    """운송장 정보"""
    # 하차지 정보 (필수)
    unloading_site: str = Field(description="하차지 (회사 이름)")
    address: str = Field(description="주소 (구체적인 상세 주소)")
    contact: str = Field(description="연락처")

    # 상차지 정보 (선택, 기본값: 유진알루미늄)
    loading_site: str = Field(default="유진알루미늄", description="상차지")
    loading_address: Optional[str] = Field(None, description="상차지 주소 (선택)")
    loading_phone: Optional[str] = Field(None, description="상차지 전화번호 (선택)")

    # 운송비 정보
    payment_type: Literal["착불", "선불"] = Field(description="운송비 지불 방법: 착불 또는 선불")
    freight_cost: Optional[int] = Field(None, description="운송비 (착불일 경우에만 입력, 원 단위)")

    # 메타데이터
    confidence: Optional[float] = Field(None, description="파싱 신뢰도 (0.0~1.0)")
    notes: Optional[str] = Field(None, description="추가 메모")


class ProductOrderInfo(BaseModel):
    """거래명세서 정보"""
    client: str = Field(description="거래처 (예: (주)삼성전자)")
    product_name: str = Field(description="품목")
    quantity: int = Field(description="수량")
    unit_price: int = Field(description="단가 (원 단위)")
    confidence: Optional[float] = Field(None, description="파싱 신뢰도 (0.0~1.0)")
    notes: Optional[str] = Field(None, description="추가 메모")


class AluminumCalculationInfo(BaseModel):
    """알루미늄 단가 계산 정보"""
    product_type: Literal["square_pipe", "round_pipe", "angle", "flat_bar", "round_bar", "channel"] = Field(
        description="제품 형상"
    )
    length_m: float = Field(description="길이 (m 단위)")
    
    # 형상별 치수
    width: Optional[float] = Field(None, description="폭 (mm)")
    height: Optional[float] = Field(None, description="높이 (mm)")
    thickness: Optional[float] = Field(None, description="두께 (mm)")
    diameter: Optional[float] = Field(None, description="지름 (mm)")
    width_a: Optional[float] = Field(None, description="앵글 폭 A (mm)")
    width_b: Optional[float] = Field(None, description="앵글 폭 B (mm)")
    channel_height: Optional[float] = Field(None, description="찬넬 웹 높이 (mm)")
    channel_width: Optional[float] = Field(None, description="찬넬 플랜지 폭 (mm)")
    
    # 필수 정보
    quantity: int = Field(description="수량")
    density: float = Field(description="비중")

    # 선택 정보
    price_per_kg: Optional[int] = Field(None, description="kg당 단가 (선택, 없으면 중량만 계산)")
    
    confidence: Optional[float] = Field(None, description="파싱 신뢰도 (0.0~1.0)")
    notes: Optional[str] = Field(None, description="추가 메모")
