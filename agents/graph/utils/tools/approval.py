"""
HITL Approval Tools

HumanInTheLoopMiddleware와 함께 사용되는 승인 요청 도구
"""

from langchain_core.tools import tool


@tool
def request_approval_delivery(parsed_info: str) -> str:
    """
    운송장 정보에 대한 사용자 승인을 요청합니다.

    이 tool이 호출되면 HumanInTheLoopMiddleware가 interrupt를 발생시킵니다.

    Args:
        parsed_info: 파싱된 운송장 정보 (포맷팅된 문자열)

    Returns:
        승인 결과 메시지
    """
    return "✅ 운송장 정보가 승인되었습니다. 이제 즉시 generate_delivery_document tool을 호출하여 문서를 생성하세요."


@tool
def request_approval_product(parsed_info: str) -> str:
    """
    거래명세서 정보에 대한 사용자 승인을 요청합니다.

    이 tool이 호출되면 HumanInTheLoopMiddleware가 interrupt를 발생시킵니다.

    Args:
        parsed_info: 파싱된 거래명세서 정보 (포맷팅된 문자열)

    Returns:
        승인 결과 메시지
    """
    return "✅ 거래명세서 정보가 승인되었습니다. 이제 즉시 generate_product_document tool을 호출하여 문서를 생성하세요."
