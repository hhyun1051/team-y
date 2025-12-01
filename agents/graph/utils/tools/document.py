"""
Document Generation Tools

DOCX 템플릿 기반 문서 생성 및 PDF 변환 도구
"""

from langchain_core.tools import tool
from ..document_generator import DocumentGenerator


@tool
def generate_delivery_document(
    unloading_site: str,
    address: str,
    contact: str,
    payment_type: str,
    loading_site: str = "유진알루미늄",
    loading_address: str = None,
    loading_phone: str = None,
    freight_cost: int = None,
    notes: str = None
) -> str:
    """
    승인된 운송장 정보로 DOCX 및 PDF 문서를 생성합니다.

    Args:
        unloading_site: 하차지 (회사 이름)
        address: 주소 (상세 주소)
        contact: 연락처
        payment_type: 운송비 지불 방법 ("착불" 또는 "선불")
        loading_site: 상차지 (기본값: "유진알루미늄")
        loading_address: 상차지 주소 (선택)
        loading_phone: 상차지 전화번호 (선택)
        freight_cost: 운송비 (착불일 경우에만, 원 단위)
        notes: 비고 (선택)

    Returns:
        생성된 문서 경로
    """
    try:
        result = DocumentGenerator.generate_delivery_document(
            unloading_site=unloading_site,
            address=address,
            contact=contact,
            payment_type=payment_type,
            loading_site=loading_site,
            loading_address=loading_address,
            loading_phone=loading_phone,
            freight_cost=freight_cost,
            notes=notes
        )

        if payment_type == "착불" and freight_cost:
            payment_display = f"{payment_type} ({freight_cost:,}원)"
        else:
            payment_display = payment_type

        return f"""✅ 운송장 생성 완료!

**생성된 파일:**
- DOCX: {result['docx']}
- PDF: {result['pdf']}

**문서 내용:**
- 하차지: {unloading_site}
- 주소: {address}
- 연락처: {contact}
- 상차지: {loading_site}
- 운송비: {payment_display}
- 비고: {notes if notes else '없음'}"""
    except Exception as e:
        return f"❌ 운송장 생성 실패: {str(e)}"


@tool
def generate_product_document(client: str, product_name: str, quantity: int, unit_price: int) -> str:
    """
    승인된 거래명세서 정보로 DOCX 및 PDF 문서를 생성합니다.

    Args:
        client: 거래처
        product_name: 품목
        quantity: 수량
        unit_price: 단가

    Returns:
        생성된 문서 경로
    """
    try:
        result = DocumentGenerator.generate_product_order_document(client, product_name, quantity, unit_price)
        total_price = quantity * unit_price
        return f"""✅ 거래명세서 생성 완료!

**생성된 파일:**
- DOCX: {result['docx']}
- PDF: {result['pdf']}

**문서 내용:**
- 거래처: {client}
- 품목: {product_name}
- 수량: {quantity}개
- 단가: {unit_price:,}원
- 합계: {total_price:,}원"""
    except Exception as e:
        return f"❌ 거래명세서 생성 실패: {str(e)}"
