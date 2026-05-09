# src/AI/navigation_AI/cache/__init__.py

"""
캐싱 시스템

- ParsingCache: 전체 파싱 결과 캐싱
- IncrementalCache: 증분 파싱 결과 캐싱
- cache_stats: 통계 수집 및 리포트
"""

from AI.cache.init_db import init_database
from AI.cache.parsing_cache import ParsingCache
from AI.cache.incremental_cache import IncrementalCache
from AI.cache.cache_stats import (
    increment_hit,
    increment_miss,
    get_cache_report,
    reset_stats,
    print_cache_report
)

__all__ = [
    'init_database',
    'ParsingCache',
    'IncrementalCache',
    'increment_hit',
    'increment_miss',
    'get_cache_report',
    'reset_stats',
    'print_cache_report'
]