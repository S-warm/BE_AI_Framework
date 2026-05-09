#src/normalizer/utils/image_vision/vision_cache.py

"""
Vision API 결과 캐싱 모듈

pHash 기반 SQLite 캐싱으로 API 호출 최소화
압축/리사이즈된 이미지도 동일 이미지로 인식
"""

from __future__ import annotations
import sqlite3
import imagehash
from PIL import Image
import io
import json
from pathlib import Path
from typing import Optional, Dict, Any


class VisionCache:
    """
    Vision API 결과를 pHash 기반으로 캐싱
    
    pHash(Perceptual Hash)를 사용하여 압축/리사이즈된 이미지도 
    동일한 이미지로 인식해서 캐시 히트율 극대화.
    
    Attributes:
        db_path: SQLite DB 파일 경로
        conn: SQLite 연결 객체
    
    Example:
        >>> cache = VisionCache()
        >>> result = cache.get(image_bytes)
        >>> if not result:
        ...     result = call_vision_api(image_bytes)
        ...     cache.set(image_bytes, result)
        >>> cache.close()
    """
    
    def __init__(self, db_path: str = "./data/vision_cache.db"):
        """
        Args:
            db_path: 캐시 DB 파일 경로
        """
        # DB 디렉토리 생성
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # SQLite 연결 (autocommit)
        self.conn = sqlite3.connect(db_path)
        self.conn.isolation_level = None  # autocommit 모드
        self.cursor = self.conn.cursor()
        
        # 테이블 생성
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS vision_cache (
                cache_key TEXT PRIMARY KEY,
                vision_result TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    def get(self, image_bytes: bytes) -> Optional[Dict[str, Any]]:
        """
        캐시에서 Vision API 결과 조회
        
        Args:
            image_bytes: 이미지 바이트 데이터
        
        Returns:
            Vision API 결과 dict 또는 None (캐시 미스)
        
        Raises:
            ValueError: 이미지 손상 등으로 캐시 키 생성 실패
        """
        cache_key = self._generate_cache_key(image_bytes)
        
        self.cursor.execute(
            "SELECT vision_result FROM vision_cache WHERE cache_key = ?",
            (cache_key,)
        )
        result = self.cursor.fetchone()
        
        return json.loads(result[0]) if result else None
    
    def set(self, image_bytes: bytes, vision_result: Dict[str, Any]):
        """
        Vision API 결과를 캐시에 저장
        
        Args:
            image_bytes: 이미지 바이트 데이터
            vision_result: Vision API 결과 dict
        
        Raises:
            ValueError: 이미지 손상 등으로 캐시 키 생성 실패
        """
        cache_key = self._generate_cache_key(image_bytes)
        vision_json = json.dumps(vision_result)
        
        self.cursor.execute(
            "INSERT OR REPLACE INTO vision_cache (cache_key, vision_result) VALUES (?, ?)",
            (cache_key, vision_json)
        )
    
    def _generate_cache_key(self, image_bytes: bytes) -> str:
        """
        pHash로 캐시 키 생성
        
        Returns:
            pHash 문자열 (16자 hex)
        
        Raises:
            ValueError: 이미지 형식 오류
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
            phash = str(imagehash.phash(img))
            return phash
        except Exception as e:
            raise ValueError(f"Failed to generate cache key: {e}") from e
    
    def close(self):
        """DB 연결 종료"""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()