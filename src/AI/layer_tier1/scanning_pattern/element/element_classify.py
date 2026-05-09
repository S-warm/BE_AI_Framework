"""
Salience 기준 Tier 분류
"""

from typing import List
import numpy as np
from normalizer.standard_ui_node import StandardUINode


def classify_by_percentile(nodes: List[StandardUINode]) -> List[StandardUINode]:
    """
    섹션 내 노드를 salience 기준 백분위로 Tier 분류
    
    Args:
        nodes: 단일 섹션의 노드 리스트
    
    Returns:
        properties['tier'] 추가된 노드 리스트
        - '상': 상위 30% (percentile 70 이상)
        - '중': 30~70% (percentile 30~70)
        - '하': 하위 30% (percentile 30 미만)
    
    Notes:
        - EXPLORATORY: 30/70 백분위 기준은 pilot study 검증 필요
        - 노드 3개 미만이면 전부 '상' 처리
        - Salience는 properties['visual_priority']에서 가져옴
    """
    if not nodes:
        return nodes
    
    # 노드 3개 미만이면 전부 '상'
    if len(nodes) < 3:
        for node in nodes:
            node.properties['tier'] = '상'
        return nodes
    
    # Salience 추출
    saliences = [n.properties.get('visual_priority', 0) for n in nodes]
    
    # 백분위 계산
    tier_상_min = np.percentile(saliences, 70)  # 상위 30% 시작점
    tier_중_min = np.percentile(saliences, 30)  # 중간 tier 시작점
    
    # Tier 할당
    for node in nodes:
        salience = node.properties.get('visual_priority', 0)
        
        if salience >= tier_상_min:
            node.properties['tier'] = '상'
        elif salience >= tier_중_min:
            node.properties['tier'] = '중'
        else:
            node.properties['tier'] = '하'
    
    return nodes