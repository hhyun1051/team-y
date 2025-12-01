"""
Scenario-specific parsers for Office Automation

시나리오별 전문 파서:
- DeliveryParser: 배송 정보 파싱
- ProductOrderParser: 제품 주문 정보 파싱
"""

from typing import Tuple
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from agents.graph.state import DeliveryInfo, ProductOrderInfo


class DeliveryParser:
    """배송 정보 파서 (시나리오 1)"""

    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.0):
        """
        DeliveryParser 초기화

        Args:
            model_name: 사용할 LLM 모델
            temperature: 모델 temperature
        """
        system_prompt = """당신은 운송장 정보 파싱 전문가입니다.

사용자 입력에서 다음 정보를 추출하세요:

**필수 필드 (하차지 정보):**
- unloading_site: 하차지 (회사 이름, 예: "삼성전자", "현대건설")
- address: 주소 (구체적인 상세 주소)
- contact: 연락처 (010-XXXX-XXXX 형식으로 정규화)

**선택 필드 (상차지 정보):**
- loading_site: 상차지 (기본값: "유진알루미늄")
- loading_address: 상차지 주소
- loading_phone: 상차지 전화번호

**운송비 정보:**
- payment_type: "착불" 또는 "선불" (기본값은 사용자 입력에서 유추)
- freight_cost: 운송비 (착불일 경우에만 입력, 원 단위 정수)

**파싱 규칙:**
1. 전화번호는 010-XXXX-XXXX 형식으로 하이픈 포함
2. 주소는 가능한 상세하게 (동/호수 포함)
3. 운송비는 "착불"이고 금액이 명시된 경우에만 freight_cost에 입력
4. "선불"인 경우 freight_cost는 None
5. 상차지가 명시되지 않으면 기본값 "유진알루미늄" 사용
6. 불명확한 부분은 notes에 기록

**신뢰도 판단:**
- 모든 필드가 명확: 1.0
- 일부 필드 불명확: 0.7~0.9
- 추측이 필요한 경우: 0.5 이하
"""

        self.agent = create_agent(
            model=f"openai:{model_name}",
            tools=[],
            system_prompt=system_prompt,
            response_format=ToolStrategy(DeliveryInfo),
        )

    def parse(self, text: str) -> DeliveryInfo:
        """
        배송 정보 파싱

        Args:
            text: 파싱할 텍스트

        Returns:
            DeliveryInfo: 파싱된 배송 정보
        """
        result = self.agent.invoke({
            "messages": [{"role": "user", "content": text}]
        })

        return result["structured_response"]

    def parse_with_validation(self, text: str) -> Tuple[DeliveryInfo, bool, str]:
        """
        파싱 + 검증

        Args:
            text: 파싱할 텍스트

        Returns:
            (DeliveryInfo, is_valid, error_message)
        """
        try:
            delivery_info = self.parse(text)

            # 필수 필드 검증 (하차지 정보)
            if not delivery_info.unloading_site:
                return delivery_info, False, "하차지가 누락되었습니다."
            if not delivery_info.address:
                return delivery_info, False, "주소가 누락되었습니다."
            if not delivery_info.contact:
                return delivery_info, False, "연락처가 누락되었습니다."

            # payment_type 검증
            if not delivery_info.payment_type:
                return delivery_info, False, "운송비 지불 방법(착불/선불)이 누락되었습니다."

            # 신뢰도 검증
            if delivery_info.confidence and delivery_info.confidence < 0.5:
                return delivery_info, False, f"파싱 신뢰도가 낮습니다 ({delivery_info.confidence:.1%})"

            return delivery_info, True, ""

        except Exception as e:
            return None, False, f"파싱 오류: {str(e)}"


class ProductOrderParser:
    """제품 주문 정보 파서 (시나리오 2)"""

    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.0):
        """
        ProductOrderParser 초기화

        Args:
            model_name: 사용할 LLM 모델
            temperature: 모델 temperature
        """
        system_prompt = """당신은 제품 주문 정보 파싱 전문가입니다.

사용자 입력에서 다음 정보를 추출하세요:

**필수 필드:**
- client: 거래처 (예: "(주)삼성전자", "현대중공업", "LG화학")
- product_name: 품목 (예: "알루미늄 원파이프", "스테인리스 각파이프")
- quantity: 수량 (정수)
- unit_price: 단가 (원 단위, 정수)

**파싱 규칙:**
1. 거래처명은 (주), 주식회사 등 법인 형태 포함
2. 품목은 재질 + 형태로 정리 (예: "알루미늄 원파이프")
3. 수량은 숫자만 추출 (단위 제거)
4. 단가는 원 단위로 변환 (천원 → 원)
5. 제원이나 규격 정보는 notes에 기록
6. 불명확한 부분은 notes에 기록

**예시:**
- 입력: "삼성전자에 알루미늄 원파이프 10개 개당 15000원, 400x400 40t"
- client: "(주)삼성전자"
- product_name: "알루미늄 원파이프"
- quantity: 10
- unit_price: 15000
- notes: "제원: 400x400 40t"

**신뢰도 판단:**
- 모든 필드가 명확: 1.0
- 일부 필드 불명확: 0.7~0.9
- 추측이 필요한 경우: 0.5 이하
"""

        self.agent = create_agent(
            model=f"openai:{model_name}",
            tools=[],
            system_prompt=system_prompt,
            response_format=ToolStrategy(ProductOrderInfo),
        )

    def parse(self, text: str) -> ProductOrderInfo:
        """
        제품 주문 정보 파싱

        Args:
            text: 파싱할 텍스트

        Returns:
            ProductOrderInfo: 파싱된 제품 주문 정보
        """
        result = self.agent.invoke({
            "messages": [{"role": "user", "content": text}]
        })

        return result["structured_response"]

    def parse_with_validation(self, text: str) -> Tuple[ProductOrderInfo, bool, str]:
        """
        파싱 + 검증

        Args:
            text: 파싱할 텍스트

        Returns:
            (ProductOrderInfo, is_valid, error_message)
        """
        try:
            order_info = self.parse(text)

            # 필수 필드 검증
            if not order_info.client:
                return order_info, False, "거래처가 누락되었습니다."
            if not order_info.product_name:
                return order_info, False, "품목이 누락되었습니다."
            if not order_info.quantity or order_info.quantity <= 0:
                return order_info, False, "올바른 수량이 누락되었습니다."
            if not order_info.unit_price or order_info.unit_price <= 0:
                return order_info, False, "올바른 단가가 누락되었습니다."

            # 신뢰도 검증
            if order_info.confidence and order_info.confidence < 0.5:
                return order_info, False, f"파싱 신뢰도가 낮습니다 ({order_info.confidence:.1%})"

            return order_info, True, ""

        except Exception as e:
            return None, False, f"파싱 오류: {str(e)}"
