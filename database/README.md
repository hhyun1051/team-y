# Database Layer - Business Registration

사업자등록증 정보를 PostgreSQL에 저장하는 데이터베이스 레이어입니다.

## 📁 구조

```
database/
├── __init__.py
└── postgres/
    ├── __init__.py
    ├── db.py              # DB 연결 관리
    ├── repository.py      # CRUD 함수
    └── init.sql           # 테이블 스키마
```

## 🗄️ 데이터베이스 스키마

### Table: `business_registrations`

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `id` | SERIAL | PRIMARY KEY | 자동 증가 ID |
| `erp_code` | INTEGER | UNIQUE, NOT NULL | ERP 코드 (50001~99999) |
| `client_name` | VARCHAR(200) | NOT NULL | 거래처명 (필수) |
| `business_name` | VARCHAR(200) | NOT NULL | 상호 (필수) |
| `representative_name` | VARCHAR(100) | - | 대표자명 |
| `business_number` | VARCHAR(20) | UNIQUE | 사업자등록번호 |
| `branch_number` | VARCHAR(20) | - | 종사업자번호 |
| `postal_code` | VARCHAR(10) | - | 우편번호 |
| `address1` | VARCHAR(300) | - | 주소1 |
| `address2` | VARCHAR(300) | - | 주소2 |
| `business_type` | VARCHAR(100) | - | 업태 |
| `business_item` | VARCHAR(200) | - | 종목 |
| `phone1` | VARCHAR(15) | - | 전화1 |
| `phone2` | VARCHAR(15) | - | 전화2 |
| `fax` | VARCHAR(15) | - | 팩스 |
| `contact_person1` | VARCHAR(50) | - | 담당자1 |
| `mobile1` | VARCHAR(15) | - | 휴대폰1 |
| `contact_person2` | VARCHAR(50) | - | 담당자2 |
| `mobile2` | VARCHAR(15) | - | 휴대폰2 |
| `client_type` | VARCHAR(1) | CHECK (I/O/M) | 거래처구분 |
| `price_grade` | VARCHAR(1) | CHECK (O/Z/N/E) | 출고가등급 |
| `initial_balance` | INTEGER | DEFAULT 0 | 기초잔액 |
| `optimal_balance` | INTEGER | DEFAULT 0 | 적정잔액 |
| `memo` | TEXT | - | 메모 |
| `confidence` | FLOAT | - | 파싱 신뢰도 |
| `image_url` | TEXT | - | 원본 이미지 URL |
| `status` | VARCHAR(20) | DEFAULT 'pending' | 상태 |
| `discord_user_id` | VARCHAR(50) | - | Discord 사용자 ID |
| `discord_message_id` | VARCHAR(50) | - | Discord 메시지 ID |
| `created_at` | TIMESTAMP | DEFAULT NOW() | 생성일시 |
| `processed_at` | TIMESTAMP | - | 처리일시 |

### Indexes

- `idx_status`: status 컬럼 인덱스
- `idx_business_number`: business_number 컬럼 인덱스 (NULL 제외)
- `idx_client_name`: client_name 컬럼 인덱스
- `idx_created_at`: created_at 컬럼 인덱스 (DESC)

## 🔧 설정

### 환경변수 (.env)

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=erp_db
```

### 데이터베이스 초기화

```bash
# PostgreSQL 컨테이너에서 실행
docker exec postgres_db psql -U postgres -c "CREATE DATABASE erp_db;"
docker exec -i postgres_db psql -U postgres -d erp_db < database/postgres/init.sql
```

## 📚 사용 방법

### 1. Import

```python
from database.postgres import (
    insert_registration,
    get_by_erp_code,
    get_by_business_number,
    update_registration,
    fetch_pending_job,
    update_status
)
```

### 2. 거래처 등록

```python
from agents.graph.state import BusinessRegistrationInfo

# State 모델 생성
info = BusinessRegistrationInfo(
    client_name="테스트 거래처",
    business_name="테스트 상호",
    representative_name="홍길동",
    business_number="123-45-67890",
    client_type="I",
    price_grade="O"
)

# Dict 변환 및 저장
data = info.model_dump()
data['discord_user_id'] = 'user_123'

result = insert_registration(data)
print(f"ERP Code: {result['erp_code']}")  # 50001
print(f"Record ID: {result['id']}")        # 1
```

### 3. 조회

```python
# ERP 코드로 조회
record = get_by_erp_code(50001)
print(record['client_name'])  # 테스트 거래처

# 사업자번호로 조회 (중복 체크)
existing = get_by_business_number("123-45-67890")
if existing:
    print(f"이미 등록됨: ERP {existing['erp_code']}")
```

### 4. 수정

```python
update_data = {
    'client_type': 'O',
    'price_grade': 'Z',
    'memo': '수정된 메모'
}
success = update_registration(record_id=1, data=update_data)
```

### 5. 상태 업데이트

```python
# pending → processing
job = fetch_pending_job()
if job:
    # 작업 처리...
    update_status(job['id'], 'completed')
```

## 🔄 워크플로우 통합

`business_registration_subgraph.py`의 `_save_node()`에서 자동으로 DB 저장:

```python
def _save_node(state: OfficeAutomationState) -> Dict[str, Any]:
    info = state.get("business_registration_info")

    # 1. 중복 체크
    if info.business_number:
        existing = get_by_business_number(info.business_number)
        if existing:
            return {"messages": [AIMessage(content="이미 등록된 사업자번호")]}

    # 2. 저장
    data = info.model_dump()
    data['discord_user_id'] = state.get('discord_user_id')

    result = insert_registration(data)

    return {
        "messages": [AIMessage(content=f"ERP 코드: {result['erp_code']}")],
        "erp_code": result['erp_code'],
        "db_record_id": result['id']
    }
```

## ✅ 테스트

```bash
# DB 연결 테스트
python test_db.py

# 통합 테스트
python test_integration.py
```

## 🔒 보안

- ✅ 환경변수로 DB 인증 정보 관리
- ✅ SQL Injection 방지 (Parameterized Query)
- ✅ 사업자번호 중복 방지 (UNIQUE 제약)
- ✅ 트랜잭션 관리 (Context Manager)

## 📊 상태 관리

상태 값:
- `pending`: 등록 대기
- `processing`: 처리 중
- `completed`: 완료
- `failed`: 실패

## 🚀 성능

- **Connection Pooling**: 현재 미구현 (추후 psycopg2.pool 사용 권장)
- **인덱스**: 4개 (status, business_number, client_name, created_at)
- **동시성 처리**: SKIP LOCKED 사용

## 📝 TODO

- [ ] Connection Pool 구현
- [ ] 실제 ERP 시스템 연동
- [ ] 감사 로그 추가
- [ ] 소프트 삭제 구현
- [ ] 배치 삽입 최적화
