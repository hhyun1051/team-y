#!/usr/bin/env python3
"""
Database connection test
"""
import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent))

from database.postgres import insert_registration, get_by_erp_code

# 테스트 데이터
test_data = {
    'client_name': '테스트 거래처',
    'business_name': '테스트 상호',
    'representative_name': '홍길동',
    'business_number': '123-45-67890',
    'address1': '서울시 강남구',
    'client_type': 'I',
    'price_grade': 'O',
    'initial_balance': 0,
    'optimal_balance': 0,
    'confidence': 0.95,
    'discord_user_id': 'test_user_123'
}

try:
    print("=" * 60)
    print("Database Connection Test")
    print("=" * 60)

    # 1. 삽입 테스트
    print("\n[1] Testing insert_registration()...")
    result = insert_registration(test_data)
    print(f"✅ 등록 성공!")
    print(f"   - ID: {result['id']}")
    print(f"   - ERP Code: {result['erp_code']}")

    # 2. 조회 테스트
    print(f"\n[2] Testing get_by_erp_code({result['erp_code']})...")
    retrieved = get_by_erp_code(result['erp_code'])
    if retrieved:
        print(f"✅ 조회 성공!")
        print(f"   - 거래처명: {retrieved['client_name']}")
        print(f"   - 상호: {retrieved['business_name']}")
        print(f"   - 사업자번호: {retrieved['business_number']}")
        print(f"   - Status: {retrieved['status']}")
    else:
        print("❌ 조회 실패")

    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
