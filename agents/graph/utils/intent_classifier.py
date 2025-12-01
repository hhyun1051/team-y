"""
Intent Classification for Office Automation

사용자 입력을 분석하여 시나리오를 분류합니다:
- delivery: 배송 정보 (이름, 전화번호, 주소)
- product_order: 제품 주문 (제품 종류, 제원, 수량)
"""

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from agents.graph.state import IntentClassification


class IntentClassifier:
    """의도 분류기"""

    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.0):
        """
        IntentClassifier 초기화

        Args:
            model_name: 사용할 LLM 모델
            temperature: 모델 temperature
        """
        system_prompt = """당신은 사무 자동화 시스템의 의도 분류 전문가입니다.

사용자 입력을 분석하여 다음 세 가지 시나리오 중 하나로 분류하세요:

**시나리오 1 - delivery (운송장):**
- 이름, 전화번호, 주소 정보가 포함된 경우
- 예시: "홍길동, 010-1234-5678, 서울시 강남구 테헤란로 123"
- 예시: "김철수님에게 부산 해운대구로 보내주세요. 전화는 010-9999-8888"

**시나리오 2 - product_order (거래명세서):**
- 거래처, 제품명, 수량, 단가 정보가 포함된 경우
- 예시: "(주)삼성전자, 알루미늄 원파이프 400x400에 40t 10개, 개당 50000원"
- 예시: "거래처 현대중공업, 스테인리스 각파이프 5개, 단가 15000원"

**시나리오 3 - help (도움말/기타):**
- 도움말, 사용법, 기능 설명 요청
- 인사, 잡담, 운송장/거래명세서와 무관한 내용
- 예시: "뭐 할 수 있어?", "안녕", "사용법 알려줘", "기능이 뭐야?"
- 예시: "도와줘", "help", "어떻게 써?", "설명해줘"

**분류 기준:**
1. 이름이나 수령인 정보가 있으면 → delivery
2. 거래처, 제품명, 수량, 단가가 있으면 → product_order
3. 도움말 요청, 기능 설명, 인사, 기타 → help
4. 불명확한 경우 문맥과 키워드로 판단

**신뢰도:**
- 명확한 경우: 0.9 이상
- 애매한 경우: 0.5~0.8
- 매우 불확실: 0.5 미만
"""

        # Agent 생성 (ToolStrategy 사용)
        self.agent = create_agent(
            model=f"openai:{model_name}",
            tools=[],
            system_prompt=system_prompt,
            response_format=ToolStrategy(IntentClassification),
        )

    def classify(self, text: str) -> IntentClassification:
        """
        텍스트를 분석하여 시나리오 분류

        Args:
            text: 분석할 텍스트

        Returns:
            IntentClassification: 분류 결과
        """
        result = self.agent.invoke({
            "messages": [{"role": "user", "content": f"다음 텍스트를 분류하세요:\n\n{text}"}]
        })

        return result["structured_response"]
