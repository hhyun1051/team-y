"""
Delivery SubGraph - 운송장 생성 워크플로우

워크플로우:
1. parse → 운송장 정보 파싱 및 검증
2. format_approval → 승인 메시지 포맷팅
3. approval (interrupt) → 사용자 승인 대기
4. generate → 운송장 문서 생성
"""

from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage

from ..state import OfficeAutomationState


def create_delivery_subgraph(checkpointer, delivery_parser, document_generator):
    """
    운송장 생성 서브그래프 생성

    Args:
        checkpointer: MemorySaver 인스턴스
        delivery_parser: DeliveryParser 인스턴스
        document_generator: DocumentGenerator 클래스

    Returns:
        Compiled SubGraph
    """
    subgraph = StateGraph(OfficeAutomationState)

    # 노드 추가 (파서와 문서생성기를 클로저로 캡처)
    def parse_node(state):
        return _parse_delivery(state, delivery_parser)

    def generate_node(state):
        return _generate_delivery(state, document_generator)

    subgraph.add_node("parse", parse_node)
    subgraph.add_node("format_approval", _format_delivery_approval)
    subgraph.add_node("approval", _approval_node)
    subgraph.add_node("generate", generate_node)
    subgraph.add_node("retry", _retry_node)

    # 엣지 연결
    subgraph.set_entry_point("parse")

    # parse 후: 파싱 성공 → format_approval, 파싱 실패 → retry
    subgraph.add_conditional_edges(
        "parse",
        lambda state: "format_approval" if state.get("delivery_info") else "retry",
        {
            "format_approval": "format_approval",
            "retry": "retry"
        }
    )

    # retry → END (사용자에게 재입력 요청 메시지 반환)
    subgraph.add_edge("retry", END)

    # format_approval → approval (항상)
    subgraph.add_edge("format_approval", "approval")

    # approval 후: 승인 → generate, 거절 → END
    subgraph.add_conditional_edges(
        "approval",
        lambda state: "generate" if state.get("approval_decision") == "approve" else END,
        {
            "generate": "generate",
            END: END
        }
    )

    # generate → END (문서 생성 완료)
    subgraph.add_edge("generate", END)

    # Compile: approval 노드 전에 interrupt 발생
    return subgraph.compile(
        checkpointer=checkpointer,
        interrupt_before=["approval"]
    )


def _parse_delivery(state: OfficeAutomationState, parser) -> Dict[str, Any]:
    """
    운송장 정보 파싱 노드 (멀티턴 지원)

    Args:
        state: 현재 상태
        parser: DeliveryParser 인스턴스

    Returns:
        업데이트된 상태
    """
    raw_input = state.get("raw_input", "")
    messages = state.get("messages", [])

    print(f"[📦] Parsing delivery info from: {raw_input[:50]}...")
    print(f"[📝] Message history count: {len(messages)}")

    try:
        # 멀티턴 지원: messages 전달
        parsed_info, is_valid, error_msg = parser.parse_with_validation(raw_input, messages=messages)

        if not is_valid:
            print(f"[❌] Parsing failed: {error_msg}")
            # 멀티턴: active_scenario를 "delivery"로 고정하여 다음 입력도 delivery로 라우팅
            import time
            return {
                "parsing_error": error_msg,
                "delivery_info": None,
                "active_scenario": "delivery",
                "active_scenario_timestamp": time.time()
            }

        print(f"[✅] Delivery info parsed: {parsed_info.unloading_site}, {parsed_info.contact}")
        # 파싱 성공: active_scenario 제거 (새로운 시나리오 시작 가능)
        return {
            "delivery_info": parsed_info,
            "parsing_error": None,
            "active_scenario": None,
            "active_scenario_timestamp": None
        }

    except Exception as e:
        print(f"[❌] Parsing exception: {e}")
        # 멀티턴: 예외 발생 시에도 active_scenario 고정
        import time
        return {
            "parsing_error": f"파싱 중 오류 발생: {str(e)}",
            "delivery_info": None,
            "active_scenario": "delivery",
            "active_scenario_timestamp": time.time()
        }


