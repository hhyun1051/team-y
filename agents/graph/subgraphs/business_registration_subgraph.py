"""
Business Registration SubGraph - 사업자등록증 등록 워크플로우

워크플로우:
1. wait_for_image (interrupt) → 이미지 업로드 대기
2. parse → Vision LLM으로 사업자등록증 파싱
3. format_approval → 승인 메시지 포맷팅
4. approval (interrupt) → 사용자 승인 대기 (편집 가능)
5. save → 정보 저장 (완료 메시지)
"""

from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage

from ..state import OfficeAutomationState
from database.postgres import insert_registration, get_by_business_number


def create_business_registration_subgraph(checkpointer, parser):
    """
    사업자등록증 등록 서브그래프 생성

    Args:
        checkpointer: MemorySaver 인스턴스
        parser: BusinessRegistrationParser 인스턴스

    Returns:
        Compiled SubGraph
    """
    subgraph = StateGraph(OfficeAutomationState)

    # 노드 추가 (파서를 클로저로 캡처)
    def parse_node(state):
        return _parse_business_registration(state, parser)

    subgraph.add_node("wait_for_image", _wait_for_image_node)
    subgraph.add_node("parse", parse_node)
    subgraph.add_node("format_approval", _format_approval)
    subgraph.add_node("approval", _approval_node)
    subgraph.add_node("save", _save_node)
    subgraph.add_node("retry", _retry_node)

    # 엣지 연결
    subgraph.set_entry_point("wait_for_image")

    # wait_for_image → parse (이미지 업로드 후 파싱)
    subgraph.add_edge("wait_for_image", "parse")

    # parse 후: 파싱 성공 → format_approval, 파싱 실패 → retry
    subgraph.add_conditional_edges(
        "parse",
        lambda state: "format_approval" if state.get("business_registration_info") else "retry",
        {
            "format_approval": "format_approval",
            "retry": "retry"
        }
    )

    # retry → END (재입력 요청 메시지 반환)
    subgraph.add_edge("retry", END)

    # format_approval → approval (항상)
    subgraph.add_edge("format_approval", "approval")

    # approval 후: 승인 → save, 거절 → END
    subgraph.add_conditional_edges(
        "approval",
        lambda state: "save" if state.get("approval_decision") == "approve" else END,
        {
            "save": "save",
            END: END
        }
    )

    # save → END (완료)
    subgraph.add_edge("save", END)

    # Compile: wait_for_image와 approval 노드 전에 interrupt 발생
    return subgraph.compile(
        checkpointer=checkpointer,
        interrupt_before=["wait_for_image", "approval"]
    )


def _wait_for_image_node(state: OfficeAutomationState) -> Dict[str, Any]:
    """
    이미지 업로드 대기 노드 (첫 interrupt 지점)

    Args:
        state: 현재 상태

    Returns:
        업데이트된 상태
    """
    print(f"[📸] Waiting for business registration image...")

    # 멀티턴: active_scenario를 "business_registration"으로 고정
    import time
    return {
        "active_scenario": "business_registration",
        "active_scenario_timestamp": time.time(),
        "messages": [AIMessage(content="📄 **사업자등록증 이미지를 업로드해주세요.**\n\n이미지를 첨부하면 자동으로 정보를 추출합니다.")]
    }


