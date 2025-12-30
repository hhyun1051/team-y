#!/usr/bin/env python3
"""
Business Registration SubGraph Integration Test
"""
import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent))

from agents.graph.state import BusinessRegistrationInfo
from database.postgres import insert_registration, get_by_erp_code

# 테스트 데이터 (State 모델 그대로)
test_info = BusinessRegistrationInfo(
    client_name="테스트 거래처",
    business_name="테스트 상호",
    representative_name="홍길동",
    business_number="123-45-67891",
    branch_number="12345",
    postal_code="123-456",
    address1="서울시 강남구 테헤란로",
    address2="123번지",
    business_type="도소매",
    business_item="알루미늄",
    phone1="02-1234-5678",
    phone2="02-8765-4321",
    fax="02-1111-2222",
    contact_person1="김담당",
    mobile1="010-1234-5678",
    contact_person2="이담당",
    mobile2="010-9876-5432",
    client_type="I",
    price_grade="O",
    initial_balance=100000,
    optimal_balance=500000,
    memo="테스트 메모",
    confidence=0.98,
    image_url="https://example.com/test.jpg"
)

try:
    print("=" * 80)
    print("Business Registration SubGraph Integration Test")
    print("=" * 80)

    # 1. State 모델 → dict 변환
    print("\n[1] Converting BusinessRegistrationInfo to dict...")
    data = test_info.model_dump()
    data['discord_user_id'] = 'test_user_123'
    data['discord_message_id'] = 'test_channel_456'
    print(f"✅ Converted {len(data)} fields")

    # 2. DB 저장
    print("\n[2] Saving to database...")
    result = insert_registration(data)
    erp_code = result['erp_code']
    record_id = result['id']
    print(f"✅ Saved successfully!")
    print(f"   - Record ID: {record_id}")
    print(f"   - ERP Code: {erp_code}")

    # 3. DB 조회
    print(f"\n[3] Retrieving from database (ERP Code: {erp_code})...")
    retrieved = get_by_erp_code(erp_code)
    if retrieved:
        print(f"✅ Retrieved successfully!")
        print(f"   - 거래처명: {retrieved['client_name']}")
        print(f"   - 상호: {retrieved['business_name']}")
        print(f"   - 사업자번호: {retrieved['business_number']}")
        print(f"   - 거래처구분: {retrieved['client_type']}")
        print(f"   - 출고가등급: {retrieved['price_grade']}")
        print(f"   - Status: {retrieved['status']}")
        print(f"   - Created: {retrieved['created_at']}")
    else:
        print("❌ Retrieval failed")

    # 4. 필드 검증
    print("\n[4] Validating fields...")
    assert retrieved['client_name'] == test_info.client_name
    assert retrieved['business_name'] == test_info.business_name
    assert retrieved['representative_name'] == test_info.representative_name
    assert retrieved['business_number'] == test_info.business_number
    assert retrieved['client_type'] == test_info.client_type
    assert retrieved['price_grade'] == test_info.price_grade
    assert retrieved['initial_balance'] == test_info.initial_balance
    assert retrieved['optimal_balance'] == test_info.optimal_balance
    assert retrieved['confidence'] == test_info.confidence
    assert retrieved['image_url'] == test_info.image_url
    assert retrieved['discord_user_id'] == 'test_user_123'
    print(f"✅ All fields validated!")

    # 5. 중복 체크 테스트
    print("\n[5] Testing duplicate business_number check...")
    from database.postgres import get_by_business_number
    existing = get_by_business_number(test_info.business_number)
    if existing:
        print(f"✅ Duplicate check working!")
        print(f"   - Found existing record: ERP Code {existing['erp_code']}")
    else:
        print("❌ Duplicate check failed")

    # 6. 정리
    print("\n[6] Cleaning up test data...")
    import psycopg2
    from database.postgres.db import DB_CONFIG
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("DELETE FROM business_registrations WHERE client_name = %s", (test_info.client_name,))
    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Test data deleted")

    print("\n" + "=" * 80)
    print("✅ All integration tests passed!")
    print("=" * 80)

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
