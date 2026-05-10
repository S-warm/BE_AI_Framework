#src/AI/layer_tier1/pre_attentive/preattentive.py

"""
Pre-attentive Processing Layer
시각적 우선순위 자동 계산 (색상, 크기, 굵기, 숫자)
색상 >> 크기 > 굵기 ≈ 숫자 (임의 가중치)

Wolfe Guided Search 6.0 (2021) 논문에 의하면 pre-attentive에 굵기나 숫자 부분은 없음
나중에 논문 쓸때 Weight/Number는 일단 넣되, 논문에 "exploratory"라고 명시

LAB와 RGB 가중치의 곱셈으로 산출
ex) 빨강 배경에 빨강 버튼은 RGB 가충치가 높아도 대비가 0이라 안보임 -> 흰색 배경에 빨강 버튼은 둘 다 높아서 제일 튐
"""

from typing import List, Tuple
import sys
import os

# 프로젝트 루트 경로 추가
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
sys.path.insert(0, project_root)

from utils.color_utils import (
    parse_rgb,
    calculate_delta_e,
    calculate_color_component_weight
)
from normalizer.standard_ui_node import StandardUINode


# ============================================ 기본 가중치 ==================================================

DEFAULT_WEIGHTS = {
    # 임의 가중치임
    'color': 0.6,    # 압도적
    'size': 0.25,    # 중요
    'weight': 0.1,   # 보조
    'number': 0.05   # 특수
}

# ============================================= 헬퍼 함수 ==================================================

def calculate_average_size(nodes: List[StandardUINode]) -> float:
    """
    전체 노드의 평균 font_size 계산
    
    Args:
        nodes: StandardUINode 리스트
    
    Returns:
        평균 font_size (기본값: 16.0)
    """
    sizes = [
        n.properties.get('font_size', 0)
        for n in nodes
        if n.properties.get('font_size', 0) > 0
    ]
    
    if not sizes:
        return 16.0  # 기본값 (일반적인 본문 크기)
    
    return sum(sizes) / len(sizes)

def calculate_average_weight(nodes: List[StandardUINode]) -> float:
    """
    전체 노드의 평균 font_weight 계산
    
    Args:
        nodes: StandardUINode 리스트
    
    Returns:
        평균 font_weight (기본값: 400.0)
    """
    weights = []
    
    for n in nodes:
        w = n.properties.get('font_weight', 'normal')
        
        # 문자열 → 숫자 변환
        if isinstance(w, str):
            if w == 'bold':
                w = 700
            elif w == 'normal':
                w = 400
            elif w == 'lighter':
                w = 300
            else:
                w = 400  # 기본값
        else:
            w = int(w)
        
        weights.append(w)
    
    if not weights:
        return 400.0  # 기본값 (normal)
    
    return sum(weights) / len(weights)

# ======================================================== 함수 목록 ==========================================================