def _parse_business_registration(state: OfficeAutomationState, parser) -> Dict[str, Any]:
    """
    사업자등록증 정보 파싱 노드 (Vision LLM)

    Args:
        state: 현재 상태
        parser: BusinessRegistrationParser 인스턴스

    Returns:
        업데이트된 상태
    """
    raw_input = state.get("raw_input", "")
    print(f"[🔍] ===== PARSE NODE STARTED =====")
    print(f"[🔍] Parsing business registration from image: {raw_input[:200]}...")
    print(f"[🔍] Parser type: {type(parser)}")

    try:
        # raw_input은 이미지 URL이어야 함
        image_url = raw_input

        # Vision LLM으로 파싱
        parsed_info, is_valid, error_msg = parser.parse_with_validation(image_url)

        if not is_valid:
            print(f"[❌] Parsing failed: {error_msg}")
            # 파싱 실패: active_scenario 유지 (재시도 가능)
            import time
            return {
                "parsing_error": error_msg,
                "business_registration_info": None,
                "active_scenario": "business_registration",
                "active_scenario_timestamp": time.time()
            }

        print(f"[✅] Business registration info parsed: {parsed_info.business_name}")
        # 파싱 성공: active_scenario 제거
        return {
            "business_registration_info": parsed_info,
            "parsing_error": None,
            "active_scenario": None,
            "active_scenario_timestamp": None
        }

    except Exception as e:
        print(f"[❌] Parsing exception: {e}")
        # 예외 발생: active_scenario 유지
        import time
        return {
            "parsing_error": f"파싱 중 오류 발생: {str(e)}",
            "business_registration_info": None,
            "active_scenario": "business_registration",
            "active_scenario_timestamp": time.time()
        }


def _format_approval(state: OfficeAutomationState) -> Dict[str, Any]:
    """
    승인 메시지 포맷팅 노드

    Args:
        state: 현재 상태

    Returns:
        업데이트된 상태 (approval_message 포함)
    """
    info = state.get("business_registration_info")
    if not info:
        return {"approval_message": "❌ 파싱된 정보가 없습니다."}

    # 승인 메시지 포맷팅 (모든 필드 표시)
    approval_msg = f"""**📄 사업자등록증 정보:**

【기본 정보】
- 거래처명: {info.client_name}
- 상호: {info.business_name}
- 대표자명: {info.representative_name or 'N/A'}
- 사업자번호: {info.business_number or 'N/A'}
- 종사업자번호: {info.branch_number or 'N/A'}

【주소】
- 우편번호: {info.postal_code or 'N/A'}
- 주소1: {info.address1 or 'N/A'}
- 주소2: {info.address2 or 'N/A'}

【업종】
- 업태: {info.business_type or 'N/A'}
- 종목: {info.business_item or 'N/A'}

【연락처】
- 전화1: {info.phone1 or 'N/A'}
- 전화2: {info.phone2 or 'N/A'}
- 팩스: {info.fax or 'N/A'}

【담당자】
- 담당자1: {info.contact_person1 or 'N/A'}
- 휴대폰1: {info.mobile1 or 'N/A'}
- 담당자2: {info.contact_person2 or 'N/A'}
- 휴대폰2: {info.mobile2 or 'N/A'}

【추가 정보】
- 거래처구분: {info.client_type or '미입력 (편집 필요)'}
- 출고가등급: {info.price_grade or '미입력 (편집 필요)'}
- 기초잔액: {info.initial_balance:,}원
- 적정잔액: {info.optimal_balance:,}원
- 메모: {info.memo or 'N/A'}
"""

    if info.confidence:
        approval_msg += f"\n신뢰도: {info.confidence * 100:.0f}%"

    approval_msg += "\n\n⚠️ **편집 버튼**을 눌러 거래처구분, 출고가등급 등 추가 정보를 입력해주세요."

    print(f"[✅] Approval message formatted")

    return {
        "approval_message": approval_msg,
        "awaiting_approval": True
    }


def _approval_node(state: OfficeAutomationState) -> Dict[str, Any]:
    """
    승인 노드 (interrupt 후 재개 지점)

    Args:
        state: 현재 상태

    Returns:
        업데이트된 상태
    """
    decision = state.get("approval_decision")
    print(f"[🔄] Approval node: decision={decision}")

    if decision == "approve":
        print(f"[✅] Approved - proceeding to save")
        return {"awaiting_approval": False}
    elif decision == "reject":
        reject_msg = state.get("reject_message", "사용자가 거절했습니다.")
        print(f"[❌] Rejected: {reject_msg}")
        return {
            "awaiting_approval": False,
            "messages": [AIMessage(content=f"❌ 거절됨: {reject_msg}")]
        }
    else:
        print(f"[⚠️] Approval node reached without decision")
        return {"awaiting_approval": False}


