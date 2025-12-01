"""
LangGraph Node Functions

워크플로우의 각 단계를 처리하는 노드 함수들
"""

from typing import Dict, Any, Optional, Tuple
from .state import (
    OfficeAutomationState,
    IntentClassification,
    DeliveryInfo,
    ProductOrderInfo,
)
from .utils.intent_classifier import IntentClassifier
from .utils.parsers import DeliveryParser, ProductOrderParser
from .utils.document_generator import DocumentGenerator


def classify_intent_node(
    state: OfficeAutomationState,
    intent_classifier: IntentClassifier
) -> Dict[str, Any]:
    """
    의도 분류 노드

    사용자 입력을 분석하여 시나리오를 분류합니다.

    Args:
        state: 현재 상태
        intent_classifier: 의도 분류기

    Returns:
        업데이트된 상태
    """
    raw_input = state.get("raw_input", "")
    print(f"[🔍] Classifying intent: {raw_input[:50]}...")

    intent = intent_classifier.classify(raw_input)
    print(f"[🎯] Intent: {intent.scenario} (confidence: {intent.confidence:.2f})")

    return {
        "intent": intent,
        "current_scenario": intent.scenario,
    }


def parse_delivery_info_node(
    state: OfficeAutomationState,
    delivery_parser: DeliveryParser
) -> Dict[str, Any]:
    """
    배송 정보 파싱 노드

    Args:
        state: 현재 상태
        delivery_parser: 배송 정보 파서

    Returns:
        업데이트된 상태
    """
    raw_input = state.get("raw_input", "")
    print(f"[📦] Parsing delivery info...")

    parsed_info, is_valid, error_msg = delivery_parser.parse_with_validation(raw_input)

    result = {
        "delivery_info": parsed_info if is_valid else None,
        "parsing_error": error_msg if not is_valid else None,
    }

    if is_valid:
        print(f"[✅] Delivery info parsed: {parsed_info.unloading_site}, {parsed_info.contact}")
    else:
        print(f"[❌] Parsing failed: {error_msg}")

    return result


def parse_product_order_node(
    state: OfficeAutomationState,
    product_parser: ProductOrderParser
) -> Dict[str, Any]:
    """
    제품 주문 정보 파싱 노드

    Args:
        state: 현재 상태
        product_parser: 제품 주문 파서

    Returns:
        업데이트된 상태
    """
    raw_input = state.get("raw_input", "")
    print(f"[🏭] Parsing product order info...")

    parsed_info, is_valid, error_msg = product_parser.parse_with_validation(raw_input)

    result = {
        "product_order_info": parsed_info if is_valid else None,
        "parsing_error": error_msg if not is_valid else None,
    }

    if is_valid:
        print(f"[✅] Product order parsed: {parsed_info.client}, {parsed_info.product_name}")
    else:
        print(f"[❌] Parsing failed: {error_msg}")

    return result


def format_approval_message_node(state: OfficeAutomationState) -> Dict[str, Any]:
    """
    승인 메시지 포맷팅 노드

    파싱된 정보를 사용자에게 보여줄 형식으로 변환합니다.

    Args:
        state: 현재 상태

    Returns:
        업데이트된 상태 (approval_message 포함)
    """
    scenario = state.get("current_scenario")

    if scenario == "delivery":
        delivery_info = state.get("delivery_info")
        if delivery_info:
            formatted_info = f"""**운송장 정보:**

【하차지 정보】
- 하차지: {delivery_info.unloading_site}
- 주소: {delivery_info.address}
- 연락처: {delivery_info.contact}

【상차지 정보】
- 상차지: {delivery_info.loading_site}"""
            if delivery_info.loading_address:
                formatted_info += f"\n- 상차지 주소: {delivery_info.loading_address}"
            if delivery_info.loading_phone:
                formatted_info += f"\n- 상차지 전화번호: {delivery_info.loading_phone}"

            formatted_info += f"\n\n【운송비】\n- 지불방법: {delivery_info.payment_type}"
            if delivery_info.freight_cost:
                formatted_info += f"\n- 운송비: {delivery_info.freight_cost:,}원"

            if delivery_info.notes:
                formatted_info += f"\n\n- 참고: {delivery_info.notes}"
            if delivery_info.confidence:
                formatted_info += f"\n\n신뢰도: {delivery_info.confidence * 100:.0f}%"

            return {"approval_message": formatted_info}

    elif scenario == "product_order":
        product_info = state.get("product_order_info")
        if product_info:
            total_price = product_info.quantity * product_info.unit_price
            formatted_info = f"""**거래명세서 정보:**
- 거래처: {product_info.client}
- 품목: {product_info.product_name}
- 수량: {product_info.quantity}개
- 단가: {product_info.unit_price:,}원
- 합계: {total_price:,}원
"""
            if product_info.notes:
                formatted_info += f"- 참고: {product_info.notes}\n"
            if product_info.confidence:
                formatted_info += f"\n신뢰도: {product_info.confidence * 100:.0f}%"

            return {"approval_message": formatted_info}

    return {"approval_message": "정보를 포맷팅할 수 없습니다."}