# ======================= 색상 ======================
def calculate_page_average_color(
    nodes: List[StandardUINode], 
    viewport_size: Tuple[int, int],
    method: str = 'body_only'
) -> Tuple[int, int, int]:
    """
    페이지 평균 배경색 계산 (면적 가중 평균)
    
    페이지 평균 배경색 구하기
            ↓
    1. body 태그 찾기 → 배경색 추출 → 가중치 50% 부여
    2. 큰 container들 찾기 → 각 면적만큼 가중치 부여
    3. 모든 색상을 면적 비율로 평균 내기
    
    body 가중치 50%
    container 30% 기준
    이것도 임의 값임 나중에 실험해보고 변경 @@@@@
    
    메소드 3개 있음 body만 container만 평균 계산 나중에 실험하고 메소드 하나 선택
    """
    
    if method == 'body_only':
        # === Method A: body만 ===
        for node in nodes:
            if node.metadata.get('html_tag') == 'body':
                bg_color = node.properties.get('background_color')
                if bg_color:
                    rgb = parse_rgb(bg_color)
                    if rgb:
                        return rgb
        return (255, 255, 255)
    
    elif method == 'largest':
        # === Method B: 가장 큰 container ===
        largest_area = 0
        largest_rgb = (255, 255, 255)
        
        for node in nodes:
            if node.type == 'container':
                width = node.properties.get('width', 0)
                height = node.properties.get('height', 0)
                area = width * height
                
                if area > largest_area:
                    bg_color = node.properties.get('background_color')
                    if bg_color:
                        rgb = parse_rgb(bg_color)
                        if rgb:
                            largest_area = area
                            largest_rgb = rgb
        
        return largest_rgb
    
    elif method == 'weighted':
        # === Method C: 면적 가중 평균 ===
        viewport_w, viewport_h = viewport_size
        viewport_area = viewport_w * viewport_h
        
        weighted_colors = []  # [(rgb, weight), ...]
        
        # Step 1: body (가중치 50%)
        for node in nodes:
            if node.metadata.get('html_tag') == 'body':
                bg_color = node.properties.get('background_color')
                if bg_color:
                    rgb = parse_rgb(bg_color)
                    if rgb:
                        weighted_colors.append((rgb, viewport_area * 0.5))
                break
        
        # Step 2: 큰 container들 (viewport 30% 이상)
        for node in nodes:
            if node.type != 'container':
                continue
            
            width = node.properties.get('width', 0)
            height = node.properties.get('height', 0)
            area = width * height
            
            # viewport 30% 이상만
            if area < viewport_area * 0.3:
                continue
            
            bg_color = node.properties.get('background_color')
            if bg_color:
                rgb = parse_rgb(bg_color)
                if rgb:
                    weighted_colors.append((rgb, area))
        
        # Step 3: 가중 평균
        if not weighted_colors:
            return (255, 255, 255)
        
        total_weight = sum(w for _, w in weighted_colors)
        
        R_avg = sum(rgb[0] * w for rgb, w in weighted_colors) / total_weight
        G_avg = sum(rgb[1] * w for rgb, w in weighted_colors) / total_weight
        B_avg = sum(rgb[2] * w for rgb, w in weighted_colors) / total_weight
        
        return (int(R_avg), int(G_avg), int(B_avg))
    
    else:
        # 기본값
        return (255, 255, 255)

def calculate_color_priority(
    node: StandardUINode,
    page_avg_rgb: Tuple[int, int, int]
) -> float:
    """
    색상 우선순위 = LAB 대비 × RGB 인지 가중치
    
    Args:
        node: 대상 노드
        page_avg_rgb: 페이지 평균 배경색
    
    Returns:
        0.0 ~ 1.0 색상 우선순위
        - 높을수록: 배경과 대비되면서 뇌가 빨리 반응하는 색
    
    로직:
        1. 배경색 우선, 없으면 글자색
        2. LAB 거리 계산 (대비)
        3. RGB 가중치 계산 (반응속도)
        4. 곱셈
    """
    
    # === Step 1: 노드 색상 추출 ===
    
    # 이미지 노드 처리
    if node.type in ['IMAGE', 'ICON']:
        if node.image_analysis and node.image_analysis.get('dominant_color'):
            # PIL이 추출한 dominant_color 사용
            r, g, b = node.image_analysis['dominant_color']
            target_color = f"rgb({r}, {g}, {b})"
        else:
            # dominant_color 없음 (콘텐츠 이미지 or Vision API 실패)
            return 0.5  # 중립값
    else:
        # 텍스트/컨테이너 노드
        node_bg = node.properties.get('background_color')
        node_fg = node.properties.get('color')
        target_color = node_bg if node_bg else node_fg
        
        if not target_color:
            return 0.0
    
    # === Step 2: LAB 대비 계산 ===
    # 페이지 평균 RGB → 문자열 변환
    page_avg_str = f"rgb({page_avg_rgb[0]}, {page_avg_rgb[1]}, {page_avg_rgb[2]})"
    
    # ΔE 계산 (0 ~ 100+)
    delta_e = calculate_delta_e(target_color, page_avg_str)
    
    # 0~1 정규화 (100 이상은 1.0으로 cap)
    contrast_score = min(delta_e / 100.0, 1.0)
    
    # === Step 3: RGB 인지 가중치 ===
    rgb = parse_rgb(target_color)
    if not rgb:
        return 0.0
    
    rgb_weight = calculate_color_component_weight(rgb)
    # 0.93 ~ 1.00 (파랑 ~ 빨강)
    
    # === Step 4: 최종 점수 (곱셈) ===
    priority = contrast_score * rgb_weight
    
    return priority

