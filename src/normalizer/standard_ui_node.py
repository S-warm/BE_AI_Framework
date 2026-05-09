from pydantic import BaseModel
from typing import Dict, Optional, Any

class StandardUINode(BaseModel):
    """
    모든 플랫폼에서 공통으로 사용할 UI 노드 구조
    
    Normalizer가 플랫폼별 원본 데이터를 이 구조로 변환
    인지 저하 레이어가 이 구조를 받아서 필터링
    """
    
    # 기본 정보
    id: str  # 고유 식별자 (xpath)
    type: str  # button, input, text, link, image, select 등
    content: str  # 버튼 텍스트, 입력값, 이미지 alt 등
    
    # 이미지 크기 분류 (Phase 1-C)
    image_tier: Optional[str] = None  # 'SMALL' | 'MEDIUM' | 'LARGE'
    
    # 이미지 분석 결과 (Phase 1-C)
    image_analysis: Optional[Dict[str, Any]] = None
    """
    예시:
    {
        "dominant_color": (255, 0, 0),      # (r, g, b) or None
        "vision_type": "BUTTON",             # 'BUTTON' | 'ICON' | 'LOGO' | ... or None
        "vision_description": "로그인 버튼"  # str or None
    }
    """
    
    # 모든 속성
    properties: Dict[str, Any]
    """
    예시:
    {
        "font_size": 14,
        "font_weight": 400,
        "font_family": "Arial",
        "color": "#333333",
        "background_color": "#ffffff",
        "contrast_ratio": 4.5,
        "position": {"x": 100, "y": 200},
        "size": {"width": 80, "height": 40},
        "border": "1px solid #ccc",
        "padding": "10px",
        "margin": "5px",
        "opacity": 1.0,
        "z_index": 1,
        "is_visible": True,
        "is_enabled": True,
        # ... 필요한 모든 CSS/스타일 속성
    }
    """
    
    # 메타데이터 (디버깅/추적용)
    metadata: Optional[Dict[str, Any]] = None
    """
    예시:
    {
        "source_type": "web_dom",  # 어디서 왔나
        "html_tag": "button", # 원본 테그
        "html_id": "login-btn", # 원본 ID
        "html_class": "btn primary",
        "xpath": "/html/body/div[1]/button[1]", # 디버깅 경로
        "original_data": {...}  # 원본 데이터 전체 (디버깅용)
    }
    """
    
    class Config:
        # JSON 예시
        json_schema_extra = {
            "example": {
                "type": "button",
                "content": "로그인",
                "properties": {
                    "font_size": 14,
                    "color": "#333333",
                    "background_color": "#4CAF50",
                    "contrast_ratio": 4.5,
                    "position": {"x": 100, "y": 200},
                    "size": {"width": 80, "height": 40},
                    "is_visible": True,
                    "is_enabled": True
                },
                "metadata": {
                    "source_type": "web_dom",
                    "html_tag": "button",
                    "html_id": "login-btn"
                }
            }
        }