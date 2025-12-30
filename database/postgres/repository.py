# repository.py
from .db import get_connection, get_cursor
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def insert_registration(data: dict) -> dict:
    """
    새 거래처 등록, erp_code 자동 생성

    Args:
        data: BusinessRegistrationInfo를 dict로 변환한 데이터
              (필드명이 State 모델과 동일해야 함)

    Returns:
        dict: {'id': int, 'erp_code': int}

    Raises:
        ValueError: 필수 필드 누락 시
        psycopg2.IntegrityError: 사업자번호 중복 등
    """
    # 필수 필드 검증
    required_fields = ['client_name', 'business_name']
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields:
        raise ValueError(f"필수 필드 누락: {', '.join(missing_fields)}")

    # 모든 선택 필드의 기본값 설정
    defaults = {
        'representative_name': None,
        'business_number': None,
        'branch_number': None,
        'postal_code': None,
        'address1': None,
        'address2': None,
        'business_type': None,
        'business_item': None,
        'phone1': None,
        'phone2': None,
        'fax': None,
        'contact_person1': None,
        'mobile1': None,
        'contact_person2': None,
        'mobile2': None,
        'client_type': None,
        'price_grade': None,
        'initial_balance': 0,
        'optimal_balance': 0,
        'memo': None,
        'confidence': None,
        'image_url': None,
        'discord_user_id': None,
        'discord_message_id': None
    }

    # 기본값과 병합
    full_data = {**defaults, **data}

    try:
        with get_connection() as conn:
            with get_cursor(conn) as cur:
                cur.execute('''
                    INSERT INTO business_registrations (
                        client_name, business_name, representative_name,
                        business_number, branch_number,
                        postal_code, address1, address2,
                        business_type, business_item,
                        phone1, phone2, fax,
                        contact_person1, mobile1, contact_person2, mobile2,
                        client_type, price_grade,
                        initial_balance, optimal_balance, memo,
                        confidence, image_url,
                        discord_user_id, discord_message_id
                    ) VALUES (
                        %(client_name)s, %(business_name)s, %(representative_name)s,
                        %(business_number)s, %(branch_number)s,
                        %(postal_code)s, %(address1)s, %(address2)s,
                        %(business_type)s, %(business_item)s,
                        %(phone1)s, %(phone2)s, %(fax)s,
                        %(contact_person1)s, %(mobile1)s, %(contact_person2)s, %(mobile2)s,
                        %(client_type)s, %(price_grade)s,
                        %(initial_balance)s, %(optimal_balance)s, %(memo)s,
                        %(confidence)s, %(image_url)s,
                        %(discord_user_id)s, %(discord_message_id)s
                    )
                    RETURNING id, erp_code
                ''', full_data)
                result = cur.fetchone()
                conn.commit()
                logger.info(f"거래처 등록 성공: id={result['id']}, erp_code={result['erp_code']}, client_name={data.get('client_name')}")
                return result
    except Exception as e:
        logger.error(f"거래처 등록 실패: {e}, data={data.get('client_name')}")
        raise

def fetch_pending_job() -> Optional[dict]:
    """
    pending 작업 하나 가져오면서 processing으로 변경

    Returns:
        dict: 작업 레코드 (모든 필드 포함) 또는 None
    """
    try:
        with get_connection() as conn:
            with get_cursor(conn) as cur:
                cur.execute('''
                    UPDATE business_registrations
                    SET status = 'processing'
                    WHERE id = (
                        SELECT id FROM business_registrations
                        WHERE status = 'pending'
                        ORDER BY created_at
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    )
                    RETURNING *
                ''')
                result = cur.fetchone()
                conn.commit()
                if result:
                    logger.info(f"작업 가져옴: id={result['id']}, client_name={result.get('client_name')}")
                return result
    except Exception as e:
        logger.error(f"작업 가져오기 실패: {e}")
        raise


def update_status(record_id: int, status: str) -> None:
    """
    작업 상태 업데이트

    Args:
        record_id: 레코드 ID
        status: 새 상태 (pending/processing/completed/failed)
    """
    try:
        with get_connection() as conn:
            with get_cursor(conn) as cur:
                cur.execute('''
                    UPDATE business_registrations
                    SET status = %s, processed_at = NOW()
                    WHERE id = %s
                ''', (status, record_id))
                conn.commit()
                logger.info(f"상태 업데이트: id={record_id}, status={status}")
    except Exception as e:
        logger.error(f"상태 업데이트 실패: id={record_id}, status={status}, error={e}")
        raise


def get_by_business_number(business_number: str) -> Optional[dict]:
    """
    사업자번호로 조회 (중복 체크용)

    Args:
        business_number: 사업자등록번호

    Returns:
        dict: 레코드 또는 None
    """
    try:
        with get_connection() as conn:
            with get_cursor(conn) as cur:
                cur.execute('''
                    SELECT * FROM business_registrations
                    WHERE business_number = %s
                    LIMIT 1
                ''', (business_number,))
                result = cur.fetchone()
                return result
    except Exception as e:
        logger.error(f"사업자번호 조회 실패: {business_number}, error={e}")
        raise


def get_by_erp_code(erp_code: int) -> Optional[dict]:
    """
    ERP 코드로 조회

    Args:
        erp_code: ERP 코드

    Returns:
        dict: 레코드 또는 None
    """
    try:
        with get_connection() as conn:
            with get_cursor(conn) as cur:
                cur.execute('''
                    SELECT * FROM business_registrations
                    WHERE erp_code = %s
                    LIMIT 1
                ''', (erp_code,))
                result = cur.fetchone()
                return result
    except Exception as e:
        logger.error(f"ERP 코드 조회 실패: {erp_code}, error={e}")
        raise


def update_registration(record_id: int, data: dict) -> bool:
    """
    거래처 정보 수정

    Args:
        record_id: 레코드 ID
        data: 업데이트할 필드 dict

    Returns:
        bool: 성공 여부
    """
    try:
        # 동적으로 UPDATE 쿼리 생성
        allowed_fields = {
            'client_name', 'business_name', 'representative_name',
            'business_number', 'branch_number', 'postal_code',
            'address1', 'address2', 'business_type', 'business_item',
            'phone1', 'phone2', 'fax', 'contact_person1', 'mobile1',
            'contact_person2', 'mobile2', 'client_type', 'price_grade',
            'initial_balance', 'optimal_balance', 'memo'
        }

        update_data = {k: v for k, v in data.items() if k in allowed_fields}
        if not update_data:
            return False

        set_clause = ', '.join([f"{field} = %({field})s" for field in update_data.keys()])

        with get_connection() as conn:
            with get_cursor(conn) as cur:
                query = f'''
                    UPDATE business_registrations
                    SET {set_clause}
                    WHERE id = %(record_id)s
                '''
                update_data['record_id'] = record_id
                cur.execute(query, update_data)
                conn.commit()
                logger.info(f"거래처 정보 수정 성공: id={record_id}, fields={list(update_data.keys())}")
                return True
    except Exception as e:
        logger.error(f"거래처 정보 수정 실패: id={record_id}, error={e}")
        raise