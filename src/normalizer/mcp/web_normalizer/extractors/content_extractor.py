#src/normalizer/mcp/web_normalizer/extractors/content_extractor.py

from typing import Dict, Any
from .type_extractor import TypeExtractor

class ContentExtractor:
    """
    raw_data에서 요소 내용 추출
    타입별로 적절한 텍스트를 추출한다
    """
    
    @staticmethod
    def _extract_content(raw_data: Dict[str, Any]) -> str:
        """
        요소 "내용" 추출 (텍스트, placeholder 등)
        AI가 의미를 이해하게 한다
        ex) 이게 로그인 버튼인지 회원가입 버튼인지
        
        타입별 추출 방법:
        - button/link/text: textContent
        - input: placeholder or value
        - image: alt 속성
        - select: 선택된 option
        - checkbox/radio: 연관된 label
        - container: 자식들의 텍스트 요약
        """
        
        try:
            # 먼저 타입 확인 (이미 구현된 _extract_type 활용)
            element_type = TypeExtractor._extract_type(raw_data)
            
            # 타입별 추출 전략
            if element_type in ['button', 'link', 'text']:
                # 1. 텍스트 요소: textContent
                return ContentExtractor._get_text_content(raw_data)
            
            elif element_type == 'input':
                # 2. 입력 필드: placeholder > value > label
                return ContentExtractor._get_input_content(raw_data)
            
            elif element_type == 'image':
                # 3. 이미지: alt > title
                return ContentExtractor._get_image_content(raw_data)
            
            elif element_type == 'select':
                # 4. 드롭다운: 선택된 옵션 or placeholder
                return ContentExtractor._get_select_content(raw_data)
            
            elif element_type in ['checkbox', 'radio']:
                # 5. 체크박스/라디오: 연관 label
                return ContentExtractor._get_checkbox_content(raw_data)
            
            elif element_type == 'container':
                # 6. 컨테이너: 자식 텍스트 요약 (짧게)
                return ContentExtractor._get_container_content(raw_data)
            
            elif element_type == 'divider':
                # 7. 구분선: 내용 없음
                return ""
            
            else:
                # 8. 기타: textContent 시도
                return ContentExtractor._get_text_content(raw_data)

        except Exception as e:
            print(f"Error extracting content: {e}")
            return ""
        
# ===================================== 헬퍼 함수 ==============================================

    @staticmethod
    def _get_text_content(raw_data: Dict[str, Any]) -> str:
        """
        텍스트 내용 추출 (button, link, text, p, span 등)
        """
        try:
            text = raw_data.get('text_content', '').strip()
            return text
        except:
            return ""

    @staticmethod
    def _get_input_content(raw_data: Dict[str, Any]) -> str:
        """
        입력 필드 내용 추출
        우선순위: value > placeholder > label
        """
        try:
            # 1. value가 있으면 (이미 입력된 값)
            value = raw_data.get('value', '').strip()
            if value:
                return value
            
            # 2. placeholder가 있으면 (입력 전 안내 문구)
            placeholder = raw_data.get('placeholder', '').strip()
            if placeholder:
                return placeholder
            
            # 3. 연관된 label 찾기
            label_text = raw_data.get('label_text', '').strip()
            return label_text
        
        except:
            return ""

    @staticmethod
    def _get_image_content(raw_data: Dict[str, Any]) -> str:
        """
        이미지 내용 추출
        우선순위: alt > title > src 파일명
        """
        try:
            # 1. alt 속성 (접근성을 위한 대체 텍스트)
            alt = raw_data.get('alt', '').strip()
            if alt:
                return alt
            
            # 2. title 속성
            title = raw_data.get('title', '').strip()
            if title:
                return title
            
            # 3. src에서 파일명 추출 (최후의 수단)
            src_filename = raw_data.get('src_filename', '').strip()
            
            return src_filename
        
        except:
            return ""

    @staticmethod
    def _get_select_content(raw_data: Dict[str, Any]) -> str:
        """
        드롭다운 내용 추출
        선택된 옵션 or 첫 번째 옵션
        """
        try:
            selected = raw_data.get('selected_option', '').strip()
            return selected
        
        except:
            return ""

    @staticmethod
    def _get_checkbox_content(raw_data: Dict[str, Any]) -> str:
        """
        체크박스/라디오 내용 추출
        연관된 label 텍스트
        """
        try:
            label_text = raw_data.get('checkbox_label', '').strip()
            return label_text
        
        except:
            return ""

    @staticmethod
    def _get_container_content(raw_data: Dict[str, Any]) -> str:
        """
        컨테이너 내용 추출 (요약)
        컨테이너 -> 덩어리 개념으로 묶음 (인간은 한번에 못 보고 덩어리 개념으로 봄)
        프로퍼티즈 -> 코드로 제한 (블러 처리, 연령대별 픽셀값 조정 등)
        
        자식이 많으면 너무 길어질 수 있으므로
        - 최대 100자까지만
        - 공백 정리
        """
        try:
            # textContent (모든 자식 텍스트, script/style 제외됨)
            text = raw_data.get('container_text', '').strip()
            
            # 공백 정리 (여러 공백 → 하나로)
            text = ' '.join(text.split())
            
            # 너무 길면 자르기 100글자 (어차피 자식 컨테이너들로 내용 힌트가 있어서 전부 파싱하면 ai 비용만 증가)
            if len(text) > 100:
                text = text[:97] + "..."
            
            return text
        
        except:
            return ""