def _save_node(state: OfficeAutomationState) -> Dict[str, Any]:
    """
    정보 저장 노드 (PostgreSQL DB 저장)

    Args:
        state: 현재 상태

    Returns:
        업데이트된 상태 (messages 포함)
    """
    info = state.get("business_registration_info")
    if not info:
        return {
            "messages": [AIMessage(content="❌ 저장할 정보가 없습니다.")]
        }

    print(f"[💾] Saving business registration info: {info.business_name}")

    try:
        # 1. 사업자번호 중복 체크 (있는 경우만)
        if info.business_number:
            existing = get_by_business_number(info.business_number)
            if existing:
                error_msg = f"""⚠️ 이미 등록된 사업자번호입니다!

**기존 등록 정보:**
- ERP 코드: {existing['erp_code']}
- 거래처명: {existing['client_name']}
- 상호: {existing['business_name']}
- 등록일: {existing['created_at']}

등록을 취소합니다."""
                print(f"[⚠️] Duplicate business_number: {info.business_number}")
                return {
                    "messages": [AIMessage(content=error_msg)]
                }

        # 2. BusinessRegistrationInfo → dict 변환
        data = info.model_dump()

        # 3. Discord 메타데이터 추가
        data['discord_user_id'] = state.get('discord_user_id')
        data['discord_message_id'] = state.get('discord_channel_id')  # channel_id를 message context로 사용

        # 4. DB 저장
        result = insert_registration(data)
        erp_code = result['erp_code']
        record_id = result['id']

        print(f"[✅] Saved to DB: id={record_id}, erp_code={erp_code}")

        # 5. 성공 메시지 (모든 필드 표시)
        success_msg = f"""✅ 사업자등록증 정보가 등록되었습니다!

**등록된 정보:**
- **ERP 코드: {erp_code}** 🎯

【기본 정보】
- 거래처명: {info.client_name}
- 상호: {info.business_name}
- 대표자명: {info.representative_name or 'N/A'}
- 사업자번호: {info.business_number or 'N/A'}
- 종사업자번호: {info.branch_number or 'N/A'}

【주소】
- 우편번호: {info.postal_code or 'N/A'}
- 주소1: {info.address1 or 'N/A'}
- 주소2: {info.address2 or 'N/A'}

【업종】
- 업태: {info.business_type or 'N/A'}
- 종목: {info.business_item or 'N/A'}

【연락처】
- 전화1: {info.phone1 or 'N/A'}
- 전화2: {info.phone2 or 'N/A'}
- 팩스: {info.fax or 'N/A'}

【담당자】
- 담당자1: {info.contact_person1 or 'N/A'}
- 휴대폰1: {info.mobile1 or 'N/A'}
- 담당자2: {info.contact_person2 or 'N/A'}
- 휴대폰2: {info.mobile2 or 'N/A'}

【추가 정보】
- 거래처구분: {info.client_type or 'N/A'}
- 출고가등급: {info.price_grade or 'N/A'}
- 기초잔액: {info.initial_balance:,}원
- 적정잔액: {info.optimal_balance:,}원
- 메모: {info.memo or 'N/A'}

📌 거래처 정보가 데이터베이스에 저장되었습니다. (ID: {record_id})"""

        return {
            "messages": [AIMessage(content=success_msg)],
            "erp_code": erp_code,
            "db_record_id": record_id
        }

    except ValueError as e:
        # 필수 필드 누락 등
        error_msg = f"❌ 데이터 검증 실패: {str(e)}"
        print(f"[❌] Validation error: {e}")
        return {
            "messages": [AIMessage(content=error_msg)]
        }
    except Exception as e:
        # DB 연결 오류 등
        error_msg = f"❌ 데이터베이스 저장 실패: {str(e)}\n\n정보는 파싱되었지만 저장되지 않았습니다."
        print(f"[❌] DB error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "messages": [AIMessage(content=error_msg)]
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

다시 시도해주세요:
- 사업자등록증 이미지가 명확하고 선명한지 확인하세요
- 이미지가 잘렸거나 흐릿하지 않은지 확인하세요
- 다른 이미지를 업로드해주세요"""

    print(f"[⚠️] Retry node: {error_msg}")

    return {
        "messages": [AIMessage(content=retry_message)]
    }
