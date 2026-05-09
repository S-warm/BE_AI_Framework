# src/AI/navigation_AI/cache/init_db.py

"""
SQLite 캐싱 데이터베이스 초기화

목적:
- 파싱 캐시 테이블 생성 (전체 파싱)
- 증분 캐시 테이블 생성 (증분 파싱)
- 인덱스 생성 (빠른 조회)

ex)

-- parsing_cache
id | url_hash                         | url                | parsed_nodes | created_at
---+----------------------------------+--------------------+--------------+------------
1  | a3f8d9e2b1c4...                 | https://naver.com  | <blob>       | 2025-04-06
2  | b4e9c1f3d2a5...                 | https://google.com | <blob>       | 2025-04-06

-- incremental_cache
id | trigger_hash                     | base_url           | trigger_action        | delta_nodes | created_at
---+----------------------------------+--------------------+-----------------------+-------------+------------
1  | c5a1f4e3b2d9...                 | https://naver.com  | click|elem42|로그인   | <blob>      | 2025-04-06
"""

import sqlite3
from pathlib import Path


def init_database(db_path: str = None) -> None:
    """
    SQLite 데이터베이스 초기화
    
    - parsing_cache 테이블 생성
    - incremental_cache 테이블 생성
    - 인덱스 생성
    
    Args:
        db_path: DB 파일 경로 (기본값: cache 폴더 내 cache.db)
    
    Example:
        >>> init_database()
        # src/AI/navigation_AI/cache/cache.db 생성
        
        >>> init_database("/tmp/test_cache.db")
        # 커스텀 경로에 생성
    """
    # 기본 경로: 현재 파일과 같은 폴더
    if db_path is None:
        current_dir = Path(__file__).parent
        db_path = str(current_dir / "cache.db")
    
    # DB 연결 (파일 없으면 자동 생성)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1. parsing_cache 테이블 (전체 파싱) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parsing_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_hash TEXT NOT NULL UNIQUE,
            url TEXT NOT NULL,
            parsed_nodes BLOB NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 인덱스: url_hash로 빠른 조회
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_parsing_url_hash 
        ON parsing_cache(url_hash)
    """)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 2. incremental_cache 테이블 (증분 파싱) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incremental_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_hash TEXT NOT NULL UNIQUE,
            base_url TEXT NOT NULL,
            trigger_action TEXT NOT NULL,
            delta_nodes BLOB NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 인덱스: trigger_hash로 빠른 조회
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_incremental_trigger_hash 
        ON incremental_cache(trigger_hash)
    """)
    
# ============================================= 3. screenshot_cache 테이블 =============================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS screenshot_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_hash TEXT NOT NULL UNIQUE,
            url TEXT NOT NULL,
            screenshot BLOB NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_screenshot_url_hash 
        ON screenshot_cache(url_hash)
    """)
    
    # 커밋 및 종료
    conn.commit()
    conn.close()
    
    print(f"✅ Database initialized: {db_path}")


if __name__ == "__main__":
    # 직접 실행 시 초기화
    init_database()