"""
BasePersona - 연령대별 페르소나 그릇

persona 관련 코드를 한 곳에 모음:
- age_config 조회
- vision_filter 적용
- FatigueManager 등 dict 받는 기존 코드 호환
"""

from typing import Dict, List
from normalizer.standard_ui_node import StandardUINode
from AI.layer_tier2.persona.age.age_config import get_age_config
from AI.layer_tier2.filters.vision_filter import VisionFilter


class BasePersona:
    def __init__(self, age_group: str):
        """
        Args:
            age_group: '10s' | '20s' | '30s' | '40s' | '50s' | '60s' | '70s'
        """
        self.age_group = age_group
        self.age_config = get_age_config(age_group)        # 연령대별 인지 제약 수치
        self.vision_filter = VisionFilter(age_group)       # 시각 인지 필터

    def to_dict(self) -> Dict:
        """
        FatigueManager 등 dict를 받는 기존 코드 호환용.
        
        Returns:
            {'age_group': '50s'}
        """
        return {'age_group': self.age_group}

    def filter_nodes(self, nodes: List[StandardUINode]) -> List[StandardUINode]:
        """
        vision_filter 적용. _process_tier1() 반환 직전에 호출.
        
        Args:
            nodes: tier 분류 + 정렬 완료된 StandardUINode 리스트
        
        Returns:
            연령대 시각 제약 기준으로 필터링된 노드 리스트
        """
        return self.vision_filter.apply(nodes)