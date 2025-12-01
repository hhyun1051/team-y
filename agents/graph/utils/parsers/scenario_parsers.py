"""
Scenario-specific parsers for Office Automation

시나리오별 전문 파서:
- DeliveryParser: 배송 정보 파싱
- ProductOrderParser: 제품 주문 정보 파싱
- AluminumCalculationParser: 알루미늄 단가 계산 정보 파싱
"""

from typing import Tuple
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from agents.graph.state import DeliveryInfo, ProductOrderInfo, AluminumCalculationInfo


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


class AluminumCalculationParser:
    """알루미늄 단가 계산 정보 파서 (시나리오 3)"""

    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.0):
        """
        AluminumCalculationParser 초기화

        Args:
            model_name: 사용할 LLM 모델
            temperature: 모델 temperature
        """
        system_prompt = """당신은 알루미늄 제품 계산 정보 파싱 전문가입니다.

사용자 입력에서 다음 정보를 추출하세요:

**필수 필드:**
- product_type: 제품 형상 ("square_pipe", "round_pipe", "angle", "flat_bar", "round_bar", "channel" 중 하나)
- length_m: 길이 (m 단위, 소수점 가능)

**형상별 치수 (product_type에 따라 필수):**
1. square_pipe (사각파이프):
   - width: 폭 (mm)
   - height: 높이 (mm)
   - thickness: 두께 (mm)

2. round_pipe (원파이프):
   - diameter: 외경 (mm)
   - thickness: 두께 (mm)

3. angle (앵글):
   - width_a: 폭 A (mm)
   - width_b: 폭 B (mm)
   - thickness: 두께 (mm)

4. flat_bar (평철):
   - width: 폭 (mm)
   - thickness: 두께 (mm)

5. round_bar (환봉):
   - diameter: 지름 (mm)

6. channel (찬넬):
   - channel_height: 웹 높이 (mm)
   - channel_width: 플랜지 폭 (mm)
   - thickness: 두께 (mm)

**선택 필드:**
- quantity: 수량 (개, 기본값: 1)
- density: 비중 (g/cm³, 기본값: 2.8)
- price_per_kg: kg당 단가 (원, 기본값: 6000)

**파싱 규칙:**
1. 형상 키워드 인식:
   - "사각파이프", "사각", "각파이프" → square_pipe
   - "원파이프", "원", "둥근파이프" → round_pipe
   - "앵글", "ㄱ자", "L형" → angle
   - "평철", "평판" → flat_bar
   - "환봉", "둥근봉", "원봉" → round_bar
   - "찬넬", "C형강", "채널" → channel

2. 치수 표기 인식:
   - "40x40x2t" → width=40, height=40, thickness=2
   - "50x2t" → diameter=50, thickness=2
   - "Ø20" → diameter=20
   - "100x5t" → width=100, thickness=5

3. 길이 단위:
   - "3m", "3M" → 3.0
   - "2.5m" → 2.5

4. 수량:
   - "5개", "/5개", "x5" → quantity=5
   - 명시 없으면 quantity=1

5. 단가 정보:
   - "비중 2.8" → density=2.8
   - "kg당 7000원" → price_per_kg=7000
   - 명시 없으면 기본값 사용

**예시:**
- 입력: "사각파이프 40x40x2t - 3m / 5개"
  → product_type="square_pipe", width=40, height=40, thickness=2, length_m=3, quantity=5

- 입력: "원 파이프 50x2t - 5m, 비중 2.8, kg당 6300원"
  → product_type="round_pipe", diameter=50, thickness=2, length_m=5, density=2.8, price_per_kg=6300

- 입력: "앵글 40x40x3 - 3m, kg당 7000원"
  → product_type="angle", width_a=40, width_b=40, thickness=3, length_m=3, price_per_kg=7000

**신뢰도 판단:**
- 형상과 모든 필수 치수 명확: 1.0
- 일부 치수 불명확: 0.7~0.9
- 형상이나 치수 추측 필요: 0.5 이하
"""

        self.agent = create_agent(
            model=f"openai:{model_name}",
            tools=[],
            system_prompt=system_prompt,
            response_format=ToolStrategy(AluminumCalculationInfo),
        )

    def parse(self, text: str) -> AluminumCalculationInfo:
        """
        알루미늄 계산 정보 파싱

        Args:
            text: 파싱할 텍스트

        Returns:
            AluminumCalculationInfo: 파싱된 알루미늄 계산 정보
        """
        result = self.agent.invoke({
            "messages": [{"role": "user", "content": text}]
        })

        return result["structured_response"]

    def parse_with_validation(self, text: str) -> Tuple[AluminumCalculationInfo, bool, str]:
        """
        파싱 + 검증

        Args:
            text: 파싱할 텍스트

        Returns:
            (AluminumCalculationInfo, is_valid, error_message)
        """
        try:
            calc_info = self.parse(text)

            # 필수 필드 검증
            if not calc_info.product_type:
                return calc_info, False, "제품 형상이 누락되었습니다."
            if not calc_info.length_m or calc_info.length_m <= 0:
                return calc_info, False, "길이가 누락되었습니다."

            # 형상별 치수 검증
            if calc_info.product_type == "square_pipe":
                if not calc_info.width or not calc_info.height or not calc_info.thickness:
                    return calc_info, False, "사각파이프 치수(폭, 높이, 두께)가 누락되었습니다."
            elif calc_info.product_type == "round_pipe":
                if not calc_info.diameter or not calc_info.thickness:
                    return calc_info, False, "원파이프 치수(외경, 두께)가 누락되었습니다."
            elif calc_info.product_type == "angle":
                if not calc_info.width_a or not calc_info.width_b or not calc_info.thickness:
                    return calc_info, False, "앵글 치수(폭A, 폭B, 두께)가 누락되었습니다."
            elif calc_info.product_type == "flat_bar":
                if not calc_info.width or not calc_info.thickness:
                    return calc_info, False, "평철 치수(폭, 두께)가 누락되었습니다."
            elif calc_info.product_type == "round_bar":
                if not calc_info.diameter:
                    return calc_info, False, "환봉 치수(지름)가 누락되었습니다."
            elif calc_info.product_type == "channel":
                if not calc_info.channel_height or not calc_info.channel_width or not calc_info.thickness:
                    return calc_info, False, "찬넬 치수(웹 높이, 플랜지 폭, 두께)가 누락되었습니다."

            # 신뢰도 검증
            if calc_info.confidence and calc_info.confidence < 0.5:
                return calc_info, False, f"파싱 신뢰도가 낮습니다 ({calc_info.confidence:.1%})"

            return calc_info, True, ""

        except Exception as e:
            return None, False, f"파싱 오류: {str(e)}"