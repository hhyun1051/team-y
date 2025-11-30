"""
Document Generation Tools

DOCX 템플릿 기반 문서 생성 및 PDF 변환 도구
"""

from langchain_core.tools import tool
from agents.document_generator import DocumentGenerator


@tool
def generate_delivery_document(name: str, phone: str, address: str) -> str:
    """
    승인된 운송장 정보로 DOCX 및 PDF 문서를 생성합니다.

    Args:
        name: 수령인 이름
        phone: 전화번호
        address: 배송 주소

    Returns:
        생성된 문서 경로
    """
    try:
        result = DocumentGenerator.generate_delivery_document(name, phone, address)
        return f"""✅ 운송장 생성 완료!

**생성된 파일:**
- DOCX: {result['docx']}
- PDF: {result['pdf']}

**문서 내용:**
- 수령인: {name}
- 전화번호: {phone}
- 배송 주소: {address}"""
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
