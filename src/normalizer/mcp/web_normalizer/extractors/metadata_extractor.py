#src/normalizer/mcp/web_normalizer/extractors/metadata_extractor.py

from typing import Dict, Any

class MetadataExtractor:
    """
    메타데이터 추출
    """
    
    @staticmethod
    def _extract_metadata(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        "메타데이터" 추출
        
        용도:
        1. 디버깅: 어떤 요소인지 확인
        2. 추적: 로그에서 요소 식별
        3. 클릭: Playwright로 클릭할 때 selector 필요
            -> AI한테 클릭을 시키면 이미 element는 StandardUINode로 바뀌었기에
            -> element 객체로는 못 찾음, 그래서 selector로 찾게 함
        
        추출 정보:
        - page_url: 페이지 URL (증분 파싱 판단용)
        - html_tag: HTML 태그 이름
        - id: id 속성
        - class_list: class 목록
        - name: name 속성 (input 등)
        - selector: CSS selector (클릭용)
        - xpath: XPath (클릭용 백업)
        - aria_label: 접근성 레이블
        - role: ARIA role
        - href: 링크 URL (a 태그)
        - src: 이미지/미디어 URL
        - parent_tag: 부모 태그
        """
        
        try:
            # JS에서 이미 추출된 메타데이터 가져오기
            meta = raw_data.get('metadata', {}).copy()
            
            # source_type 추가 (MCP 구분용)
            meta['source_type'] = 'web_dom'
        
            return meta
        
        except Exception as e:
            print(f"Error extracting metadata: {e}")
            return MetadataExtractor._get_default_metadata()

    @staticmethod
    def _get_default_metadata() -> Dict[str, Any]:
        """에러 시 기본 메타데이터 반환"""
        return {
            'page_url': '',
            'html_tag': '',
            'id': '',
            'class_list': [],
            'name': '',
            'selector': '',
            'xpath': '',
            'aria_label': '',
            'aria_role': '',
            'title': '',
            'alt': '',
            'href': '',
            'src': '',
            'parent_tag': '',
            'parent_id': '',
            'parent_class': [],
            'disabled': False,
            'readonly': False,
            'checked': False,
            'selected': False,
            'input_type': '',
            'placeholder': '',
            'value': '',
            
            'required': False,
            'pattern': '',
            'minlength': None,
            'maxlength': None,
            'min': '',
            'max': '',
            'step': '',
            'inputmode': '',
            'autocomplete': '',
            'source_type': 'web_dom'
        }