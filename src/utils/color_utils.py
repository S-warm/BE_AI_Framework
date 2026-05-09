#src/AI/layer_tier1/utils/color_utils.py

"""
색상 변환 및 거리 계산 유틸리티
RGB → LAB 변환 (D65 표준)
"""

import math
from typing import Optional, Tuple

def parse_rgb(color_string: str) -> Optional[Tuple[int, int, int]]:
    """
    색상 문자열 → RGB 튜플
    
    지원 형식:
    - "rgb(255, 0, 0)"
    - "rgba(255, 0, 0, 0.5)"
    - "#ff0000"
    
    Returns:
        (R, G, B) 튜플 (0-255) 또는 None
    """
    try:
        # rgb(r, g, b) 또는 rgba(r, g, b, a)
        if 'rgb' in color_string:
            # "rgb(255, 0, 0)" → "255, 0, 0"
            values = color_string.split('(')[1].split(')')[0]
            # "255, 0, 0" → [255, 0, 0]
            rgb = [int(x.strip()) for x in values.split(',')[:3]]
            return tuple(rgb)
        
        # #RRGGBB
        elif color_string.startswith('#'):
            hex_color = color_string.lstrip('#')
            # "ff0000" → (255, 0, 0)
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        return None
        
    except:
        return None
    
# =====================================================
# RGB → LAB 변환 (3단계)
# =====================================================

def rgb_to_srgb(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    """
    RGB(0-255) → 선형 RGB(0-1) 감마 보정
    
    sRGB 표준 선형화 (IEC 61966-2-1)
    
    왜 필요한가?
    모니터는 비선형(어두운 곳이 더 촘촘)
    계산은 선형 공간에서 해야 정확함
    감마 보정 = 비선형 -> 선형
    
    인간의 눈은 어두운 곳의 차이를 더 잘봄 그래서 모니터는 어두운 곳의 단계를 더 많이 세분화해서 만듬
    하지만 계산을 위해 선형 즉 밝은곳과 어두운 곳을 동일하게 단계를 나눔
    """
    def linearize(c: int) -> float:
        # 1. 0-255 → 0-1 범위로 변환
        v = c / 255.0
        
        # 2. 감마 보정 (비선형 → 선형)
        if v <= 0.04045:
            # 어두운 영역 : 단순 나누기
            return v / 12.92
        else:
            # 밝은 영역 : 지수 변환
            return ((v + 0.055) / 1.055) ** 2.4
    
    # R, G, B 각각 변환
    return tuple(linearize(c) for c in rgb)


def srgb_to_xyz(srgb: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """
    선형 RGB → XYZ (D65 변환 행렬)
    
    IEC 61966-2-1 표준 행렬
    
    XYZ 란?
    RGB : 모니터 기준
    XYZ : 인간 눈 기준
    LAB으로 가기 위한 중간 단계
    """
    r, g, b = srgb
    
    # D65 변환 행렬 적용
    x = 0.4124 * r + 0.3576 * g + 0.1805 * b
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = 0.0193 * r + 0.1192 * g + 0.9505 * b
    
    # 100 스케일로 변환
    return (x * 100, y * 100, z * 100)

def xyz_to_lab(xyz: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """
    XYZ → LAB (CIE 1976)
    
    D65 기준점:
    - Xn = 95.047
    - Yn = 100.000
    - Zn = 108.883
    
    L : 밝기
    a : 초록 - 빨강
    b : 파랑 - 노랑
    """
    # D65 기준점 (표준 흰색)
    xn, yn, zn = 95.047, 100.000, 108.883
    
    x, y, z = xyz
    
    # 정규화 (기준점 대비 비율)
    x = x / xn
    y = y / yn
    z = z / zn
    
    # f(t) 함수 정의 : 밝은 영역 - 세제곱근(비선형), 어두운영역 : 선형 근사 (인간 눈의 밝기 인식 특성)
    def f(t: float) -> float:
        threshold = (6/29) ** 3  # 약 0.008856
        
        if t > threshold:
            # 밝은 영역: 세제곱근
            return t ** (1/3)
        else:
            # 어두운 영역: 선형 근사
            return (1/3) * ((29/6) ** 2) * t + 4/29
    
    # f 함수 적용
    fx = f(x)
    fy = f(y)
    fz = f(z)
    
    # LAB 계산
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b = 200 * (fy - fz)
    
    return (L, a, b)

def calculate_color_component_weight(rgb: Tuple[int, int, int]) -> float:
    """
    RGB 채널별 인지 가중치 (반응시간 기반)
    
    논문 근거:
    - 빨강(Red): 207.88ms → 가중치 1.00
    - 초록(Green): 218.24ms → 가중치 0.97
    - 파랑(Blue): 224.39ms → 가중치 0.93
    
    Args:
        rgb: (R, G, B) 튜플 (0-255)
    
    Returns:
        0.93 ~ 1.00 (빨강 성분 많을수록 높음)
    
    예시:
        (255, 0, 0) → 1.00 (순수 빨강)
        (0, 0, 255) → 0.93 (순수 파랑)
        (128, 128, 128) → 0.97 (회색, 균등)
    """
    R, G, B = rgb
    wR, wG, wB = 1.00, 0.97, 0.93
    
    # 0~1 정규화
    Rn = R / 255.0
    Gn = G / 255.0
    Bn = B / 255.0
    
    total = Rn + Gn + Bn
    if total == 0:
        return 0.0
    
    # 채널별 가중합
    return (Rn * wR + Gn * wG + Bn * wB) / total

# =====================================================
# 통합 함수
# =====================================================

def rgb_to_lab(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    """
    RGB → LAB 전체 변환
    
    Args:
        rgb: (R, G, B) 튜플 (0-255)
    
    Returns:
        (L, a, b) 튜플
        - L: 0-100 (밝기)
        - a: -128~127 (초록↔빨강)
        - b: -128~127 (파랑↔노랑)
    """
    # 1단계: RGB → 선형 RGB
    srgb = rgb_to_srgb(rgb)
    
    # 2단계: 선형 RGB → XYZ
    xyz = srgb_to_xyz(srgb)
    
    # 3단계: XYZ → LAB
    lab = xyz_to_lab(xyz)
    
    return lab

def calculate_delta_e(color1: str, color2: str) -> float:
    """
    두 색상의 LAB 거리 (ΔE)
    ΔE = √[(L₁-L₂)² + (a₁-a₂)² + (b₁-b₂)²] 유클리드 거리 공식
    
    Args:
        color1, color2: 색상 문자열 (rgb/hex)
        예: "rgb(255,0,0)", "#ff0000"
    
    Returns:
        0-2:    거의 같음
        2-10:   약간 다름
        10-50:  명확히 다름
        50+:    완전 다른 색
        100+:   정반대 색
    """
    # 1. 문자열 → RGB 튜플
    rgb1 = parse_rgb(color1)
    rgb2 = parse_rgb(color2)
    
    # 파싱 실패 시 거리 0
    if not rgb1 or not rgb2:
        return 0.0
    
    # 2. RGB → LAB
    lab1 = rgb_to_lab(rgb1)
    lab2 = rgb_to_lab(rgb2)
    
    # 3. 유클리드 거리
    delta_e = math.sqrt(
        (lab1[0] - lab2[0]) ** 2 +  # L 차이
        (lab1[1] - lab2[1]) ** 2 +  # a 차이
        (lab1[2] - lab2[2]) ** 2    # b 차이
    )
    
    return delta_e