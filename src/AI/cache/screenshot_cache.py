"""
ScreenshotCache: 전체 페이지 스크린샷 캐싱

목적:
- URL별 전체 페이지 PNG 저장
- 프론트엔드 히트맵/페이지 뷰어용
- 길잡이 AI 실행 시 자동 캐싱

사용:
    cache = ScreenshotCache()
    
    # 저장
    cache.save("https://naver.com", png_bytes)
    
    # 조회
    png_bytes = cache.get("https://naver.com")
"""

import sqlite3
import hashlib
import re
from typing import Optional
from pathlib import Path

from AI.cache.cache_stats import increment_hit, increment_miss


class ScreenshotCache:
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            current_dir = Path(__file__).parent
            db_path = str(current_dir / "cache.db")
        
        self.db_path = db_path
        
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
            CREATE TABLE screenshot_cache (
                url_hash TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                screenshot BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def _get_url_hash(self, url: str) -> str:
        return hashlib.md5(url.encode('utf-8')).hexdigest()
    
    def get(self, url: str) -> Optional[bytes]:
        url_hash = self._get_url_hash(url)
        
        try:
            conn = self.conn if self.conn else sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT screenshot FROM screenshot_cache WHERE url_hash = ?",
                (url_hash,)
            )
            
            row = cursor.fetchone()
            
            if not self.conn:
                conn.close()
            
            if row:
                increment_hit('screenshot')
                return row[0]  # PNG bytes 그대로 반환
            else:
                increment_miss('screenshot')
                return None
        
        except Exception as e:
            print(f"⚠️ ScreenshotCache.get() 에러: {e}")
            increment_miss('screenshot')
            return None
    
    def save(self, url: str, png_bytes: bytes) -> None:
        # pickle.loads() 없이 bytes 그대로 반환하는 것. PNG는 이미 바이너리라 역직렬화 불필요
        url_hash = self._get_url_hash(url)
        
        try:
            conn = self.conn if self.conn else sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO screenshot_cache 
                (url_hash, url, screenshot)
                VALUES (?, ?, ?)
            """, (url_hash, url, png_bytes))
            
            conn.commit()
            
            if not self.conn:
                conn.close()
            
            print(f"✅ 스크린샷 캐시 저장: {url} ({len(png_bytes) // 1024}KB)")
        
        except Exception as e:
            print(f"⚠️ ScreenshotCache.save() 에러: {e}")
    
    def delete(self, url: str) -> None:
        url_hash = self._get_url_hash(url)
        
        try:
            conn = self.conn if self.conn else sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "DELETE FROM screenshot_cache WHERE url_hash = ?",
                (url_hash,)
            )
            
            conn.commit()
            
            if not self.conn:
                conn.close()
        
        except Exception as e:
            print(f"⚠️ ScreenshotCache.delete() 에러: {e}")
            
    
    def upload_to_s3(self, urls: list, uploader, date_prefix: str) -> dict:
        """지정된 URL의 스크린샷을 S3에 업로드. {url: s3_key} 반환"""
        result = {}
        for url in urls:
            png_bytes = self.get(url)
            if png_bytes is None:
                continue
            url_hash = self._get_url_hash(url)
            slug = re.sub(r'https?://', '', url)
            slug = re.sub(r'[^\w\-]', '_', slug)[:200]
            s3_key = f"raw/{date_prefix}/screenshots/{slug}.png"
            local_path = Path(f"/tmp/{url_hash}.png")
            local_path.write_bytes(png_bytes)
            if uploader.upload_file(str(local_path), s3_key):
                result[url] = s3_key
                local_path.unlink()
        return result