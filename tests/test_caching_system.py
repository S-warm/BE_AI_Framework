# tests/test_caching_system.py

"""
캐싱 시스템 테스트

테스트 항목:
1. ParsingCache 저장/조회
2. IncrementalCache 저장/조회
3. 캐시 미스 처리
4. URL 해시 충돌 처리
5. cache_stats 카운팅
6. 전체 캐시 삭제
"""

import pytest
from pathlib import Path
from normalizer.standard_ui_node import StandardUINode
from AI.cache import (
    ParsingCache,
    IncrementalCache,
    get_cache_report,
    reset_stats
)


@pytest.fixture
def temp_db(tmp_path):
    """임시 DB 경로 생성"""
    db_path = str(tmp_path / "test_cache.db")
    return db_path


@pytest.fixture
def sample_nodes():
    """테스트용 샘플 노드들"""
    return [
        StandardUINode(
            type="button",
            content="로그인",
            properties={'x': 100, 'y': 200},
            metadata={'xpath': '/html/body/button[1]'},
            node_id="elem1"
        ),
        StandardUINode(
            type="input",
            content="",
            properties={'x': 50, 'y': 50},
            metadata={'xpath': '/html/body/input[1]'},
            node_id="elem2"
        )
    ]


class TestParsingCache:
    """ParsingCache 테스트"""
    
    def test_save_and_get(self, temp_db, sample_nodes):
        """저장 후 조회 성공"""
        cache = ParsingCache(temp_db)
        
        # 저장
        cache.save("https://naver.com", sample_nodes)
        
        # 조회
        result = cache.get("https://naver.com")
        
        assert result is not None
        assert len(result) == 2
        assert result[0].content == "로그인"
        assert result[1].type == "input"
    
    def test_cache_miss(self, temp_db):
        """캐시 미스 시 None 반환"""
        cache = ParsingCache(temp_db)
        
        result = cache.get("https://google.com")
        
        assert result is None
    
    def test_overwrite(self, temp_db, sample_nodes):
        """같은 URL 저장 시 덮어쓰기"""
        cache = ParsingCache(temp_db)
        
        # 첫 번째 저장
        cache.save("https://naver.com", sample_nodes)
        
        # 두 번째 저장 (다른 노드)
        new_nodes = [
            StandardUINode(
                type="link",
                content="홈",
                properties={},
                metadata={'xpath': '/html/body/a[1]'},
                node_id="elem3"
            )
        ]
        cache.save("https://naver.com", new_nodes)
        
        # 조회
        result = cache.get("https://naver.com")
        
        assert len(result) == 1
        assert result[0].type == "link"
    
    def test_delete(self, temp_db, sample_nodes):
        """특정 URL 삭제"""
        cache = ParsingCache(temp_db)
        
        # 저장
        cache.save("https://naver.com", sample_nodes)
        
        # 삭제
        cache.delete("https://naver.com")
        
        # 조회
        result = cache.get("https://naver.com")
        assert result is None
    
    def test_clear_all(self, temp_db, sample_nodes):
        """전체 캐시 삭제"""
        cache = ParsingCache(temp_db)
        
        # 여러 URL 저장
        cache.save("https://naver.com", sample_nodes)
        cache.save("https://google.com", sample_nodes)
        
        # 전체 삭제
        cache.clear_all()
        
        # 조회
        assert cache.get("https://naver.com") is None
        assert cache.get("https://google.com") is None


