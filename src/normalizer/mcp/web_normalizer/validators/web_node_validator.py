#src/normalizer/mcp/web_normalizer/validation/web_node_validator.py

from typing import Dict, Any

class WebNodeValidator:
    """
    파싱 전 필요없는 내용 제거
    """
    
    # 제외할 태그 목록 (렌더링 안되는 태그들 제외)
    EXCLUDED_TAGS = {
        'script',   # JavaScript 코드
        'style',    # CSS 코드
        'meta',     # 메타데이터
        'link',     # 외부 리소스
        'head',     # HTML 헤더
        'noscript'  # JS 비활성화 메시지
    }
    
    @staticmethod
    def _is_valid_node(raw_data: Dict[str, Any]) -> bool:
        """
        렌더링된 요소인지만 체크 (최소한의 필터링)
        Playwright isVisible() 로직 재현
        
        필터링 조건:
        1. 메타데이터 태그 (script, style, meta 등)
        2. non-empty bounding box
        3. visibility !== hidden (본인만 체크, 부모는 JS에서 이미 처리)
        4. 너무 작은 요소 (1x1 추적 픽셀)
        5. 화면 밖 요소
        
        주의: opacity:0은 visible로 간주 (Playwright 기준)
        """
        
        try:
            # 1. 메타데이터 태그 제외
            tag_name = raw_data.get('tag', '').lower()
            if tag_name in WebNodeValidator.EXCLUDED_TAGS:
                return False
            
            # 2. bounding box 존재 여부
            rect = raw_data.get('rect', {})
            if not rect:
                return False
            
            width = rect.get('width', 0)
            height = rect.get('height', 0)
            x = rect.get('x', 0)
            y = rect.get('y', 0)
            
            # 3. non-empty bounding box
            if width <= 0 or height <= 0:
                return False
            
            # 4. 너무 작은 요소 제외 (1x1 추적 픽셀)
            if width < 2 or height < 2:
                return False
            
            # 5. 화면 밖 요소 제외
            if x < -1000 or y < -1000:
                return False
            
            # 6. visibility: hidden 체크
            styles = raw_data.get('styles', {})
            visibility = styles.get('visibility', '')
            if visibility == 'hidden':
                return False
            
            # 투명도 처리 (0.1 미만은 인지하기 어려우므로 제외)
            opacity = styles.get('opacity', 1)
            if opacity < 0.1: # 기존 로직과 동일하게 추가
                return False
            
            # 주의: display:none은 체크 안 함 (이미 bounding box가 empty)
            # 주의: opacity:0은 제외 안 함 (Playwright는 visible로 간주)
            
            return True
        
        except:
            return False