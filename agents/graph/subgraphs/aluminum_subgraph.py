"""
Aluminum SubGraph - 알루미늄 계산 워크플로우

워크플로우:
1. parse_aluminum → 파싱 성공 시 calculate_aluminum
2. parse_aluminum → 파싱 실패 시 retry
3. calculate_aluminum → 계산 수행 후 END

특징:
- 멀티턴 지원 (파싱 실패 시 시나리오 잠금)
- 승인 프로세스 없음 (즉시 계산)
- 8가지 계산 공식 지원
"""

from typing import Dict, Any
from langgraph.graph import StateGraph, END
import time

from ..state import OfficeAutomationState
from ..utils.tools import aluminum_calculator


def create_aluminum_subgraph(parser):
    """
    알루미늄 계산 서브그래프 생성

    Args:
        parser: AluminumCalculationParser 인스턴스

    Returns:
        Compiled SubGraph
    """
    subgraph = StateGraph(OfficeAutomationState)

    # 노드 추가 (parser를 클로저로 캡처)
    def parse_node(state):
        return _parse_aluminum(state, parser)

    subgraph.add_node("parse_aluminum", parse_node)
    subgraph.add_node("calculate_aluminum", _calculate_aluminum)
    subgraph.add_node("retry", _retry_node)

    # 진입점
    subgraph.set_entry_point("parse_aluminum")

    # 조건부 라우팅: parse → calculate or retry
    def should_retry(state: OfficeAutomationState) -> str:
        """파싱 에러가 있으면 retry, 없으면 calculate"""
        if state.get("parsing_error"):
            return "retry"
        return "calculate_aluminum"

    subgraph.add_conditional_edges(
        "parse_aluminum",
        should_retry,
        {
            "calculate_aluminum": "calculate_aluminum",
            "retry": "retry"
        }
    )

    # calculate → END
    subgraph.add_edge("calculate_aluminum", END)

    # retry → END (멀티턴 대기)
    subgraph.add_edge("retry", END)

    return subgraph.compile()


def _parse_aluminum(state: OfficeAutomationState, parser) -> Dict[str, Any]:
    """
    알루미늄 정보 파싱 노드 (멀티턴 지원)
    """
    raw_input = state.get("raw_input", "")
    messages = state.get("messages", [])

    print(f"[🔧] Parsing aluminum info from: {raw_input[:50]}...")
    print(f"[📝] Message history count: {len(messages)}")

    try:
        # 멀티턴 지원: messages 전달
        parsed_info, is_valid, error_msg = parser.parse_with_validation(raw_input, messages=messages)

        if not is_valid:
            print(f"[❌] Parsing failed: {error_msg}")
            return {
                "parsing_error": error_msg,
                "aluminum_calculation_info": None,
                "active_scenario": "aluminum_calculation",
                "active_scenario_timestamp": time.time()
            }

        print(f"[✅] Aluminum info parsed: {parsed_info.product_type}, {parsed_info.length_m}m")
        return {
            "aluminum_calculation_info": parsed_info,
            "parsing_error": None,
            "active_scenario": None,
            "active_scenario_timestamp": None
        }

    except Exception as e:
        print(f"[❌] Parsing exception: {e}")
        return {
            "parsing_error": f"파싱 중 오류 발생: {str(e)}",
            "aluminum_calculation_info": None,
            "active_scenario": "aluminum_calculation",
            "active_scenario_timestamp": time.time()
        }


def _calculate_aluminum(state: OfficeAutomationState) -> Dict[str, Any]:
    """
    알루미늄 계산 노드 - 8가지 공식 중 선택하여 계산
    """
    calc_info = state.get("aluminum_calculation_info")

    if not calc_info:
        print("[❌] No aluminum calculation info")
        from langchain_core.messages import AIMessage
        return {
            "messages": [AIMessage(content="❌ 알루미늄 계산 정보가 없습니다.")]
        }

    print(f"[🔧] Calculating {calc_info.product_type}...")

    try:
        result = None

        # 제품 타입에 따라 계산 함수 선택
        if calc_info.product_type == "round_pipe":
            result = aluminum_calculator.calculate_round_pipe_weight(
                diameter=calc_info.diameter,
                thickness=calc_info.thickness,
                length=calc_info.length_m,
                quantity=calc_info.quantity,
                density=calc_info.density
            )

        elif calc_info.product_type == "flat_bar":
            result = aluminum_calculator.calculate_flat_bar_weight(
                width=calc_info.width,
                thickness=calc_info.thickness,
                density=calc_info.density,
                length=calc_info.length_m,
                quantity=calc_info.quantity
            )

        elif calc_info.product_type == "channel":
            result = aluminum_calculator.calculate_channel_weight(
                width=calc_info.channel_width,
                height=calc_info.channel_height,
                thickness=calc_info.thickness,
                density=calc_info.density,
                length=calc_info.length_m,
                quantity=calc_info.quantity
            )

        elif calc_info.product_type == "square_pipe":
            result = aluminum_calculator.calculate_square_pipe_weight(
                width=calc_info.width,
                height=calc_info.height,
                thickness=calc_info.thickness,
                density=calc_info.density,
                length=calc_info.length_m,
                quantity=calc_info.quantity
            )

        elif calc_info.product_type == "angle":
            result = aluminum_calculator.calculate_angle_weight(
                width=calc_info.width_a,
                height=calc_info.width_b,
                thickness=calc_info.thickness,
                density=calc_info.density,
                length=calc_info.length_m,
                quantity=calc_info.quantity
            )

        elif calc_info.product_type == "round_bar":
            result = aluminum_calculator.calculate_round_bar_weight(
                diameter=calc_info.diameter,
                density=calc_info.density,
                length=calc_info.length_m,
                quantity=calc_info.quantity
            )

        else:
            raise ValueError(f"Unknown product type: {calc_info.product_type}")

        # 결과 포맷팅
        formatted_result = aluminum_calculator.format_result(result)

        print(f"[✅] Calculation completed: {result['weight_kg']:.4f} kg")

        from langchain_core.messages import AIMessage
        return {
            "messages": [AIMessage(content=formatted_result)]
        }

    except Exception as e:
        print(f"[❌] Calculation failed: {e}")
        from langchain_core.messages import AIMessage
        return {
            "messages": [AIMessage(content=f"❌ 계산 실패: {str(e)}")]
        }


def _retry_node(state: OfficeAutomationState) -> Dict[str, Any]:
    """
    재시도 메시지 생성 노드
    """
    error_msg = state.get("parsing_error", "알 수 없는 오류")

    retry_message = f"""❌ {error_msg}

누락된 정보만 입력해주세요."""

    from langchain_core.messages import AIMessage
    return {
        "messages": [AIMessage(content=retry_message)]
    }
