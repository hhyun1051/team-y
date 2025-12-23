"""
Product SubGraph - 거래명세서 생성 워크플로우

워크플로우:
1. parse → 거래명세서 정보 파싱 및 검증
2. format_approval → 승인 메시지 포맷팅
3. approval (interrupt) → 사용자 승인 대기
4. generate → 거래명세서 문서 생성
"""

from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage

from ..state import OfficeAutomationState


def create_product_subgraph(checkpointer, product_parser, document_generator):
    """
    거래명세서 생성 서브그래프 생성

    Args:
        checkpointer: MemorySaver 인스턴스
        product_parser: ProductOrderParser 인스턴스
        document_generator: DocumentGenerator 클래스

    Returns:
        Compiled SubGraph
    """
    subgraph = StateGraph(OfficeAutomationState)

    # 노드 추가 (파서와 문서생성기를 클로저로 캡처)
    def parse_node(state):
        return _parse_product(state, product_parser)

    def generate_node(state):
        return _generate_product(state, document_generator)

    subgraph.add_node("parse", parse_node)
    subgraph.add_node("format_approval", _format_product_approval)
    subgraph.add_node("approval", _approval_node)
    subgraph.add_node("generate", generate_node)
    subgraph.add_node("retry", _retry_node)

    # 엣지 연결
    subgraph.set_entry_point("parse")

    # parse 후: 파싱 성공 → format_approval, 파싱 실패 → retry
    subgraph.add_conditional_edges(
        "parse",
        lambda state: "format_approval" if state.get("product_order_info") else "retry",
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


def _parse_product(state: OfficeAutomationState, parser) -> Dict[str, Any]:
    """
    거래명세서 정보 파싱 노드 (멀티턴 지원)

    Args:
        state: 현재 상태
        parser: ProductOrderParser 인스턴스

    Returns:
        업데이트된 상태
    """
    raw_input = state.get("raw_input", "")
    messages = state.get("messages", [])

    print(f"[🏭] Parsing product order info from: {raw_input[:50]}...")
    print(f"[📝] Message history count: {len(messages)}")

    try:
        # 멀티턴 지원: messages 전달
        parsed_info, is_valid, error_msg = parser.parse_with_validation(raw_input, messages=messages)

        if not is_valid:
            print(f"[❌] Parsing failed: {error_msg}")
            # 멀티턴: active_scenario를 "product_order"로 고정하여 다음 입력도 product_order로 라우팅
            import time
            return {
                "parsing_error": error_msg,
                "product_order_info": None,
                "active_scenario": "product_order",
                "active_scenario_timestamp": time.time()
            }

        print(f"[✅] Product order parsed: {parsed_info.client}, {parsed_info.product_name}")
        # 파싱 성공: active_scenario 제거 (새로운 시나리오 시작 가능)
        return {
            "product_order_info": parsed_info,
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
            "product_order_info": None,
            "active_scenario": "product_order",
            "active_scenario_timestamp": time.time()
        }


def _format_product_approval(state: OfficeAutomationState) -> Dict[str, Any]:
    """
    승인 메시지 포맷팅 노드

    Args:
        state: 현재 상태

    Returns:
        업데이트된 상태 (approval_message 포함)
    """
    info = state.get("product_order_info")
    if not info:
        return {"approval_message": "❌ 파싱된 정보가 없습니다."}

    # 합계 계산
    total_price = info.quantity * info.unit_price

    # 승인 메시지 포맷팅
    approval_msg = f"""**거래명세서 정보:**

- 거래처: {info.client}
- 품목: {info.product_name}
- 수량: {info.quantity}개
- 단가: {info.unit_price:,}원
- **합계: {total_price:,}원**"""

    if info.notes:
        approval_msg += f"\n- 참고: {info.notes}"

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


def _generate_product(state: OfficeAutomationState, document_generator) -> Dict[str, Any]:
    """
    거래명세서 문서 생성 노드

    Args:
        state: 현재 상태
        document_generator: DocumentGenerator 클래스

    Returns:
        업데이트된 상태 (pdf_path, docx_path, messages 포함)
    """
    info = state.get("product_order_info")
    if not info:
        return {
            "messages": [AIMessage(content="❌ 거래명세서 정보가 없습니다.")]
        }

    print(f"[📄] Generating product order document...")

    try:
        result = document_generator.generate_product_order_document(
            client=info.client,
            product_name=info.product_name,
            quantity=info.quantity,
            unit_price=info.unit_price
        )

        print(f"[✅] Document generated: {result['pdf']}")

        total_price = info.quantity * info.unit_price

        success_msg = f"""✅ 거래명세서 생성 완료!

📄 **생성된 파일:**
- PDF: `{result['pdf']}`
- DOCX: `{result['docx']}`

【거래 정보】
- 거래처: {info.client}
- 품목: {info.product_name}
- 수량: {info.quantity}개
- 단가: {info.unit_price:,}원
- **합계: {total_price:,}원**"""

        return {
            "pdf_path": result["pdf"],
            "docx_path": result["docx"],
            "image_paths": result.get("images", []),
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
