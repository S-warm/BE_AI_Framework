#src/normalizer/mcp/web_normalizer/extractors/property_extractor.py

from typing import Dict, Any
from .type_extractor import TypeExtractor

class PropertyExtractor:
    """
    raw_data에서 CSS 속성 추출 + 대비 계산
    """
    
    @staticmethod
    def _extract_properties(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        모든 CSS "속성" 추출
        인지 저하 레이어가 필터링 할 재료
        
        추출 속성:
        - 폰트: font_size, font_weight, font_family, line_height
        - 색상: color, background_color, border_color
        - 위치: x, y, width, height
        - 간격: padding, margin
        - 테두리: border_width, border_style
        - 표시: opacity, visibility, display, z_index
        - 대비: contrast_ratio
        """
        
        try:
            # JS에서 이미 계산된 속성들 가져오기
            props = raw_data.get('properties', {}).copy()
            
            # 대비 계산 (contrast_ratio) -> 의미없는 요소인 container와 image는 대비 계산 뺌
            node_type = TypeExtractor._extract_type(raw_data)
            if node_type in ['button', 'input', 'link', 'text']:
                props['contrast_ratio'] = PropertyExtractor._calculate_contrast_ratio(
                    props.get('color', ''),
                    props.get('background_color', '')
                )
            else:
                props['contrast_ratio'] = None
            
            return props
        
        except Exception as e:
            print(f"Error extracting properties: {e}")
            # 에러 시 기본값 반환
            return PropertyExtractor._get_default_properties()

    @staticmethod
    def _calculate_contrast_ratio(foreground: str, background: str) -> float:
        """
        색상 대비 계산 (WCAG 기준)
        
            foreground: 전경색 (예: "rgb(0, 0, 0)")
            background: 배경색 (예: "rgb(255, 255, 255)")
            
            대비 비율 (1-21, 높을수록 좋음)
        """

        try:
            # 1. RGB 추출
            fg_rgb = PropertyExtractor._parse_rgb(foreground) # 글씨 색
            bg_rgb = PropertyExtractor._parse_rgb(background) # 배경 색
            
            if not fg_rgb or not bg_rgb:
                return 1.0  # 파싱 실패 시 최소값
            
            # 2. 상대 휘도 계산
            fg_luminance = PropertyExtractor._get_relative_luminance(fg_rgb)
            bg_luminance = PropertyExtractor._get_relative_luminance(bg_rgb)
            
            # 3. 대비 비율 계산
            lighter = max(fg_luminance, bg_luminance)
            darker = min(fg_luminance, bg_luminance)
            
            # 0으로 나누는 것 방지하기 위해 0.05를 더한다 (같은 색도 1.0이 되도록)
            contrast = (lighter + 0.05) / (darker + 0.05)
            
            return round(contrast, 2)
            
        except:
            return 1.0

    @staticmethod
    def _parse_rgb(color_string: str) -> tuple:
        """
        RGB 추출 이후
        색상 문자열 → RGB 튜플 변환
        
        예:
        - "rgb(255, 0, 0)" → (255, 0, 0) -> 글자와 괄호 제거 -> 튜플
        - "rgba(255, 0, 0, 0.5)" → (255, 0, 0) -> 글자와 괄호 제거 -> 튜플
        - "#ff0000" → (255, 0, 0)
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

    @staticmethod
    def _get_relative_luminance(rgb: tuple) -> float:
        """
        RGB → 상대 휘도 계산 (WCAG 공식)
        
            rgb: (R, G, B) 튜플 (0-255)
            
            올바른 가중치 (WCAG 공식) = 0.2126*R + 0.7152*G + 0.0722*B
            상대 휘도 (0-1)
        """
        
        def convert_channel(channel):
            # 0-255 → 0-1 -> 0~1 값으로 조정
            c = channel / 255.0
            
            # 감마 보정 (눈의 비 선형 특성) -> 어두운 곳에서 작은 변화를 잘 감지하고 밝은 곳에서는 큰 변화가 필요함
            # ex) 0 -> 10 확밝아진 느낌 / 200 -> 210 거의 차이 못 느낌 (이걸 감마 보정으로 수식화)
            if c <= 0.03928:
                return c / 12.92
            else:
                return ((c + 0.055) / 1.055) ** 2.4
        
        r, g, b = rgb
        
        # 상대 휘도 = 0.2126*R + 0.7152*G + 0.0722*B
        luminance = (
            0.2126 * convert_channel(r) +
            0.7152 * convert_channel(g) +
            0.0722 * convert_channel(b)
        )
        
        return luminance

    @staticmethod
    def _get_default_properties() -> Dict[str, Any]:
        """에러 시 기본 속성 반환"""
        return {
            'font_size': 14,
            'font_weight': 'normal',
            'font_family': '',
            'line_height': 0,
            'color': '',
            'background_color': '',
            'border_color': '',
            'x': 0,
            'y': 0,
            'width': 0,
            'height': 0,
            'padding_top': 0,
            'padding_right': 0,
            'padding_bottom': 0,
            'padding_left': 0,
            'margin_top': 0,
            'margin_right': 0,
            'margin_bottom': 0,
            'margin_left': 0,
            'border_width': 0,
            'border_style': 'none',
            'border_radius': 0,
            'opacity': 1,
            'visibility': 'visible',
            'display': '',
            'z_index': 0,
            'cursor': 'auto',
            'text_align': 'left',
            'text_decoration': 'none',
            'background_image': 'none',
            'position': 'static',
            'contrast_ratio': 1.0
        }

