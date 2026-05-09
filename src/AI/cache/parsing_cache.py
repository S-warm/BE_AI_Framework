# src/AI/navigation_AI/cache/parsing_cache.py

"""
ParsingCache: 전체 파싱 결과 캐싱

목적:
- URL별 전체 DOM 파싱 결과 저장
- 같은 페이지 재방문 시 파싱 스킵
- 900번 시뮬레이션에서 파싱 비용 96% 절감

사용:
    cache = ParsingCache()
    
    # 조회
    nodes = cache.get("https://naver.com")
    if nodes:
        # 캐시 히트
    else:
        # 캐시 미스 → 파싱 후 저장
        nodes = normalizer.normalize(page)
        cache.save("https://naver.com", nodes)
"""

import sqlite3
import hashlib
import pickle
from typing import List, Optional
from pathlib import Path

from normalizer.standard_ui_node import StandardUINode
from AI.cache.cache_stats import increment_hit, increment_miss


class ParsingCache:
    """
    전체 파싱 결과 캐싱
    
    저장 구조:
    - 키: URL의 MD5 해시
    - 값: List[StandardUINode] (pickle 직렬화)
    - 저장소: SQLite
    """
    
    def __init__(self, db_path: str = None):
        """
        초기화
        
        Args:
            db_path: SQLite DB 파일 경로 (기본값: cache/cache.db)
        
        Example:
            >>> cache = ParsingCache()
            # cache/cache.db 사용
            
            >>> cache = ParsingCache("/tmp/test_cache.db")
            # 커스텀 경로
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
        """메모리 DB 테이블 생성"""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE parsing_cache (
                url_hash TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                parsed_nodes BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
    
    def _get_url_hash(self, url: str) -> str:
        """
        URL → MD5 해시
        
        Args:
            url: 전체 URL (쿼리 포함)
        
        Returns:
            32자 해시 문자열
        
        Example:
            >>> self._get_url_hash("https://naver.com?q=test")
            'a3f8d9e2b1c4f5a6...'
        """
        return hashlib.md5(url.encode('utf-8')).hexdigest()
    
    def get(self, url: str) -> Optional[List[StandardUINode]]:
        """
        캐시 조회
        
        Args:
            url: 조회할 URL
        
        Returns:
            캐시된 노드 리스트 or None (캐시 미스)
        
        Example:
            >>> nodes = cache.get("https://naver.com")
            >>> if nodes:
            ...     print(f"캐시 히트: {len(nodes)}개 노드")
            ... else:
            ...     print("캐시 미스")
        """
        url_hash = self._get_url_hash(url)
        
        try:
            conn = self.conn if self.conn else sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT parsed_nodes FROM parsing_cache WHERE url_hash = ?",
                (url_hash,)
            )
            
            row = cursor.fetchone()
            
            if not self.conn:  # 파일 DB만 닫기
                conn.close()
            
            if row:
                # 캐시 히트
                increment_hit('parsing')
                parsed_nodes = pickle.loads(row[0])
                return parsed_nodes
            else:
                # 캐시 미스
                increment_miss('parsing')
                return None
        
        except Exception as e:
            print(f"⚠️ ParsingCache.get() 에러: {e}")
            increment_miss('parsing')
            return None
    
    def save(self, url: str, nodes: List[StandardUINode]) -> None:
        """
        파싱 결과 저장
        
        Args:
            url: URL
            nodes: 파싱된 노드 리스트
        
        Example:
            >>> nodes = normalizer.normalize(page)
            >>> cache.save("https://naver.com", nodes)
            ✅ 캐시 저장: https://naver.com (50개 노드)
        """
        url_hash = self._get_url_hash(url)
        
        try:
            # pickle 직렬화
            serialized = pickle.dumps(nodes)
            
            conn = self.conn if self.conn else sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # UPSERT (있으면 업데이트, 없으면 삽입)
            cursor.execute("""
                INSERT OR REPLACE INTO parsing_cache 
                (url_hash, url, parsed_nodes)
                VALUES (?, ?, ?)
            """, (url_hash, url, serialized))
            
            conn.commit()
            
            if not self.conn:  # 파일 DB만 닫기
                conn.close()
            
            print(f"✅ 캐시 저장: {url} ({len(nodes)}개 노드)")
        
        except Exception as e:
            print(f"⚠️ ParsingCache.save() 에러: {e}")
    
    def delete(self, url: str) -> None:
        """
        특정 URL 캐시 삭제
        
        Args:
            url: 삭제할 URL
        
        Example:
            >>> cache.delete("https://naver.com")
        """
        url_hash = self._get_url_hash(url)
        
        try:
            conn = self.conn if self.conn else sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "DELETE FROM parsing_cache WHERE url_hash = ?",
                (url_hash,)
            )
            
            conn.commit()
            
            if not self.conn:  # 파일 DB만 닫기
                conn.close()
        
        except Exception as e:
            print(f"⚠️ ParsingCache.delete() 에러: {e}")
    
    def clear_all(self) -> None:
        """
        전체 캐시 삭제
        
        Example:
            >>> cache.clear_all()
            ✅ 전체 캐시 삭제 완료
        """
        try:
            conn = self.conn if self.conn else sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM parsing_cache")
            
            conn.commit()
            
            if not self.conn:  # 파일 DB만 닫기
                conn.close()
            
            print("✅ 전체 캐시 삭제 완료")
        
        except Exception as e:
            print(f"⚠️ ParsingCache.clear_all() 에러: {e}")