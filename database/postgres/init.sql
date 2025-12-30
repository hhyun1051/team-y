-- init.sql
-- State 모델(BusinessRegistrationInfo)과 필드명 통일

CREATE SEQUENCE erp_code_seq START 50001 MAXVALUE 99999;

CREATE TABLE business_registrations (
    id SERIAL PRIMARY KEY,
    erp_code INTEGER UNIQUE NOT NULL DEFAULT nextval('erp_code_seq'),

    -- 필수 필드 (State 모델 기준)
    client_name VARCHAR(200) NOT NULL,          -- 거래처명 (필수)
    business_name VARCHAR(200) NOT NULL,        -- 상호 (필수)

    -- 선택 필드 (LLM 파싱)
    representative_name VARCHAR(100),            -- 대표자명
    business_number VARCHAR(20) UNIQUE,          -- 사업자등록번호 (형식: XXX-XX-XXXXX, 중복 불가)
    branch_number VARCHAR(20),                   -- 종사업자번호
    postal_code VARCHAR(10),                     -- 우편번호 (형식: XXX-XXX)
    address1 VARCHAR(300),                       -- 주소1
    address2 VARCHAR(300),                       -- 주소2
    business_type VARCHAR(100),                  -- 업태
    business_item VARCHAR(200),                  -- 종목
    phone1 VARCHAR(15),                          -- 전화1
    phone2 VARCHAR(15),                          -- 전화2
    fax VARCHAR(15),                             -- 팩스
    contact_person1 VARCHAR(50),                 -- 거래처담당자1
    mobile1 VARCHAR(15),                         -- 휴대폰1
    contact_person2 VARCHAR(50),                 -- 거래처담당자2
    mobile2 VARCHAR(15),                         -- 휴대폰2
    memo TEXT,                                   -- 메모

    -- 편집 필수 필드
    client_type VARCHAR(1) CHECK (client_type IN ('I', 'O', 'M')),  -- 거래처구분: I(매입처), O(매출처), M(기타)
    price_grade VARCHAR(1) CHECK (price_grade IN ('O', 'Z', 'N', 'E')),  -- 출고가등급: O(별도), Z(영세), N(면세), E(없음)
    initial_balance INTEGER DEFAULT 0 NOT NULL,  -- 기초잔액
    optimal_balance INTEGER DEFAULT 0 NOT NULL,  -- 적정잔액

    -- 메타데이터
    confidence FLOAT,                            -- 파싱 신뢰도 (0.0~1.0)
    image_url TEXT,                              -- 원본 이미지 URL

    -- 상태 관리
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    discord_user_id VARCHAR(50),
    discord_message_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    processed_at TIMESTAMP
);

-- 인덱스
CREATE INDEX idx_status ON business_registrations(status);
CREATE INDEX idx_business_number ON business_registrations(business_number) WHERE business_number IS NOT NULL;
CREATE INDEX idx_client_name ON business_registrations(client_name);
CREATE INDEX idx_created_at ON business_registrations(created_at DESC);