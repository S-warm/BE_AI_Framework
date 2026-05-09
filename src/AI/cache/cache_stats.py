# src/AI/navigation_AI/cache/cache_stats.py

"""
캐시 통계 수집 및 리포트 생성

목적:
- ParsingCache, IncrementalCache 히트/미스 카운팅
- 시뮬레이션 종료 시 캐시 성능 리포트 생성
- 절감률 계산

사용:
    # 캐시에서 호출
    increment_hit('parsing')
    increment_miss('incremental')
    
    # 시뮬레이션 종료 시
    report = get_cache_report()
    print(report)
    # {
    #     'parsing_cache': {
    #         'hits': 850,
    #         'misses': 50,
    #         'hit_rate': '94.44%'
    #     },
    #     'incremental_cache': {
    #         'hits': 120,
    #         'misses': 30,
    #         'hit_rate': '80.00%'
    #     }
    # }
"""

from typing import Dict


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 전역 통계 변수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
cache_stats = {
    "parsing_hits": 0,
    "parsing_misses": 0,
    "incremental_hits": 0,
    "incremental_misses": 0,
    "screenshot_hits": 0,
    "screenshot_misses": 0,
}


def increment_hit(cache_type: str) -> None:
    """
    캐시 히트 카운트 증가
    
    Args:
        cache_type: 'parsing' or 'incremental'
    
    Example:
        >>> increment_hit('parsing')
        >>> cache_stats['parsing_hits']
        1
    """
    if cache_type == 'parsing':
        cache_stats["parsing_hits"] += 1
    elif cache_type == 'incremental':
        cache_stats["incremental_hits"] += 1
    elif cache_type == 'screenshot':
        cache_stats["screenshot_hits"] += 1
    else:
        raise ValueError(f"Unknown cache_type: {cache_type}")


def increment_miss(cache_type: str) -> None:
    """
    캐시 미스 카운트 증가
    
    Args:
        cache_type: 'parsing' or 'incremental'
    
    Example:
        >>> increment_miss('parsing')
        >>> cache_stats['parsing_misses']
        1
    """
    if cache_type == 'parsing':
        cache_stats["parsing_misses"] += 1
    elif cache_type == 'incremental':
        cache_stats["incremental_misses"] += 1
    elif cache_type == 'screenshot':
        cache_stats["screenshot_misses"] += 1
    else:
        raise ValueError(f"Unknown cache_type: {cache_type}")


def get_cache_report() -> Dict:
    """
    캐시 통계 리포트 생성
    
    Returns:
        {
            'parsing_cache': {
                'hits': int,
                'misses': int,
                'hit_rate': str (예: '94.44%')
            },
            'incremental_cache': {
                'hits': int,
                'misses': int,
                'hit_rate': str
            }
        }
    
    Example:
        >>> increment_hit('parsing')
        >>> increment_hit('parsing')
        >>> increment_miss('parsing')
        >>> report = get_cache_report()
        >>> print(report['parsing_cache']['hit_rate'])
        '66.67%'
    """
    # Parsing Cache
    total_parsing = cache_stats["parsing_hits"] + cache_stats["parsing_misses"]
    parsing_hit_rate = (
        cache_stats["parsing_hits"] / total_parsing * 100 
        if total_parsing > 0 else 0
    )
    
    # Incremental Cache
    total_incremental = cache_stats["incremental_hits"] + cache_stats["incremental_misses"]
    incremental_hit_rate = (
        cache_stats["incremental_hits"] / total_incremental * 100 
        if total_incremental > 0 else 0
    )
    
    return {
        "parsing_cache": {
            "hits": cache_stats["parsing_hits"],
            "misses": cache_stats["parsing_misses"],
            "hit_rate": f"{parsing_hit_rate:.2f}%"
        },
        "incremental_cache": {
            "hits": cache_stats["incremental_hits"],
            "misses": cache_stats["incremental_misses"],
            "hit_rate": f"{incremental_hit_rate:.2f}%"
        }
    }


def reset_stats() -> None:
    """
    통계 초기화 (테스트용)
    
    Example:
        >>> reset_stats()
        >>> cache_stats
        {'parsing_hits': 0, 'parsing_misses': 0, ...}
    """
    cache_stats["parsing_hits"] = 0
    cache_stats["parsing_misses"] = 0
    cache_stats["incremental_hits"] = 0
    cache_stats["incremental_misses"] = 0


def print_cache_report() -> None:
    """
    캐시 리포트 예쁘게 출력 (디버깅용)
    
    Example:
        >>> print_cache_report()
        
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        📊 캐시 성능 리포트
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        [Parsing Cache]
        - Hits: 850
        - Misses: 50
        - Hit Rate: 94.44%
        
        [Incremental Cache]
        - Hits: 120
        - Misses: 30
        - Hit Rate: 80.00%
        
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
    report = get_cache_report()
    
    print()
    print("━" * 50)
    print("📊 캐시 성능 리포트")
    print("━" * 50)
    print()
    
    # Parsing Cache
    pc = report['parsing_cache']
    print("[Parsing Cache]")
    print(f"- Hits: {pc['hits']}")
    print(f"- Misses: {pc['misses']}")
    print(f"- Hit Rate: {pc['hit_rate']}")
    print()
    
    # Incremental Cache
    ic = report['incremental_cache']
    print("[Incremental Cache]")
    print(f"- Hits: {ic['hits']}")
    print(f"- Misses: {ic['misses']}")
    print(f"- Hit Rate: {ic['hit_rate']}")
    print()
    
    print("━" * 50)