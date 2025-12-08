"""
알루미늄 단가 계산 정보 파서

사용자 입력에서 알루미늄 제품 계산 정보를 추출합니다.
"""

from typing import Tuple, Optional
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from agents.graph.state import AluminumCalculationInfo


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

**🔴 핵심 필수 필드 (절대 누락 불가):**

1. **제품 형상 (product_type)** - 가장 중요!
   - "square_pipe", "round_pipe", "angle", "flat_bar", "round_bar", "channel" 중 하나
   - 형상 키워드: "원파이프", "사각파이프", "앵글", "평철", "환봉", "찬넬"

2. **제품 치수** - 형상에 따라 필수!
   - square_pipe: width(폭), height(높이), thickness(두께) - 예: "40x40x2t"
   - round_pipe: diameter(지름), thickness(두께) - 예: "50x2t", "Ø50x2t"
   - angle: width_a(폭A), width_b(폭B), thickness(두께) - 예: "40x40x3t"
   - flat_bar: width(폭), thickness(두께) - 예: "100x5t"
   - round_bar: diameter(지름) - 예: "Ø20"
   - channel: channel_width(플랜지폭), channel_height(웹높이), thickness(두께)

3. **길이 (length_m)** - 필수!
   - m 단위, 소수점 가능
   - 예: "3m", "2.5m", "6M"
   - 명시 없으면 에러

4. **수량 (quantity)** - 필수!
   - 개수 (정수)
   - 예: "5개", "10개", "1개"
   - 명시 없으면 에러

5. **비중 (density)** - 필수!
   - g/cm³ 단위
   - 예: "비중 2.8", "2.7"
   - 명시 없으면 에러

6. **kg당 단가 (price_per_kg)** - 선택!
   - 원 단위
   - 예: "kg당 6000원", "단가 7000"
   - 명시 없으면 None (중량만 계산)

**⚠️ 중요 파싱 규칙:**

1. **절대 기본값 사용 금지!**
   - 형상, 치수, 길이, 수량, 비중이 명시되지 않은 경우
   - 절대 추측하거나 기본값(1, 2.8 등) 사용 금지
   - 누락된 필수 필드는 None 또는 0으로 설정하여 validation 에러 발생시킴
   - kg당 단가는 선택 사항이므로 없으면 None으로 설정 (에러 아님)

2. **형상 키워드 인식** (최우선!):
   - "원", "원파이프" → round_pipe
   - "사각", "사각파이프" → square_pipe
   - "앵글", "ㄱ자" → angle
   - "평철", "평판" → flat_bar
   - "환봉", "둥근봉" → round_bar
   - "찬넬", "채널" → channel

3. **치수 표기 인식** (최우선!):
   - "40x40x2t" → 사각: width=40, height=40, thickness=2
   - "50x2t" → 원: diameter=50, thickness=2
   - "Ø40x3t" → 원: diameter=40, thickness=3
   - "100x5t" → 평철: width=100, thickness=5

**파싱 예시:**

✅ 완벽한 예시 (가격 계산):
- "원 지름40 두께3 길이3m 수량5개 비중2.8 단가6000"
  → product_type="round_pipe", diameter=40, thickness=3, length_m=3, quantity=5, density=2.8, price_per_kg=6000

- "사각파이프 40x40x2t - 3m / 5개, 비중 2.8, kg당 6000원"
  → product_type="square_pipe", width=40, height=40, thickness=2, length_m=3, quantity=5, density=2.8, price_per_kg=6000

✅ 중량만 계산 (단가 없음):
- "원 지름40 두께3 길이3m 수량5개 비중2.8"
  → product_type="round_pipe", diameter=40, thickness=3, length_m=3, quantity=5, density=2.8, price_per_kg=None

❌ 불완전한 예시 (에러 발생시켜야 함):
- "원 지름40 두께3 비중2.8" → length_m=None, quantity=None (에러!)
- "사각 40x40x2t 3m" → quantity=None, density=None (에러!)

**신뢰도 판단:**
- 형상, 치수, 모든 필수 필드 명확: 1.0
- 일부 필드만 명확: 0.5 이하 (validation에서 에러 발생)
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

    def parse_with_validation(self, text: str, messages: Optional[list] = None) -> Tuple[AluminumCalculationInfo, bool, str]:
        """
        파싱 + 검증 (멀티턴 지원)

        Args:
            text: 현재 입력 텍스트
            messages: 전체 메시지 히스토리 (멀티턴 대화용)

        Returns:
            (AluminumCalculationInfo, is_valid, error_message)
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
                    calc_info = self.parse(combined_text)
                else:
                    # HumanMessage가 없으면 현재 텍스트만 파싱
                    calc_info = self.parse(text)
            else:
                # messages가 없으면 현재 텍스트만 파싱 (단일턴)
                calc_info = self.parse(text)

            # 필수 필드 검증
            if not calc_info.product_type:
                return calc_info, False, "제품 형상이 누락되었습니다."
            if not calc_info.length_m or calc_info.length_m <= 0:
                return calc_info, False, "길이가 누락되었습니다."

            # 필수 필드 검증 (수량, 비중)
            if not calc_info.quantity or calc_info.quantity <= 0:
                return calc_info, False, "수량이 누락되었습니다."
            if not calc_info.density or calc_info.density <= 0:
                return calc_info, False, "비중이 누락되었습니다."
            # price_per_kg는 선택 사항이므로 검증하지 않음

            # 형상별 치수 검증
            if calc_info.product_type == "square_pipe":
                if not calc_info.width or not calc_info.height or not calc_info.thickness:
                    return calc_info, False, "사각파이프 치수(폭, 높이, 두께)가 누락되었습니다."
            elif calc_info.product_type == "round_pipe":
                if not calc_info.diameter or not calc_info.thickness:
                    return calc_info, False, "원파이프 치수(지름, 두께)가 누락되었습니다."
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
