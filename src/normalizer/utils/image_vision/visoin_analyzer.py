#src/normalizer/utils/image_vision/vision_analizer.py

"""
Vision API 분석 모듈

Claude Vision API로 이미지 semantic labeling
캐싱 통합으로 API 호출 최소화
"""

from __future__ import annotations
from anthropic import Anthropic
from typing import Dict, Any
import os
import base64
import json
import imghdr


class VisionAnalyzer:
    """
    Claude Vision API 클라이언트 (캐싱 통합)
    
    이미지 레이블 분석 + PIL 색상 추출 여부 판단
    """
    
    # UI 요소 타입 (색상 추출 대상)
    UI_ELEMENTS = {'BUTTON', 'ICON', 'LOGO', 'ILLUSTRATION'}
    
    def __init__(self, cache, api_key: str = None):
        """
        Vision API 클라이언트 초기화 (API Key 방식)
        
        Args:
            cache: VisionCache 인스턴스
            api_key: Anthropic API Key (없으면 환경변수에서 읽음)
        
        Raises:
            ValueError: API Key가 없을 때
        """
        # API Key 확인
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not provided. "
                "Please set it in .env file or pass as parameter."
            )
        
        self.cache = cache
        self.client = Anthropic(api_key=self.api_key)
    
    def analyze(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        이미지 레이블 분석 (캐싱 통합)
        
        Returns:
            {
                "type": "BUTTON" | "LOGO" | "PRODUCT" | "PROFILE" | "AD" | "ICON" | "PHOTO" | "ILLUSTRATION",
                "description": "남성용 파란 가디건" | "로그인 버튼" | "나이키 운동화 광고" 등
            }
        """
        
        # 1. 캐시 조회
        cached = self.cache.get(image_bytes)
        if cached:
            return cached
        
        # 2. API 호출
        result = self._call_vision_api(image_bytes)
        
        # 3. 캐시 저장
        self.cache.set(image_bytes, result)
        
        return result
    
    def _call_vision_api(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Claude Vision API 실제 호출
        
        Returns:
            {
                "type": str,  # 이미지 유형
                "description": str  # 구체적 설명
            }
        """
        try:
            # 이미지 타입 자동 감지
            img_type = imghdr.what(None, h=image_bytes)
            media_type = f"image/{img_type}" if img_type in ['png', 'jpeg', 'gif', 'webp'] else "image/png"
            
            # base64 인코딩
            image_b64 = base64.standard_b64encode(image_bytes).decode('utf-8')
            
            # Claude Vision API 호출
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_b64
                                }
                            },
                            {
                                "type": "text",
                                "text": """이 이미지를 분석해줘.

응답 형식 (JSON만, 다른 텍스트 없이):
{
  "type": "이미지 유형 (하나만 선택)",
  "description": "구체적 설명"
}

type 선택지 (정확히 이 중 하나만):
- BUTTON
- ICON
- LOGO
- PRODUCT
- PROFILE
- AD
- PHOTO
- ILLUSTRATION

description 작성법:
- BUTTON/ICON: "로그인 버튼", "메뉴 아이콘"
- LOGO: "나이키 로고", "애플 로고"
- PRODUCT: "남성용 파란 가디건", "iPhone 15 Pro"
- PROFILE: "남성 프로필 사진", "비즈니스 정장 여성"
- AD: "나이키 운동화 광고", "자동차 프로모션"
- PHOTO: "커피 한 잔", "해변 풍경"
- ILLUSTRATION: "체크마크 그래픽", "화살표 일러스트"

짧고 명확하게 (10단어 이내)"""
                            }
                        ]
                    }
                ]
            )
            
            # 응답 파싱
            response_text = response.content[0].text.strip()
            
            # ```json ``` 제거
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            result = json.loads(response_text.strip())
            
            # 형식 검증
            if 'type' not in result or 'description' not in result:
                raise ValueError("Invalid response format: missing 'type' or 'description'")
            
            # type 검증 및 매핑
            valid_types = ['BUTTON', 'ICON', 'LOGO', 'PRODUCT', 'PROFILE', 'AD', 'PHOTO', 'ILLUSTRATION']
            
            if result['type'] not in valid_types:
                # 소문자나 변형된 응답 매핑
                type_mapping = {
                    'button': 'BUTTON',
                    'login button': 'BUTTON',
                    'submit button': 'BUTTON',
                    'icon': 'ICON',
                    'logo': 'LOGO',
                    'product image': 'PRODUCT',
                    'product': 'PRODUCT',
                    'advertisement': 'AD',
                    'banner': 'AD',
                    'ad': 'AD',
                    'photo': 'PHOTO',
                    'picture': 'PHOTO',
                    'image': 'PHOTO',
                    'illustration': 'ILLUSTRATION',
                    'graphic': 'ILLUSTRATION',
                    'profile': 'PROFILE',
                    'avatar': 'PROFILE'
                }
                
                result['type'] = type_mapping.get(result['type'].lower(), 'PHOTO')
            
            return result
        
        except json.JSONDecodeError as e:
            # JSON 파싱 실패 시 폴백
            return {
                'type': 'PHOTO',
                'description': 'Unknown image (JSON parse failed)'
            }
        
        except Exception as e:
            # API 호출 실패 시 폴백
            return {
                'type': 'PHOTO', 
                'description': f'API error: {str(e)[:50]}'
            }
    
    @staticmethod
    def should_extract_color(vision_type: str) -> bool:
        """
        색상 추출 여부 판단
        
        UI 요소(BUTTON, ICON, LOGO, ILLUSTRATION)만 색상 추출
        콘텐츠 이미지(PRODUCT, PHOTO, AD, PROFILE)는 제외
        
        Args:
            vision_type: Vision API가 반환한 이미지 타입
            
        Returns:
            True if UI 요소, False otherwise
        """
        return vision_type in VisionAnalyzer.UI_ELEMENTS