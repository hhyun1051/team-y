"""
Aluminum SubGraph - 알루미늄 단가 계산 워크플로우

워크플로우:
1. aluminum_agent → Agent가 8개 계산 도구 중 선택하여 실행

특징:
- 승인 프로세스 없음 (즉시 실행)
- Agent 패턴 사용 (LLM이 도구 선택)
- 단일 노드 SubGraph
"""

from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from ..state import OfficeAutomationState


def create_aluminum_subgraph(model_name: str, temperature: float, aluminum_tools: List, middleware: List = None):
    """
    알루미늄 계산 서브그래프 생성

    Args:
        model_name: LLM 모델 이름
        temperature: 모델 temperature
        aluminum_tools: 8개 알루미늄 계산 도구 리스트
        middleware: Middleware 리스트 (Langfuse 로깅 등)

    Returns:
        Compiled SubGraph (interrupt 없음)
    """
    # Agent 생성 (8개 계산 도구)
    system_prompt = """당신은 알루미늄 제품 단가 계산 전문가입니다.

사용자 입력에서 제품 종류와 규격을 파악하여 적절한 계산 도구를 선택하세요.

**사용 가능한 도구:**
- calculate_aluminum_price_square_pipe: 사각파이프 (폭, 높이, 두께, 길이)
- calculate_aluminum_price_round_pipe: 원파이프 (외경, 두께, 길이)
- calculate_aluminum_price_angle: 앵글(ㄱ자) (폭A, 폭B, 두께, 길이)
- calculate_aluminum_price_flat_bar: 평철 (폭, 두께, 길이)
- calculate_aluminum_price_round_bar: 환봉 (지름, 길이)
- calculate_aluminum_price_channel: 찬넬(C형강) (높이, 폭, 두께, 길이)
- calculate_price_from_weight_and_price_per_kg: 중량과 kg당 가격으로 개당 가격 계산
- calculate_price_per_kg_from_unit_price_and_weight: 제품 단가와 중량으로 kg당 가격 계산

**중요:**
- 사용자 입력에서 제품 종류와 규격을 정확히 파악하세요
- 적절한 도구를 선택하여 즉시 계산을 수행하세요
- 계산 결과를 명확하게 반환하세요"""

    agent = create_agent(
        model=f"openai:{model_name}",
        tools=aluminum_tools,
        system_prompt=system_prompt,
        middleware=middleware if middleware else []
    )

    subgraph = StateGraph(OfficeAutomationState)

    # 노드 추가 (Agent를 클로저로 캡처)
    def aluminum_agent_node(state):
        return _run_aluminum_agent(state, agent)

    subgraph.add_node("aluminum_agent", aluminum_agent_node)
    subgraph.set_entry_point("aluminum_agent")
    subgraph.add_edge("aluminum_agent", END)

    # Compile: interrupt 없음 (즉시 실행)
    return subgraph.compile()


def _run_aluminum_agent(state: OfficeAutomationState, agent) -> Dict[str, Any]:
    """
    알루미늄 Agent 실행 노드

    Args:
        state: 현재 상태
        agent: create_agent로 생성된 Agent

    Returns:
        업데이트된 상태 (messages 포함)
    """
    raw_input = state.get("raw_input", "")
    print(f"[🔧] Running aluminum calculation agent: {raw_input[:50]}...")

    try:
        # Agent에게 사용자 입력 전달
        messages = state.get("messages", [])

        # 새 메시지 추가 (raw_input을 HumanMessage로)
        if raw_input and not any(isinstance(m, HumanMessage) and m.content == raw_input for m in messages):
            messages = messages + [HumanMessage(content=raw_input)]

        # Agent 실행
        result = agent.invoke({"messages": messages})

        print(f"[✅] Aluminum calculation completed")

        # Agent의 메시지 반환
        return {"messages": result["messages"]}

    except Exception as e:
        print(f"[❌] Aluminum calculation failed: {e}")
        from langchain_core.messages import AIMessage
        return {
            "messages": [AIMessage(content=f"❌ 알루미늄 계산 실패: {str(e)}")]
        }