# ===================== 크기 ======================
def calculate_size_priority(
    node: StandardUINode,
    avg_size: float,
    method: str = 'relative'
) -> float:
    """
    Tier 1: 크기 우선순위
    
    Args:
        node: 대상 노드
        avg_size: 전체 페이지 평균 font_size (미리 계산됨)
        method: 
            - 'relative': 페이지 평균 대비
            - 'absolute': 절대값 기준
    """
    
    font_size = node.properties.get('font_size', 0)
    
    if font_size == 0:
        return 0.0
    
    if method == 'absolute':
        # 절대값 기준
        if font_size >= 48:
            return 1.0
        elif font_size >= 36:
            return 0.9
        elif font_size >= 24:
            return 0.7
        elif font_size >= 18:
            return 0.5
        elif font_size >= 14:
            return 0.3
        else:
            return 0.1
    
    else:  # 'relative'
        # 상대값 기준 (파라미터로 받은 avg_size 사용)
        ratio = font_size / avg_size
        
        if ratio >= 2.0:
            return 1.0
        elif ratio >= 1.5:
            return 0.9
        elif ratio >= 1.2:
            return 0.7
        elif ratio >= 1.0:
            return 0.5
        elif ratio >= 0.8:
            return 0.3
        else:
            return 0.1

# ===================== 굵기 ======================
def calculate_weight_priority(
    node: StandardUINode,
    avg_weight: float
) -> float:
    """
    Tier 1: 굵기 우선순위
    
    Args:
        node: 대상 노드
        avg_weight: 전체 페이지 평균 font_weight (미리 계산됨)
    
    Returns:
        0.0 ~ 1.0 굵기 우선순위
    
    주의:
        - Pre-attentive feature 아님 (논문 근거 없음)
        - 보조적 역할
    """
    
    # === Step 1: font_weight 추출 ===
    font_weight = node.properties.get('font_weight', 'normal')
    
    # 문자열 → 숫자 변환
    if isinstance(font_weight, str):
        if font_weight == 'bold':
            font_weight = 700
        elif font_weight == 'normal':
            font_weight = 400
        elif font_weight == 'lighter':
            font_weight = 300
        else:
            font_weight = 400  # 기본값
    else:
        font_weight = int(font_weight)
    
    # === Step 2: 상대 비율 ===
    ratio = font_weight / avg_weight
    
    # === Step 3: 정규화 ===
    if ratio >= 1.5:
        return 1.0
    elif ratio >= 1.2:
        return 0.7
    elif ratio >= 1.0:
        return 0.5
    elif ratio >= 0.8:
        return 0.3
    else:
        return 0.1

# ===================== 숫자 ======================

def calculate_number_priority(
    node: StandardUINode
) -> float:
    """
    Tier 1: 숫자 포함 우선순위
    
    Args:
        node: 대상 노드
    
    Returns:
        0.0 ~ 1.0 숫자 우선순위
        - 1.0: 숫자 포함
        - 0.0: 숫자 없음
    
    로직:
        content에 숫자(0-9) 포함 여부
    
    주의:
        - Semantic feature (Wolfe: guidance 안 함)
        - 특수 케이스 (가격, 카운트다운 등)
        - 실험으로 효과 검증 필요
    """
    
    import re
    
    content = node.content
    
    if not content:
        return 0.0
    
    # 숫자 포함 여부 (0-9)
    if re.search(r'\d', content):
        return 1.0
    else:
        return 0.0

# ===================== 통합 우선순위 ======================
def calculate_visual_priority(
    node: StandardUINode,
    avg_size: float,
    avg_weight: float,
    page_bg_color: tuple,
    weights: dict = None,
    method_config: dict = None
) -> float:
    """
    Tier 1: 최종 시각적 우선순위 (통합)
    
    Args:
        node: 대상 노드
        avg_size: 전체 페이지 평균 font_size
        avg_weight: 전체 페이지 평균 font_weight
        page_bg_color: 페이지 배경색 (R, G, B)
        weights: 가중치 딕셔너리
        method_config: 메서드 설정
    
    Returns:
        0.0 ~ 1.0 최종 우선순위
    """
    
    # === Step 1: 기본값 설정 ===
    if weights is None:
        weights = {
            'color': 0.6,
            'size': 0.25,
            'weight': 0.1,
            'number': 0.05
        }
    
    if method_config is None:
        method_config = {
            'size_method': 'relative',
            'bg_method': 'body_only'
        }
    
    # === Step 2: 각 feature 점수 계산 ===
    
    # 2-1. 색상 우선순위
    color_score = calculate_color_priority(
        node=node,
        page_avg_rgb=page_bg_color
    )
    
    # 2-2. 크기 우선순위
    size_score = calculate_size_priority(
        node=node,
        avg_size=avg_size,
        method=method_config['size_method']
    )
    
    # 2-3. 굵기 우선순위
    weight_score = calculate_weight_priority(
        node=node,
        avg_weight=avg_weight
    )
    
    # 2-4. 숫자 우선순위
    number_score = calculate_number_priority(node)
    
    # === Step 3: 가중 합산 ===
    final_priority = (
        color_score * weights['color'] +
        size_score * weights['size'] +
        weight_score * weights['weight'] +
        number_score * weights['number']
    )
    
    # === Step 4: 블러/투명도 패널티 ===
    opacity = node.properties.get('opacity', 1.0)
    filter_val = node.properties.get('filter', '')
    
    if opacity < 0.5:
        final_priority *= opacity
    
    if 'blur' in filter_val:
        final_priority *= 0.2
    
    # === Step 5: 범위 제한 (0.0 ~ 1.0) ===
    final_priority = max(0.0, min(1.0, final_priority))
    
    return final_priority

