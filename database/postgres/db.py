# db.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from dotenv import load_dotenv
import logging

# 환경 변수 로드
load_dotenv()

logger = logging.getLogger(__name__)

# DB 설정 (환경변수에서 로드)
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'erp_db'),
    'user': os.getenv('POSTGRES_USER', 'erp_user'),
    'password': os.getenv('POSTGRES_PASSWORD', 'your_password')
}


@contextmanager
def get_connection():
    """
    PostgreSQL 연결 획득 (Context Manager)

    Yields:
        psycopg2.connection: DB 연결 객체

    Raises:
        psycopg2.Error: 연결 실패 시
    """
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        yield conn
    except psycopg2.Error as e:
        logger.error(f"DB 연결 실패: {e}")
        raise
    finally:
        if conn:
            conn.close()


@contextmanager
def get_cursor(conn):
    """
    커서 획득 (Context Manager)

    Args:
        conn: psycopg2 연결 객체

    Yields:
        psycopg2.cursor: RealDictCursor (결과를 dict로 반환)
    """
    cur = None
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        yield cur
    finally:
        if cur:
            cur.close()