# src/AI/navigation_AI/cache/incremental_cache.py

"""
IncrementalCache: 증분 파싱 결과 캐싱

목적:
- trigger별 증분 파싱 결과 저장
- 같은 액션(클릭) 시 증분 파싱 스킵
- 예: "로그인 버튼 클릭 → 모달" 결과를 900번 재사용

사용:
    cache = IncrementalCache()
    
    # 조회
    trigger = "click|elem42|로그인"
    delta = cache.get("https://naver.com", trigger)
    if delta:
        # 캐시 히트
    else:
        # 캐시 미스 → 증분 파싱 후 저장
        delta = normalizer.normalize_incremental(page)
        cache.save("https://naver.com", trigger, delta)
"""

import sqlite3
import hashlib
import pickle
from typing import List, Optional
from pathlib import Path

from normalizer.standard_ui_node import StandardUINode
from AI.cache.cache_stats import increment_hit, increment_miss


class IncrementalCache:
    """
    증분 파싱 결과 캐싱
    
    저장 구조:
    - 키: (base_url + trigger)의 MD5 해시
    - 값: List[StandardUINode] (pickle 직렬화)
    - 저장소: SQLite
    """
    
    def __init__(self, db_path: str = None):
        """
        초기화
        
        Args:
            db_path: SQLite DB 파일 경로 (기본값: cache/cache.db)
        
        Example:
            >>> cache = IncrementalCache()
        """
        if db_path is None:
            current_dir = Path(__file__).parent
            db_path = str(current_dir / "cache.db")
        
        self.db_path = db_path
        
        # :memory:면 연결 유지
        if db_path == ":memory:":
            self.conn = sqlite3.connect(":memory:")
            self._init_memory_tables()
        else:
            self.conn = None
            if not Path(db_path).exists():
                from AI.cache.init_db import init_database
                init_database(db_path)
    
    def _init_memory_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incremental_cache (
                trigger_hash TEXT PRIMARY KEY,
                base_url TEXT NOT NULL,
                trigger_action TEXT NOT NULL,
                delta_nodes BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
    
    def _get_trigger_hash(self, base_url: str, trigger: str) -> str:
        """
        (base_url + trigger) → MD5 해시
        
        Args:
            base_url: 페이지 URL
            trigger: "click|elem42|로그인"
        
        Returns:
            32자 해시 문자열
        
        Example:
            >>> self._get_trigger_hash(
            ...     "https://naver.com",
            ...     "click|elem42|로그인"
            ... )
            'c5a1f4e3b2d9...'
        """
        trigger_key = f"{base_url}|{trigger}"
        return hashlib.md5(trigger_key.encode('utf-8')).hexdigest()
    
    def get(self, base_url: str, trigger: str) -> Optional[List[StandardUINode]]:
        """
        캐시 조회
        
        Args:
            base_url: 페이지 URL
            trigger: "click|elem42|로그인"
        
        Returns:
            캐시된 delta 노드 리스트 or None (캐시 미스)
        
        Example:
            >>> delta = cache.get("https://naver.com", "click|elem42|로그인")
            >>> if delta:
            ...     print(f"캐시 히트: {len(delta)}개 증분 노드")
        """
        trigger_hash = self._get_trigger_hash(base_url, trigger)
        
        try:
            conn = self.conn if self.conn else sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT delta_nodes FROM incremental_cache WHERE trigger_hash = ?",
                (trigger_hash,)
            )
            
            row = cursor.fetchone()
            
            if not self.conn:
                conn.close()
            
            if row:
                # 캐시 히트
                increment_hit('incremental') 
                delta_nodes = pickle.loads(row[0])
                return delta_nodes
            else:
                # 캐시 미스
                increment_miss('incremental')
                return None
        
        except Exception as e:
            print(f"⚠️ IncrementalCache.get() 에러: {e}")
            increment_miss('incremental') 
            return None
    
    def save(self, base_url: str, trigger: str, delta: List[StandardUINode]) -> None:
        """
        증분 파싱 결과 저장
        
        Args:
            base_url: 페이지 URL
            trigger: "click|elem42|로그인"
            delta: 증분 노드 리스트
        
        Example:
            >>> delta = normalizer.normalize_incremental(page)
            >>> cache.save("https://naver.com", "click|elem42|로그인", delta)
            ✅ 증분 캐시 저장: https://naver.com | click|elem42|로그인 (3개 노드)
        """
        trigger_hash = self._get_trigger_hash(base_url, trigger)
        
        try:
            # pickle 직렬화
            serialized = pickle.dumps(delta)
            
            conn = self.conn if self.conn else sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # UPSERT
            cursor.execute("""
                INSERT OR REPLACE INTO incremental_cache 
                (trigger_hash, base_url, trigger_action, delta_nodes)
                VALUES (?, ?, ?, ?)
            """, (trigger_hash, base_url, trigger, serialized))
            
            conn.commit()
            
            if not self.conn:
                conn.close()
            
            print(f"✅ 증분 캐시 저장: {base_url} | {trigger} ({len(delta)}개 노드)")
        
        except Exception as e:
            print(f"⚠️ IncrementalCache.save() 에러: {e}")
    
    def clear_all(self) -> None:
        """
        전체 증분 캐시 삭제
        
        Example:
            >>> cache.clear_all()
            ✅ 증분 캐시 전체 삭제 완료
        """
        try:
            conn = self.conn if self.conn else sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM incremental_cache")
            
            conn.commit()
            
            if not self.conn:
                conn.close()
            
            print("✅ 증분 캐시 전체 삭제 완료")
        
        except Exception as e:
            print(f"⚠️ IncrementalCache.clear_all() 에러: {e}")