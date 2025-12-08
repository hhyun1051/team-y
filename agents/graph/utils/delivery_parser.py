"""
배송 정보 파서

사용자 입력에서 배송 정보를 추출합니다.
"""

from typing import Tuple, Optional
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from agents.graph.state import DeliveryInfo


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
2. **주소에 포함할 것 (중요!):**
   - 도로명/지번 주소
   - 건물명, 동/호수
   - **위치 표시는 반드시 주소에 포함**: "○○건물 옆", "○○금속 오른쪽/왼쪽/앞/뒤", "1층 현관" 등
   - 예: "경기도 김포시 통진읍 김포대로 1938번길 48-1,48-2,48-3,48-4 기흥금속 오른쪽"
3. 운송비는 "착불"이고 금액이 명시된 경우에만 freight_cost에 입력
4. "선불"인 경우 freight_cost는 None
5. 상차지가 명시되지 않으면 기본값 "유진알루미늄" 사용
6. **비고(notes)에만 포함할 것:**
   - **시간 지시사항**: "오후3시전도착", "오전배송", "저녁배송", "오전중", "오후중" 등
   - 특별 요청: "급함", "조심히", "깨지기쉬움" 등
   - **절대 위치 정보를 비고에 넣지 마세요 - 위치는 무조건 주소에 포함**
7. **파싱 과정에서의 불명확함이나 추측은 notes에 기록하지 마세요**

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

    def parse_with_validation(self, text: str, messages: Optional[list] = None) -> Tuple[DeliveryInfo, bool, str]:
        """
        파싱 + 검증 (멀티턴 지원)

        Args:
            text: 현재 입력 텍스트
            messages: 전체 메시지 히스토리 (멀티턴 대화용)

        Returns:
            (DeliveryInfo, is_valid, error_message)
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
                    delivery_info = self.parse(combined_text)
                else:
                    # HumanMessage가 없으면 현재 텍스트만 파싱
                    delivery_info = self.parse(text)
            else:
                # messages가 없으면 현재 텍스트만 파싱 (단일턴)
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