def _format_delivery_approval(state: OfficeAutomationState) -> Dict[str, Any]:
    """
    승인 메시지 포맷팅 노드

    Args:
        state: 현재 상태

    Returns:
        업데이트된 상태 (approval_message 포함)
    """
    info = state.get("delivery_info")
    if not info:
        return {"approval_message": "❌ 파싱된 정보가 없습니다."}

    # 승인 메시지 포맷팅
    approval_msg = f"""**운송장 정보:**

【하차지 정보】
- 하차지: {info.unloading_site}
- 주소: {info.address}
- 연락처: {info.contact}

【상차지 정보】
- 상차지: {info.loading_site}"""

    if info.loading_address:
        approval_msg += f"\n- 상차지 주소: {info.loading_address}"
    if info.loading_phone:
        approval_msg += f"\n- 상차지 전화번호: {info.loading_phone}"

    approval_msg += f"\n\n【운송비】\n- 지불방법: {info.payment_type}"
    if info.freight_cost:
        approval_msg += f"\n- 운송비: {info.freight_cost:,}원"

    if info.notes:
        approval_msg += f"\n\n- 비고: {info.notes}"

    if info.confidence:
        approval_msg += f"\n\n신뢰도: {info.confidence * 100:.0f}%"

    print(f"[✅] Approval message formatted")

    return {
        "approval_message": approval_msg,
        "awaiting_approval": True
    }


def _approval_node(state: OfficeAutomationState) -> Dict[str, Any]:
    """
    승인 노드 (interrupt 후 재개 지점)

    이 노드는 interrupt 전에는 실행되지 않습니다.
    Resume 후 실행될 때는 approval_decision이 이미 설정되어 있어야 합니다.

    Args:
        state: 현재 상태

    Returns:
        업데이트된 상태
    """
    decision = state.get("approval_decision")
    print(f"[🔄] Approval node: decision={decision}")

    if decision == "approve":
        print(f"[✅] Approved - proceeding to document generation")
        return {"awaiting_approval": False}
    elif decision == "reject":
        reject_msg = state.get("reject_message", "사용자가 거절했습니다.")
        print(f"[❌] Rejected: {reject_msg}")
        return {
            "awaiting_approval": False,
            "messages": [AIMessage(content=f"❌ 거절됨: {reject_msg}")]
        }
    else:
        # 이 경우는 발생하지 않아야 함 (interrupt 후 resume으로만 도달)
        print(f"[⚠️] Approval node reached without decision")
        return {"awaiting_approval": False}


def _generate_delivery(state: OfficeAutomationState, document_generator) -> Dict[str, Any]:
    """
    운송장 문서 생성 노드

    Args:
        state: 현재 상태
        document_generator: DocumentGenerator 클래스

    Returns:
        업데이트된 상태 (pdf_path, docx_path, messages 포함)
    """
    info = state.get("delivery_info")
    if not info:
        return {
            "messages": [AIMessage(content="❌ 운송장 정보가 없습니다.")]
        }

    print(f"[📄] Generating delivery document...")

    try:
        result = document_generator.generate_delivery_document(
            unloading_site=info.unloading_site,
            address=info.address,
            contact=info.contact,
            payment_type=info.payment_type,
            freight_cost=info.freight_cost,
            loading_site=info.loading_site,
            loading_address=info.loading_address,
            loading_phone=info.loading_phone,
            notes=info.notes
        )

        print(f"[✅] Document generated: {result['pdf']}")

        success_msg = f"""✅ 운송장 생성 완료!

📄 **생성된 파일:**
- PDF: `{result['pdf']}`
- DOCX: `{result['docx']}`

【하차지 정보】
- 하차지: {info.unloading_site}
- 주소: {info.address}
- 연락처: {info.contact}

【운송비】
- 지불방법: {info.payment_type}"""

        if info.freight_cost:
            success_msg += f"\n- 운송비: {info.freight_cost:,}원"

        return {
            "pdf_path": result["pdf"],
            "docx_path": result["docx"],
            "messages": [AIMessage(content=success_msg)]
        }

    except Exception as e:
        print(f"[❌] Document generation failed: {e}")
        return {
            "messages": [AIMessage(content=f"❌ 문서 생성 실패: {str(e)}")]
        }


def _retry_node(state: OfficeAutomationState) -> Dict[str, Any]:
    """
    파싱 실패 시 재시도 메시지 생성 노드

    Args:
        state: 현재 상태

    Returns:
        업데이트된 상태 (messages 포함)
    """
    error_msg = state.get("parsing_error", "알 수 없는 오류")

    retry_message = f"""❌ {error_msg}

누락된 정보만 입력해주세요."""

    print(f"[⚠️] Retry node: {error_msg}")

    return {
        "messages": [AIMessage(content=retry_message)]
    }
