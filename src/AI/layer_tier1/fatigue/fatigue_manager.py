#src/AI/layer_tier1/fatigue/fatigue_manager.py

"""
Tier 1: 피로도 관리
섹션별/전역 피로도 추적 및 임계값 판단

페르소나 20대 50대 70대만 코딩 되어 있으며 이 조차 임의값으로 코딩되어 있음
피로도는 추후 아이 트레커를 통한 패턴 분석 이후 수치를 정할 수 있다고 판단 함
"""

from typing import Dict

AGE_GROUP_MAP = {
    '10s': '20s',
    '30s': '20s',
    '40s': '50s',
    '60s': '70s',
}

class FatigueManager:
    # Tier별 기본 피로도 비용
    FATIGUE_COST = {
        '상': 0.05,
        '중': 0.075,  # 1.5× 상
        '하': 0.10    # 2× 상
    }
    
    # 재방문 가중치 (v4.0)
    REVISIT_MULTIPLIER = 2.0
    
    # 페르소나별 임계값 (EXPLORATORY: pilot study 검증 필요)
    PERSONA_THRESHOLDS = {
        '20s': {'section': 1.2, 'global': 4.0},
        '50s': {'section': 0.8, 'global': 2.5},
        '70s': {'section': 0.5, 'global': 1.5}
    }
    
    def __init__(self, persona: Dict):
        """
        Args:
            persona: {
                'age_group': '20s'/'50s'/'70s'
            }
        """
        self.age_group = persona.get('age_group', '70s')
        
        # 보간 연령대 → 가장 가까운 앵커값으로 매핑
        mapped = AGE_GROUP_MAP.get(self.age_group, self.age_group)
        
        self.section_fatigue = 0.0
        self.global_fatigue = 0.0
        
        thresholds = self.PERSONA_THRESHOLDS[mapped]
        self.section_threshold = thresholds['section']
        self.global_threshold = thresholds['global']
    
    def add_fatigue(self, tier: str, is_revisit: bool = False) -> None:
        """
        피로도 추가
        
        Args:
            tier: '상'/'중'/'하'
            is_revisit: 재방문 여부 (True면 2배 비용)
        """
        # v4.0: tier별 차등 재방문 비용
        base_cost = self.FATIGUE_COST.get(tier, 0.05)
        
        if is_revisit:
            cost = base_cost * self.REVISIT_MULTIPLIER
        else:
            cost = base_cost
        
        self.section_fatigue += cost
        self.global_fatigue += cost
    
    def is_section_exhausted(self) -> bool:
        """섹션 피로도 임계값 도달 여부"""
        return self.section_fatigue >= self.section_threshold
    
    def is_globally_exhausted(self) -> bool:
        """전체 피로도 임계값 도달 여부"""
        return self.global_fatigue >= self.global_threshold
    
    def reset_section_fatigue(self) -> None:
        """섹션 전환 시 섹션 피로도 리셋"""
        self.section_fatigue = 0.0
    
    def get_current_fatigue(self) -> Dict:
        """현재 피로도 상태 반환"""
        return {
            'section_fatigue': self.section_fatigue,
            'global_fatigue': self.global_fatigue,
            'section_threshold': self.section_threshold,
            'global_threshold': self.global_threshold,
            'section_exhausted': self.is_section_exhausted(),
            'globally_exhausted': self.is_globally_exhausted()
        }