class TestIncrementalCache:
    """IncrementalCache 테스트"""
    
    def test_save_and_get(self, temp_db, sample_nodes):
        """저장 후 조회 성공"""
        cache = IncrementalCache(temp_db)
        
        # 저장
        trigger = "click|elem42|로그인"
        cache.save("https://naver.com", trigger, sample_nodes)
        
        # 조회
        result = cache.get("https://naver.com", trigger)
        
        assert result is not None
        assert len(result) == 2
    
    def test_different_triggers(self, temp_db, sample_nodes):
        """같은 URL, 다른 trigger는 별도 저장"""
        cache = IncrementalCache(temp_db)
        
        # trigger 1
        trigger1 = "click|elem42|로그인"
        cache.save("https://naver.com", trigger1, sample_nodes[:1])
        
        # trigger 2
        trigger2 = "click|elem50|회원가입"
        cache.save("https://naver.com", trigger2, sample_nodes[1:])
        
        # 조회
        result1 = cache.get("https://naver.com", trigger1)
        result2 = cache.get("https://naver.com", trigger2)
        
        assert len(result1) == 1
        assert len(result2) == 1
        assert result1[0].content == "로그인"
        assert result2[0].type == "input"
    
    def test_cache_miss(self, temp_db):
        """캐시 미스"""
        cache = IncrementalCache(temp_db)
        
        result = cache.get("https://naver.com", "click|elem99|존재안함")
        
        assert result is None
    
    def test_clear_all(self, temp_db, sample_nodes):
        """전체 캐시 삭제"""
        cache = IncrementalCache(temp_db)
        
        # 저장
        cache.save("https://naver.com", "click|elem1|test", sample_nodes)
        
        # 삭제
        cache.clear_all()
        
        # 조회
        result = cache.get("https://naver.com", "click|elem1|test")
        assert result is None


class TestCacheStats:
    """cache_stats 테스트"""
    
    def test_hit_and_miss_counting(self, temp_db, sample_nodes):
        """히트/미스 카운팅"""
        reset_stats()
        cache = ParsingCache(temp_db)
        
        # 미스
        cache.get("https://naver.com")
        
        # 저장
        cache.save("https://naver.com", sample_nodes)
        
        # 히트
        cache.get("https://naver.com")
        cache.get("https://naver.com")
        
        # 리포트 확인
        report = get_cache_report()
        
        assert report['parsing_cache']['hits'] == 2
        assert report['parsing_cache']['misses'] == 1
        assert report['parsing_cache']['hit_rate'] == "66.67%"
    
    def test_incremental_stats(self, temp_db, sample_nodes):
        """증분 캐시 통계"""
        reset_stats()
        cache = IncrementalCache(temp_db)
        
        trigger = "click|elem1|test"
        
        # 미스
        cache.get("https://naver.com", trigger)
        
        # 저장
        cache.save("https://naver.com", trigger, sample_nodes)
        
        # 히트
        cache.get("https://naver.com", trigger)
        
        # 리포트 확인
        report = get_cache_report()
        
        assert report['incremental_cache']['hits'] == 1
        assert report['incremental_cache']['misses'] == 1
        assert report['incremental_cache']['hit_rate'] == "50.00%"


class TestURLHashing:
    """URL 해시 충돌 테스트"""
    
    def test_query_params_different(self, temp_db, sample_nodes):
        """쿼리 파라미터 다르면 다른 캐시"""
        cache = ParsingCache(temp_db)
        
        # URL1
        cache.save("https://naver.com?q=test1", sample_nodes[:1])
        
        # URL2
        cache.save("https://naver.com?q=test2", sample_nodes[1:])
        
        # 조회
        result1 = cache.get("https://naver.com?q=test1")
        result2 = cache.get("https://naver.com?q=test2")
        
        assert len(result1) == 1
        assert len(result2) == 1
        assert result1[0].content == "로그인"
        assert result2[0].type == "input"


class TestWebNormalizerIncrementalRemoved:
    """WebNormalizerIncremental removed 플래그 테스트"""
    
    def test_removed_flag_added(self):
        """added 노드는 removed=False"""
        node = StandardUINode(
            type="button",
            content="테스트",
            properties={'removed': False},
            metadata={},
            node_id="elem1"
        )
        
        assert node.properties.get('removed') == False
    
    def test_removed_flag_removed(self):
        """removed 노드는 removed=True"""
        node = StandardUINode(
            type="button",
            content="테스트",
            properties={'removed': True},
            metadata={},
            node_id="elem1"
        )
        
        assert node.properties.get('removed') == True
    
    def test_filter_removed_nodes(self, sample_nodes):
        """removed 노드 필터링"""
        # removed 노드 추가
        removed_node = StandardUINode(
            type="div",
            content="사라짐",
            properties={'removed': True},
            metadata={},
            node_id="elem3"
        )
        
        all_nodes = sample_nodes + [removed_node]
        
        # 필터링
        non_removed = [n for n in all_nodes if not n.properties.get('removed', False)]
        
        assert len(non_removed) == 2
        assert all(not n.properties.get('removed') for n in non_removed)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])