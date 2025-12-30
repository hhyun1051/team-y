"""
사업자등록증 정보 파서 (Vision LLM 기반)

이미지에서 사업자등록증 필드를 추출합니다.
"""

from typing import Tuple, Optional
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from agents.graph.state import BusinessRegistrationInfo


class BusinessRegistrationParser:
    """사업자등록증 파서 (Vision LLM)"""

    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.0):
        """
        BusinessRegistrationParser 초기화

        Args:
            model_name: 사용할 Vision LLM 모델 (gpt-4o 또는 gpt-4o-mini)
            temperature: 모델 temperature
        """
        system_prompt = """당신은 사업자등록증 OCR 및 정보 추출 전문가입니다.

사업자등록증 이미지에서 다음 정보를 정확하게 추출하세요:

**필수 필드:**
- client_name: 거래처명 (사업자등록증의 상호와 동일하거나 사용자가 지정)
- business_name: 상호

**선택 필드:**
- representative_name: 대표자명
- business_number: 사업자등록번호 (형식: XXX-XX-XXXXX, 반드시 하이픈(-) 포함)
- branch_number: 종사업자번호 (숫자만, 있는 경우에만)
- postal_code: 우편번호 (형식: XXX-XXX, 7자)
- address1: 주소1 (시/도, 구/군, 동 등 기본 주소)
- address2: 주소2 (상세 주소, 건물번호 등)
- business_type: 업태 (예: 유통, 도소매, 제조업 등)
- business_item: 종목 (예: 축산물, 가구, 금속제품 등)
- phone1: 전화번호1 (형식: XXX-XXXX-XXXX 또는 XX-XXXX-XXXX, 하이픈 포함, 최대 15자)
- phone2: 전화번호2 (형식 동일, 있는 경우에만)
- fax: 팩스번호 (형식 동일, 있는 경우에만)
- contact_person1: 거래처담당자1 (최대 한글 15자)
- mobile1: 휴대폰1 (형식: 01X-XXXX-XXXX, 하이픈 포함, 최대 15자)
- contact_person2: 거래처담당자2 (최대 한글 15자, 있는 경우에만)
- mobile2: 휴대폰2 (형식 동일, 있는 경우에만)
- memo: 특이사항이나 추가 메모

**파싱 규칙:**
1. **사업자등록번호는 반드시 하이픈을 포함**해야 합니다 (XXX-XX-XXXXX)
2. **전화번호는 반드시 하이픈을 포함**해야 합니다
   - 02 지역번호: 02-XXXX-XXXX
   - 기타 지역번호: 0XX-XXX-XXXX 또는 0XX-XXXX-XXXX
   - 휴대폰: 010-XXXX-XXXX
3. 우편번호는 XXX-XXX 형식 (총 7자)
4. 주소는 address1(기본 주소), address2(상세 주소)로 분리
5. 담당자 정보는 이미지에 없으면 빈 값으로 남겨둠
6. client_name은 business_name과 동일하게 설정 (사용자가 나중에 편집 가능)
7. **수동 입력 필드 (LLM이 파싱하지 않음):**
   - client_type, price_grade는 None으로 설정 (사용자가 편집 단계에서 입력)
   - initial_balance, optimal_balance는 0으로 설정

**신뢰도 판단:**
- 모든 필수 필드가 명확하게 보임: 1.0
- 일부 필드가 흐릿하거나 불명확: 0.7~0.9
- 여러 필드가 읽기 어려움: 0.5 이하

**중요:**
- 이미지에서 명확하게 보이는 정보만 추출하세요
- 추측하지 마세요 - 불명확하면 해당 필드를 None으로 남겨두세요
- 숫자 형식을 정확히 지켜주세요 (하이픈 포함)
"""

        self.agent = create_agent(
            model=f"openai:{model_name}",
            tools=[],
            system_prompt=system_prompt,
            response_format=ToolStrategy(BusinessRegistrationInfo),
        )

    def parse_image(self, image_url: str) -> BusinessRegistrationInfo:
        """
        이미지에서 사업자등록증 정보 파싱

        Args:
            image_url: 사업자등록증 이미지 URL

        Returns:
            BusinessRegistrationInfo: 파싱된 사업자등록증 정보
        """
        result = self.agent.invoke({
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "다음 사업자등록증 이미지에서 모든 정보를 추출하세요:"
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        }
                    ]
                }
            ]
        })

        return result["structured_response"]

    def parse_with_validation(self, image_url: str) -> Tuple[BusinessRegistrationInfo, bool, str]:
        """
        파싱 + 검증

        Args:
            image_url: 사업자등록증 이미지 URL

        Returns:
            (BusinessRegistrationInfo, is_valid, error_message)
        """
        try:
            business_info = self.parse_image(image_url)

            # 이미지 URL 저장
            business_info.image_url = image_url

            # 필수 필드 검증
            if not business_info.client_name:
                return business_info, False, "거래처명이 누락되었습니다."
            if not business_info.business_name:
                return business_info, False, "상호가 누락되었습니다."

            # 사업자등록번호 형식 검증 (있는 경우에만)
            if business_info.business_number:
                # 하이픈 포함 여부 확인
                if "-" not in business_info.business_number:
                    return business_info, False, "사업자등록번호에 하이픈(-)이 누락되었습니다."

                # 형식 검증: XXX-XX-XXXXX
                parts = business_info.business_number.split("-")
                if len(parts) != 3 or len(parts[0]) != 3 or len(parts[1]) != 2 or len(parts[2]) != 5:
                    return business_info, False, "사업자등록번호 형식이 잘못되었습니다 (XXX-XX-XXXXX 형식이어야 합니다)."

            # 전화번호 형식 검증 (하이픈 포함 여부만 체크)
            for field_name, field_value in [
                ("전화1", business_info.phone1),
                ("전화2", business_info.phone2),
                ("팩스", business_info.fax),
                ("휴대폰1", business_info.mobile1),
                ("휴대폰2", business_info.mobile2),
            ]:
                if field_value and "-" not in field_value:
                    return business_info, False, f"{field_name}에 하이픈(-)이 누락되었습니다."

            # 신뢰도 검증
            if business_info.confidence and business_info.confidence < 0.5:
                return business_info, False, f"파싱 신뢰도가 낮습니다 ({business_info.confidence:.1%})"

            # client_name이 비어있으면 business_name으로 설정
            if not business_info.client_name and business_info.business_name:
                business_info.client_name = business_info.business_name

            return business_info, True, ""

        except Exception as e:
            return None, False, f"파싱 오류: {str(e)}"
