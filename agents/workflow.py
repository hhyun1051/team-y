"""
Office Automation Workflow

HumanInTheLoopMiddleware를 사용하는 Agent 기반 워크플로우
"""

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

# Langfuse 통합
from langfuse import get_client
from langfuse.langchain import CallbackHandler

# Local imports
from .intent_classifier import IntentClassifier
from .parsers import DeliveryParser, ProductOrderParser
from .document_generator import DocumentGenerator
from .tools import (
    request_approval_delivery,
    request_approval_product,
    generate_delivery_document,
    generate_product_document,
)


class OfficeAutomationGraph:
    """사무 자동화 Agent (HITL 미들웨어 사용)"""

    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.0,
        use_langfuse: bool = True,
    ):
        """
        OfficeAutomationGraph 초기화

        Args:
            model_name: 사용할 LLM 모델
            temperature: 모델 temperature
            use_langfuse: Langfuse 로깅 사용 여부
        """
        print(f"[🤖] Initializing Office Automation Agent with HITL...")

        # 환경 변수 로드
        load_dotenv()

        self.model_name = model_name
        self.temperature = temperature
        self.use_langfuse = use_langfuse

        # Langfuse 초기화
        self._init_langfuse()

        # Parser 초기화
        self.intent_classifier = IntentClassifier(model_name=model_name, temperature=temperature)
        self.delivery_parser = DeliveryParser(model_name=model_name, temperature=temperature)
        self.product_parser = ProductOrderParser(model_name=model_name, temperature=temperature)

        # 체크포인터 (메모리 저장)
        self.checkpointer = MemorySaver()

        # HITL 미들웨어 설정 (정보 확인만 승인, 문서 생성은 자동)
        hitl_middleware = HumanInTheLoopMiddleware(
            interrupt_on={
                "request_approval_delivery": True,  # 운송장 정보 승인
                "request_approval_product": True,  # 거래명세서 정보 승인
            },
            description_prefix="승인이 필요합니다",
        )

        # System prompt
        system_prompt = """당신은 사무 자동화 전문가입니다.

사용자가 입력한 텍스트에서 정보를 추출하고, 사용자 승인을 받은 후 자동으로 문서를 생성합니다.

**워크플로우:**

1. **정보 승인 요청**
   - 사용자가 지시한 대로 정확히 `request_approval_delivery` 또는 `request_approval_product` tool을 호출하세요
   - tool 호출 시 parsed_info 파라미터에 포맷팅된 정보를 전달하세요
   - tool 호출 후 "승인을 기다립니다"라고만 응답하세요

2. **승인 후 문서 자동 생성 (매우 중요!)**
   - 승인 도구의 응답을 받으면 IMMEDIATELY(즉시) 문서 생성 도구를 호출해야 합니다
   - `generate_delivery_document` 또는 `generate_product_document` tool을 사용자가 지시한 파라미터로 정확히 호출하세요
   - 추가 승인이나 대기 없이 바로 문서를 생성하세요
   - 문서 생성 tool의 응답을 그대로 사용자에게 전달하세요

**중요 규칙:**
- 승인 tool 응답 후 반드시 문서 생성 tool을 호출하세요 (필수!)
- 사용자의 지시사항에 있는 파라미터를 정확히 사용하세요
- 승인을 기다리거나 추가 확인을 요청하지 마세요
"""

        # Agent 생성
        self.agent = create_agent(
            model=f"openai:{model_name}",
            tools=[
                request_approval_delivery,
                request_approval_product,
                generate_delivery_document,
                generate_product_document,
            ],
            system_prompt=system_prompt,
            middleware=[hitl_middleware],
            checkpointer=self.checkpointer,
        )

        print(f"[✅] Office Automation Agent initialized successfully")

    def _init_langfuse(self):
        """Langfuse 초기화"""
        if not self.use_langfuse:
            self.langfuse_client = None
            return

        try:
            # Langfuse v3: singleton client 사용
            self.langfuse_client = get_client()
            print(f"[✅] Langfuse initialized: {os.getenv('LANGFUSE_BASE_URL', 'default')}")
        except Exception as e:
            print(f"[⚠️] Langfuse initialization failed: {e}")
            self.langfuse_client = None

    def _format_parsed_info(self, parsed) -> str:
        """파싱된 정보를 승인 메시지로 포맷팅"""
        lines = []

        # 시나리오 1: 배송 정보
        if parsed.name or parsed.phone or parsed.address:
            lines.append("**배송 정보:**")
            if parsed.name:
                lines.append(f"- 이름: {parsed.name}")
            if parsed.phone:
                lines.append(f"- 전화번호: {parsed.phone}")
            if parsed.address:
                lines.append(f"- 주소: {parsed.address}")

        # 시나리오 2: 제품 주문
        if parsed.product_type or parsed.specifications or parsed.quantity:
            lines.append("**제품 주문 정보:**")
            if parsed.product_type:
                lines.append(f"- 제품 종류: {parsed.product_type}")
            if parsed.specifications:
                lines.append(f"- 제원: {parsed.specifications}")
            if parsed.quantity:
                lines.append(f"- 수량: {parsed.quantity}개")

        # 신뢰도
        if parsed.confidence is not None:
            lines.append(f"\n신뢰도: {parsed.confidence * 100:.0f}%")

        return "\n".join(lines)

    def invoke(
        self,
        raw_input: str,
        input_type: str = "text",
        discord_user_id: Optional[str] = None,
        discord_channel_id: Optional[str] = None,
        thread_id: str = "default",
    ) -> Dict[str, Any]:
        """
        워크플로우 실행

        Args:
            raw_input: 입력 텍스트 (원본 또는 음성 변환)
            input_type: 입력 타입 ("text" 또는 "voice")
            discord_user_id: 디스코드 사용자 ID
            discord_channel_id: 디스코드 채널 ID
            thread_id: 스레드 ID (대화 세션 식별)

        Returns:
            Agent 실행 결과 (interrupt 발생 시 __interrupt__ 포함)
        """
        print(f"[🔍] Classifying intent: {raw_input[:50]}...")

        # 1단계: 의도 분류
        intent = self.intent_classifier.classify(raw_input)
        print(f"[🎯] Intent classification: {intent.scenario} (confidence: {intent.confidence:.2f})")

        # 2단계: 시나리오별 처리
        if intent.scenario == "help":
            # 도움말 시나리오 - 파싱 없이 바로 응답
            print(f"[ℹ️] Help scenario detected")
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

            return {
                "status": "help",
                "messages": [{"role": "assistant", "content": help_message}]
            }

        elif intent.scenario == "delivery":
            print(f"[📦] Parsing delivery info...")
            parsed_info, is_valid, error_msg = self.delivery_parser.parse_with_validation(raw_input)
            scenario = "delivery"

            if is_valid:
                formatted_info = f"""**운송장 정보:**
- 이름: {parsed_info.name}
- 전화번호: {parsed_info.phone}
- 주소: {parsed_info.address}
"""
                if parsed_info.confidence:
                    formatted_info += f"\n신뢰도: {parsed_info.confidence * 100:.0f}%"

        elif intent.scenario == "product_order":
            print(f"[🏭] Parsing product order info...")
            parsed_info, is_valid, error_msg = self.product_parser.parse_with_validation(raw_input)
            scenario = "product_order"

            if is_valid:
                total_price = parsed_info.quantity * parsed_info.unit_price
                formatted_info = f"""**거래명세서 정보:**
- 거래처: {parsed_info.client}
- 품목: {parsed_info.product_name}
- 수량: {parsed_info.quantity}개
- 단가: {parsed_info.unit_price:,}원
- 합계: {total_price:,}원
"""
                if parsed_info.notes:
                    formatted_info += f"- 참고: {parsed_info.notes}\n"
                if parsed_info.confidence:
                    formatted_info += f"\n신뢰도: {parsed_info.confidence * 100:.0f}%"

        else:
            return {
                "status": "error",
                "error": f"알 수 없는 시나리오: {intent.scenario}",
                "messages": [{"role": "assistant", "content": f"❌ 시나리오 분류 실패: {intent.scenario}"}]
            }

        # 파싱 실패 처리 - 재요청
        if not is_valid:
            if scenario == "delivery":
                retry_message = f"""❌ 필수 정보가 누락되었습니다: {error_msg}

다음 정보를 모두 포함하여 다시 입력해주세요:
- 이름 (수령인)
- 전화번호 (010-XXXX-XXXX 형식)
- 주소 (상세주소 포함)

**예시:** 홍길동 010-1234-5678 서울시 강남구 테헤란로 123"""
            else:  # product_order
                retry_message = f"""❌ 필수 정보가 누락되었습니다: {error_msg}

다음 정보를 모두 포함하여 다시 입력해주세요:
- 거래처 (예: (주)삼성전자)
- 품목 (제품명)
- 수량 (숫자)
- 단가 (원 단위)

**예시:** 거래처 (주)삼성전자, 알루미늄 원파이프, 6개, 개당 50000원"""

            return {
                "status": "retry",
                "error": error_msg,
                "messages": [{"role": "assistant", "content": retry_message}]
            }

        # Langfuse CallbackHandler 생성
        callbacks = []
        if self.langfuse_client:
            try:
                langfuse_handler = CallbackHandler()
                callbacks = [langfuse_handler]
            except Exception as e:
                print(f"[⚠️] Failed to create Langfuse handler: {e}")

        config = {
            "configurable": {"thread_id": thread_id},
            "callbacks": callbacks,
            "metadata": {
                "langfuse_session_id": thread_id,
                "langfuse_user_id": discord_user_id or "unknown",
                "langfuse_tags": ["office-automation", input_type],
            }
        }

        # 3단계: Agent에게 시나리오별 승인 요청 및 문서 생성 지시
        if scenario == "delivery":
            user_message = f"""시나리오: delivery (운송장)

다음 정보를 파싱했습니다:
{formatted_info}

**지시사항:**
먼저 `request_approval_delivery` tool을 호출하여 승인을 요청하세요.
승인 후 즉시 `generate_delivery_document` tool을 호출하세요 (이름={parsed_info.name}, 전화번호={parsed_info.phone}, 주소={parsed_info.address})"""
        else:  # product_order
            user_message = f"""시나리오: product_order (거래명세서)

다음 정보를 파싱했습니다:
{formatted_info}

**지시사항:**
먼저 `request_approval_product` tool을 호출하여 승인을 요청하세요.
승인 후 즉시 `generate_product_document` tool을 호출하세요 (거래처={parsed_info.client}, 품목={parsed_info.product_name}, 수량={parsed_info.quantity}, 단가={parsed_info.unit_price})"""

        print(f"[📤] Invoking agent with scenario: {scenario}...")
        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": user_message}]},
            config
        )

        return result

    def get_state(self, thread_id: str = "default") -> Optional[Dict[str, Any]]:
        """
        특정 스레드의 현재 상태 조회

        Args:
            thread_id: 스레드 ID

        Returns:
            현재 상태 또는 None
        """
        config = {"configurable": {"thread_id": thread_id}}
        try:
            state = self.agent.get_state(config)
            return state.values if state else None
        except Exception as e:
            print(f"[⚠️] Failed to get state: {e}")
            return None

    def resume(
        self,
        decision_type: str,
        edited_args: Optional[Dict[str, Any]] = None,
        reject_message: Optional[str] = None,
        thread_id: str = "default",
    ) -> Dict[str, Any]:
        """
        HITL 승인 후 워크플로우 재개

        Args:
            decision_type: "approve", "edit", "reject"
            edited_args: edit인 경우 수정된 args
            reject_message: reject인 경우 거절 메시지
            thread_id: 스레드 ID

        Returns:
            Agent 실행 결과
        """
        from langgraph.types import Command

        config = {"configurable": {"thread_id": thread_id}}

        # 결정 타입에 따라 Command 생성
        if decision_type == "approve":
            print(f"[✅] Resuming with approval...")
            resume_data = Command(
                resume={"decisions": [{"type": "approve"}]}
            )
        elif decision_type == "edit":
            print(f"[✏️] Resuming with edits: {edited_args}")
            resume_data = Command(
                resume={
                    "decisions": [{
                        "type": "edit",
                        "edited_action": {
                            "name": "request_approval",
                            "args": edited_args or {}
                        }
                    }]
                }
            )
        elif decision_type == "reject":
            print(f"[❌] Resuming with rejection: {reject_message}")
            resume_data = Command(
                resume={
                    "decisions": [{
                        "type": "reject",
                        "message": reject_message or "사용자가 거절했습니다."
                    }]
                }
            )
        else:
            raise ValueError(f"Invalid decision_type: {decision_type}")

        # Agent 재개
        result = self.agent.invoke(resume_data, config)
        return result
