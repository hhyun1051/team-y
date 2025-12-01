"""
Office Automation Workflow - LangGraph StateGraph 기반

노드 기반 워크플로우:
1. classify_intent → 의도 분류
2. help / delivery_subgraph / product_subgraph / aluminum_subgraph → 시나리오별 처리
"""

import os
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage

# Langfuse 통합
from langfuse import get_client
from langfuse.langchain import CallbackHandler

# Local imports
from .state import OfficeAutomationState
from .utils.intent_classifier import IntentClassifier
from .utils.parsers import DeliveryParser, ProductOrderParser
from .utils.document_generator import DocumentGenerator
from .utils.tools.aluminum_calculator import (
    calculate_aluminum_price_square_pipe,
    calculate_aluminum_price_round_pipe,
    calculate_aluminum_price_angle,
    calculate_aluminum_price_flat_bar,
    calculate_aluminum_price_round_bar,
    calculate_aluminum_price_channel,
    calculate_price_from_weight_and_price_per_kg,
    calculate_price_per_kg_from_unit_price_and_weight,
)
from .subgraphs import create_delivery_subgraph, create_product_subgraph, create_aluminum_subgraph
from ..middleware import LangfuseToolLoggingMiddleware


class OfficeAutomationGraph:
    """사무 자동화 그래프 (LangGraph StateGraph 기반)"""

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
        print(f"[🤖] Initializing Office Automation Graph (StateGraph)...")

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

        # Middleware 설정 (AluminumSubGraph용)
        aluminum_middlewares = []
        if self.use_langfuse and self.langfuse_client:
            langfuse_middleware = LangfuseToolLoggingMiddleware(
                langfuse_client=self.langfuse_client,
                verbose=True,
                log_errors=True
            )
            aluminum_middlewares.append(langfuse_middleware)

        # 알루미늄 계산 도구 리스트
        aluminum_tools = [
            calculate_aluminum_price_square_pipe,
            calculate_aluminum_price_round_pipe,
            calculate_aluminum_price_angle,
            calculate_aluminum_price_flat_bar,
            calculate_aluminum_price_round_bar,
            calculate_aluminum_price_channel,
            calculate_price_from_weight_and_price_per_kg,
            calculate_price_per_kg_from_unit_price_and_weight,
        ]

        # 서브그래프 생성
        print(f"[🔨] Creating subgraphs...")
        self.delivery_subgraph = create_delivery_subgraph(
            checkpointer=self.checkpointer,
            delivery_parser=self.delivery_parser,
            document_generator=DocumentGenerator
        )
        self.product_subgraph = create_product_subgraph(
            checkpointer=self.checkpointer,
            product_parser=self.product_parser,
            document_generator=DocumentGenerator
        )
        self.aluminum_subgraph = create_aluminum_subgraph(
            model_name=model_name,
            temperature=temperature,
            aluminum_tools=aluminum_tools,
            middleware=aluminum_middlewares if aluminum_middlewares else None
        )

        # 메인 그래프 빌드
        self.graph = self._build_graph()

        print(f"[✅] Office Automation Graph initialized successfully")

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

    def _build_graph(self) -> StateGraph:
        """메인 그래프 빌드"""
        workflow = StateGraph(OfficeAutomationState)

        # 노드 추가
        workflow.add_node("classify_intent", self._classify_intent_node)
        workflow.add_node("help", self._help_node)
        workflow.add_node("delivery_subgraph", self.delivery_subgraph)
        workflow.add_node("product_subgraph", self.product_subgraph)
        workflow.add_node("aluminum_subgraph", self.aluminum_subgraph)

        # 엣지 연결
        workflow.set_entry_point("classify_intent")

        # classify_intent 후: 시나리오별 라우팅
        workflow.add_conditional_edges(
            "classify_intent",
            self._route_by_scenario,
            {
                "help": "help",
                "delivery": "delivery_subgraph",
                "product_order": "product_subgraph",
                "aluminum_calculation": "aluminum_subgraph",
            }
        )

        # 각 노드 → END
        workflow.add_edge("help", END)
        workflow.add_edge("delivery_subgraph", END)
        workflow.add_edge("product_subgraph", END)
        workflow.add_edge("aluminum_subgraph", END)

        # Compile
        return workflow.compile(checkpointer=self.checkpointer)

    # ========================================================================
    # 노드 함수들
    # ========================================================================

    def _classify_intent_node(self, state: OfficeAutomationState) -> Dict[str, Any]:
        """
        의도 분류 노드 (멀티턴 지원)

        active_scenario가 있으면 재분류하지 않고 해당 시나리오 유지

        Args:
            state: 현재 상태

        Returns:
            업데이트된 상태 (scenario, confidence)
        """
        # 멀티턴 대화: active_scenario가 있으면 그대로 유지
        active_scenario = state.get("active_scenario")
        if active_scenario:
            print(f"[🔒] Active scenario locked: {active_scenario} (multi-turn mode)")
            return {
                "scenario": active_scenario,
                "confidence": 1.0  # Active scenario는 100% 신뢰도
            }

        # active_scenario가 없으면 새로운 의도 분류
        raw_input = state.get("raw_input", "")
        print(f"[🔍] Classifying intent: {raw_input[:50]}...")

        intent = self.intent_classifier.classify(raw_input)
        print(f"[🎯] Intent: {intent.scenario} (confidence: {intent.confidence:.2f})")

        return {
            "scenario": intent.scenario,
            "confidence": intent.confidence
        }

    def _route_by_scenario(self, state: OfficeAutomationState) -> str:
        """
        시나리오별 라우팅 함수

        Args:
            state: 현재 상태

        Returns:
            다음 노드 이름
        """
        scenario = state.get("scenario")
        print(f"[🧭] Routing to: {scenario}")
        return scenario

    def _help_node(self, state: OfficeAutomationState) -> Dict[str, Any]:
        """
        도움말 노드

        Args:
            state: 현재 상태

        Returns:
            업데이트된 상태 (messages)
        """
        print(f"[ℹ️] Providing help message")

        help_message = """안녕하세요! 저는 사무 자동화 봇입니다. 👋

제가 도와드릴 수 있는 기능은 다음과 같습니다:

**1️⃣ 운송장 생성**
배송 정보를 입력하면 운송장 PDF를 자동으로 생성해드립니다.

필요한 정보:
- 하차지 (회사 이름)
- 주소 (상세주소 포함)
- 연락처 (010-XXXX-XXXX 형식)
- 지불방법 (착불 또는 선불)

**입력 예시:**
`(주)삼성전자 서울시 강남구 테헤란로 123 010-1234-5678 착불 35000원`

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

**3️⃣ 알루미늄 단가 계산**
알루미늄 제품의 단가를 자동으로 계산해드립니다.

지원 제품:
- 사각파이프, 원파이프, 앵글, 평철, 환봉, 찬넬

**입력 예시:**
- `사각파이프 50x30x2t, 3m`
- `원파이프 Ø40x2t, 6m`
- `중량 2.5kg, kg당 6000원`

---

**📌 사용 방법:**
1. 위 정보를 입력하시면 자동으로 처리됩니다
2. 문서 생성은 확인 버튼(승인/거절/편집)이 표시됩니다
3. 알루미늄 계산은 즉시 결과가 표시됩니다

궁금하신 점이 있으시면 언제든지 물어보세요! 😊"""

        return {
            "messages": [AIMessage(content=help_message)]
        }

    # ========================================================================
    # 외부 인터페이스
    # ========================================================================

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
            Graph 실행 결과
        """
        print(f"[📤] Invoking graph with thread_id={thread_id}...")

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

        initial_state = {
            "raw_input": raw_input,
            "input_type": input_type,
            "messages": [HumanMessage(content=raw_input)],
            "discord_user_id": discord_user_id,
            "discord_channel_id": discord_channel_id,
            "thread_id": thread_id,
            "awaiting_approval": False,
        }

        result = self.graph.invoke(initial_state, config)
        print(f"[✅] Graph execution completed")
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
            state = self.graph.get_state(config)
            return state
        except Exception as e:
            print(f"[⚠️] Failed to get state: {e}")
            return None

    def resume(
        self,
        decision_type: str,
        reject_message: Optional[str] = None,
        thread_id: str = "default",
    ) -> Dict[str, Any]:
        """
        HITL 승인/거절 후 워크플로우 재개

        Args:
            decision_type: "approve" 또는 "reject"
            reject_message: reject인 경우 거절 메시지
            thread_id: 스레드 ID

        Returns:
            Graph 실행 결과
        """
        config = {"configurable": {"thread_id": thread_id}}

        print(f"[🔄] Resuming graph with decision={decision_type}, thread_id={thread_id}...")

        # 현재 상태 가져오기
        state = self.graph.get_state(config)
        if not state:
            print(f"[❌] No state found for thread_id={thread_id}")
            return {"error": "No state found"}

        # Subgraph interrupt인 경우: subgraph state 업데이트
        if state.tasks and len(state.tasks) > 0:
            task = state.tasks[0]
            print(f"[🔍] Found interrupted task: {task.name}")

            # Subgraph의 state 업데이트
            update_values = {
                "approval_decision": decision_type,
                "awaiting_approval": False
            }

            if decision_type == "reject":
                update_values["reject_message"] = reject_message or "사용자가 거절했습니다."

            # update_state를 사용하여 subgraph state 업데이트
            print(f"[🔧] Updating subgraph state: {update_values}")
            self.graph.update_state(task.state, update_values)

            # 그래프 재개 (invoke 없이, 단순히 None으로 재개)
            print(f"[🚀] Invoking graph to resume from interrupt...")
            result = self.graph.invoke(None, config)
        else:
            # Main graph interrupt (이 경우는 없어야 함)
            print(f"[⚠️] No tasks found - updating main graph state")
            updated_values = {
                "approval_decision": decision_type,
                "awaiting_approval": False
            }

            if decision_type == "reject":
                updated_values["reject_message"] = reject_message or "사용자가 거절했습니다."

            self.graph.update_state(config, updated_values)
            result = self.graph.invoke(None, config)

        print(f"[✅] Graph resume completed")
        return result