def generate_delivery_document_node(
    state: OfficeAutomationState
) -> Dict[str, Any]:
    """
    운송장 문서 생성 노드

    Args:
        state: 현재 상태

    Returns:
        업데이트된 상태 (생성된 문서 경로 포함)
    """
    delivery_info = state.get("delivery_info")

    if not delivery_info:
        return {
            "error": "배송 정보가 없습니다.",
            "document_path": None,
        }

    print(f"[📄] Generating delivery document...")

    try:
        result = DocumentGenerator.generate_delivery_document(
            delivery_info.name,
            delivery_info.phone,
            delivery_info.address
        )

        print(f"[✅] Document generated: {result['pdf']}")

        return {
            "document_path": result['pdf'],
            "docx_path": result['docx'],
        }
    except Exception as e:
        print(f"[❌] Document generation failed: {e}")
        return {
            "error": f"문서 생성 실패: {str(e)}",
            "document_path": None,
        }


def generate_product_document_node(
    state: OfficeAutomationState
) -> Dict[str, Any]:
    """
    거래명세서 문서 생성 노드

    Args:
        state: 현재 상태

    Returns:
        업데이트된 상태 (생성된 문서 경로 포함)
    """
    product_info = state.get("product_order_info")

    if not product_info:
        return {
            "error": "제품 주문 정보가 없습니다.",
            "document_path": None,
        }

    print(f"[📄] Generating product order document...")

    try:
        result = DocumentGenerator.generate_product_order_document(
            product_info.client,
            product_info.product_name,
            product_info.quantity,
            product_info.unit_price
        )

        print(f"[✅] Document generated: {result['pdf']}")

        return {
            "document_path": result['pdf'],
            "docx_path": result['docx'],
        }
    except Exception as e:
        print(f"[❌] Document generation failed: {e}")
        return {
            "error": f"문서 생성 실패: {str(e)}",
            "document_path": None,
        }


def generate_help_message_node(state: OfficeAutomationState) -> Dict[str, Any]:
    """
    도움말 메시지 생성 노드

    Args:
        state: 현재 상태

    Returns:
        업데이트된 상태 (도움말 메시지 포함)
    """
    help_message = """안녕하세요! 저는 사무 자동화 봇입니다. 👋

제가 도와드릴 수 있는 기능은 다음과 같습니다:

**1️⃣ 운송장 생성**
배송 정보를 입력하면 운송장 PDF를 자동으로 생성해드립니다.

필요한 정보:
- 수령인 이름
- 전화번호 (010-XXXX-XXXX 형식)
- 배송 주소 (상세주소 포함)

**입력 예시:**
`홍길동 010-1234-5678 서울시 강남구 테헤란로 123`

---

**2️⃣ 거래명세서 생성**
제품 주문 정보를 입력하면 거래명세서 PDF를 자동으로 생성해드립니다.

필요한 정보:
- 거래처 (예: (주)삼성전자)
- 품목 (제품명)
- 수량 (개수)
- 단가 (원 단위)

**입력 예시:**
`거래처 (주)삼성전자, 알루미늄 원파이프, 10개, 개당 50000원`

---

**📌 사용 방법:**
1. 위 정보를 입력하시면 자동으로 파싱됩니다
2. 확인 버튼(승인/거절/편집)이 표시됩니다
3. 승인하시면 문서가 생성됩니다
4. 생성된 PDF 파일을 받으실 수 있습니다

궁금하신 점이 있으시면 언제든지 물어보세요! 😊"""

    return {"help_message": help_message}


def generate_retry_message_node(state: OfficeAutomationState) -> Dict[str, Any]:
    """
    재시도 메시지 생성 노드

    파싱 실패 시 사용자에게 안내 메시지를 생성합니다.

    Args:
        state: 현재 상태

    Returns:
        업데이트된 상태 (재시도 메시지 포함)
    """
    scenario = state.get("current_scenario")
    error_msg = state.get("parsing_error", "알 수 없는 오류")

    if scenario == "delivery":
        retry_message = f"""❌ 필수 정보가 누락되었습니다: {error_msg}

다음 정보를 모두 포함하여 다시 입력해주세요:
- 이름 (수령인)
- 전화번호 (010-XXXX-XXXX 형식)
- 주소 (상세주소 포함)

**예시:** 홍길동 010-1234-5678 서울시 강남구 테헤란로 123"""

    elif scenario == "product_order":
        retry_message = f"""❌ 필수 정보가 누락되었습니다: {error_msg}

다음 정보를 모두 포함하여 다시 입력해주세요:
- 거래처 (예: (주)삼성전자)
- 품목 (제품명)
- 수량 (숫자)
- 단가 (원 단위)

**예시:** 거래처 (주)삼성전자, 알루미늄 원파이프, 6개, 개당 50000원"""

    else:
        retry_message = f"❌ 처리 중 오류가 발생했습니다: {error_msg}"

    return {"retry_message": retry_message}
