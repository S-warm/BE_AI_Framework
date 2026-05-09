#src/AI/layer_tier1/utils/sorter.py

"""
section, element y좌표기반 정렬 함수

Y좌표 오름차순 정렬 (위→아래)
"""

from typing import List
from normalizer.standard_ui_node import StandardUINode

    
def sort_by_y_position(nodes: List[StandardUINode]) -> List[StandardUINode]:
    """
    Y좌표 오름차순 정렬 (위→아래)
        
    Args:
        nodes: StandardUINode 리스트
        
    Returns:
        Y좌표 기준 정렬된 노드 리스트
        
    Notes:
        - properties['y']가 없으면 0으로 처리
        - 동일 Y좌표는 원래 순서 유지 (stable sort)
    """
    return sorted(nodes, key=lambda n: n.properties.get('y', 0))
