# src/AI/layer_tier2/filters/vision_filter.py

"""
Vision Filter - 시각 인지 제약 필터

연령대별 시각 인지 수치(age_config)를 기반으로 StandardUINode 리스트를 필터링.
NavigationLoop에서 캐시 로드 직후, prompt_builder 전에 적용.

필터 순서:
1. font_size: 텍스트 노드 최소 폰트 크기 미달 제거
2. contrast: 대비비 미달 제거
3. button_size: 버튼/링크 최소 크기 미달 제거
4. icon_only: 아이콘 단독 노드 하 tier부터 비율 제거
"""

import random
from typing import List
from normalizer.standard_ui_node import StandardUINode
from AI.layer_tier2.persona.age.age_config import get_age_config

TEXT_TYPES = {'text', 'link', 'button'} # 텍스트 타입 설정 - 텍스트 필터에 사용
TIER_ORDER = ['하', '중', '상']

class VisionFilter:
    """
    연령대별 시각 제약 필터.
    
    Args:
        age_group: '10s' | '20s' | '30s' | '40s' | '50s' | '60s' | '70s'
    
    Usage:
        f = VisionFilter('70s')
        filtered_nodes = f.apply(nodes)
    """

    def __init__(self, age_group: str):
        self.age_group = age_group
        self.config = get_age_config(age_group)
        self.vision = self.config['vision']
        self.action = self.config['action_accuracy']

    def apply(self, nodes: List[StandardUINode]) -> List[StandardUINode]:
        nodes = self._filter_font_size(nodes)
        nodes = self._filter_contrast(nodes)
        nodes = self._filter_button_size(nodes)
        nodes = self._filter_icon_only(nodes)
        return nodes

    def _filter_font_size(self, nodes: List[StandardUINode]) -> List[StandardUINode]:
        """
        텍스트 노드 중 font_size가 연령대 최솟값 미달인 노드 제거.
        font_size가 None이면 이미지 버튼으로 간주하고 통과.
        image/input/select는 필터 대상 아님.
        """
        
        min_size = self.vision['min_font_size']
        return [
            node for node in nodes
            if node.type not in TEXT_TYPES
            or node.properties.get('font_size') is None  # 이미지 버튼 등
            or node.properties.get('font_size') >= min_size
        ]

    def _filter_contrast(self, nodes: List[StandardUINode]) -> List[StandardUINode]:
        """
        contrast_ratio가 연령대 최솟값 미달인 노드 제거.
        contrast_ratio가 None이면 통과 (이미지 등).
        """
        min_contrast = self.vision['min_contrast_ratio']
        return [
            node for node in nodes
            if node.properties.get('contrast_ratio') is None
            or node.properties.get('contrast_ratio') >= min_contrast
        ]

    def _filter_button_size(self, nodes: List[StandardUINode]) -> List[StandardUINode]:
        """
        버튼/링크 중 width 또는 height가 연령대 최소 버튼 크기 미달인 노드 제거.
        size 속성 없으면 통과.
        """
        min_size = self.action['min_button_size']
        result = []
        for node in nodes:
            if node.type not in ('button', 'link'):
                result.append(node)
                continue
            size = node.properties.get('size')
            if size is None:
                result.append(node)
                continue
            if size.get('width', 0) >= min_size and size.get('height', 0) >= min_size:
                result.append(node)
        return result

    def _filter_icon_only(self, nodes: List[StandardUINode]) -> List[StandardUINode]:
        """
        아이콘 단독 노드(content 없고 vision_type == 'ICON')를
        icon_only_recognition_rate 기반 비율로 제거.
        제거 순서: 하 tier → 중 tier → 상 tier.
        논문 수치 유지 (70대=80%, 50대=40%, 20대=5%).
        """
        recognition_rate = self.vision['icon_only_recognition_rate']
        remove_ratio = 1 - recognition_rate

        # 아이콘 단독 노드 분리
        icon_nodes = [
            n for n in nodes
            if not n.content.strip()
            and (getattr(n, 'image_analysis', None) or {}).get('vision_type') == 'ICON'
        ]
        non_icon_nodes = [n for n in nodes if n not in icon_nodes]

        if not icon_nodes:
            return nodes

        # 제거할 개수
        remove_count = round(len(icon_nodes) * remove_ratio)

        # 하 tier부터 제거 대상 선정
        to_remove = []
        for tier in TIER_ORDER:
            if len(to_remove) >= remove_count:
                break
            tier_nodes = [n for n in icon_nodes if n.properties.get('tier') == tier]
            needed = remove_count - len(to_remove)
            to_remove.extend(tier_nodes[:needed])

        return non_icon_nodes + [n for n in icon_nodes if n not in to_remove]