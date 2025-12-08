"""
제품 주문 정보 파서

사용자 입력에서 제품 주문 정보를 추출합니다.
"""

from typing import Tuple, Optional
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from agents.graph.state import ProductOrderInfo


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

    def parse_with_validation(self, text: str, messages: Optional[list] = None) -> Tuple[ProductOrderInfo, bool, str]:
        """
        파싱 + 검증 (멀티턴 지원)

        Args:
            text: 현재 입력 텍스트
            messages: 전체 메시지 히스토리 (멀티턴 대화용)

        Returns:
            (ProductOrderInfo, is_valid, error_message)
        """
        try:
            # 멀티턴 대화: 전체 메시지에서 HumanMessage만 추출하여 결합
            if messages:
                from langchain_core.messages import HumanMessage

                human_inputs = []
                for msg in messages:
                    if isinstance(msg, HumanMessage):
                        human_inputs.append(msg.content)

                # 모든 사용자 입력을 결합하여 파싱
                if human_inputs:
                    combined_text = " ".join(human_inputs)
                    print(f"[🔄] Multi-turn parsing: combining {len(human_inputs)} human messages")
                    print(f"[📝] Combined text: {combined_text}")
                    order_info = self.parse(combined_text)
                else:
                    # HumanMessage가 없으면 현재 텍스트만 파싱
                    order_info = self.parse(text)
            else:
                # messages가 없으면 현재 텍스트만 파싱 (단일턴)
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