#======================= 메인 함수 ===========================

def apply_preattentive_priority(
    nodes: List[StandardUINode],
    viewport_size: tuple = (1920, 1080),
    weights: dict = None,
    method_config: dict = None,
    cached_stats: dict = None  # ← 추가
) -> tuple:  # ← 반환 타입 변경 (List → tuple)
    """
    전체 노드에 pre-attentive 우선순위 적용
    
    Args:
        nodes: StandardUINode 리스트
        viewport_size: 뷰포트 크기
        weights: 가중치 (None이면 기본값)
        method_config: 메서드 설정
        cached_stats: 캐시된 통계 (증분 파싱용) {
            'avg_size': float,
            'avg_weight': float,
            'page_bg': tuple
        }
    
    Returns:
        (nodes, stats): 
            - nodes: 우선순위가 추가된 노드 리스트
            - stats: 통계 딕셔너리 (캐싱용)
    
    사용:
        # 전체 파싱
        nodes, stats = apply_preattentive_priority(nodes)
        incremental.cached_stats = stats
        
        # 증분 파싱
        delta, _ = apply_preattentive_priority(delta, cached_stats=incremental.cached_stats)
    """
    
    # === Step 1: 기본값 설정 ===
    if method_config is None:
        method_config = {
            'bg_method': 'body_only',
            'size_method': 'relative'
        }
    
    # === Step 2: 통계 계산 or 재사용 ===
    if cached_stats:
        # 증분 파싱: 캐시 재사용
        avg_size = cached_stats['avg_size']
        avg_weight = cached_stats['avg_weight']
        page_bg = cached_stats['page_bg']
    else:
        # 전체 파싱: 새로 계산
        avg_size = calculate_average_size(nodes)
        avg_weight = calculate_average_weight(nodes)
        page_bg = calculate_page_average_color(
            nodes=nodes,
            viewport_size=viewport_size,
            method=method_config['bg_method']
        )
    
    # === Step 3: 각 노드에 우선순위 계산 ===
    for node in nodes:
        priority = calculate_visual_priority(
            node=node,
            avg_size=avg_size,
            avg_weight=avg_weight,
            page_bg_color=page_bg,
            weights=weights,
            method_config=method_config
        )
        
        # === Step 3.5: 인터랙션 요소 보너스 / 컨테이너 패널티 ===
        INTERACTIVE_TYPES = {'button', 'link', 'input', 'select', 'textarea', 'checkbox', 'radio', 'image'}
        if node.type in INTERACTIVE_TYPES:
            priority *= 2.0
        elif node.type == 'container':
            priority *= 0.3
        
        # 범위 제한
        priority = max(0.0, min(1.0, priority))
        
        # properties에 추가
        node.properties['visual_priority'] = priority
        
        #print(f"[DEBUG] {node.id} | type:{node.type} | priority:{priority:.3f} | tier 예정")
    
    # === Step 4: 통계 반환 (캐싱용) ===
    stats = {
        'avg_size': avg_size,
        'avg_weight': avg_weight,
        'page_bg': page_bg
    }
    
    return nodes, stats



"""
변경 가중치 종류
1. 색상 안에서 컨테이너/바디/상대
2. 크기가 필요한가 -> 이것도 절대와 상대 기준
3. 굵기, 숫자가 필요한가
"""