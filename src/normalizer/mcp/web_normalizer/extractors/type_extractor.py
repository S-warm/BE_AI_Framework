#src/normalizer/mcp/web_normalizer/extractors/type_extractor.py

from typing import Dict, Any

class TypeExtractor:
    
    @staticmethod
    def _extract_type(raw_data: Dict[str, Any]) -> str:
        """
        요소 "타입" 추출
        AI가 요소의 역할을 이해하게 한다.
        
        반환 가능한 타입:
        1. button: 버튼 (<button>, <input type="submit/button">, role="button")
        2. input: 입력 필드 (<input type="text/email/password">, <textarea>)
        3. text: 일반 텍스트 (<p>, <span>, <div with text>, <h1-h6>)
        4. link: 링크 (<a>)
        5. image: 이미지 (<img>, <svg>)
        6. select: 드롭다운 (<select>)
        7. checkbox: 체크박스 (<input type="checkbox">)
        8. radio: 라디오 버튼 (<input type="radio">)
        9. container: 컨테이너 (<div>, <section>, <article> 등)
        10. divider: 구분선 (<hr>)
        11. other: 기타
        """
        
        try:
            tag_name = raw_data.get('tag', '').lower()
            role = raw_data.get('role', '').lower()
            
            # 1. role 속성 우선 확인 (접근성, 예: div지만 버튼처럼 동작)
            if role:
                if role == 'button':
                    return 'button'
                elif role == 'link':
                    return 'link'
                elif role in ['textbox', 'searchbox']:
                    return 'input'
            
            # 2. 명확한 태그 기반 판단 (딕셔너리 이용)
            type_map = {
                'button': 'button',
                'a': 'link',
                'img': 'image',
                'svg': 'image',
                'select': 'select',
                'textarea': 'input',
                'hr': 'divider',
            }
            
            if tag_name in type_map:
                return type_map[tag_name]
            
            # 3. input 태그 세분화
            if tag_name == 'input':
                input_type = raw_data.get('input_type', '').lower()
                
                if input_type in ['button', 'submit', 'reset']:
                    return 'button'
                elif input_type == 'checkbox':
                    return 'checkbox'
                elif input_type == 'radio':
                    return 'radio'
                else:
                    return 'input'
            
            # 5. 컨테이너 요소
            if tag_name in ['div', 'section', 'article', 'main', 'header', 'footer', 'nav', 'aside', 'form', 'body', 'html']:
                return 'container'
                
            # span/li/td 등 — 조상에 a나 nav가 있으면 link, onclick 있으면 button
            if tag_name in ['span', 'li', 'td', 'th', 'label']:
                metadata = raw_data.get('metadata', {})
                ancestor_tags = metadata.get('ancestor_tags', [])
                has_onclick = metadata.get('has_onclick', False)
                
                if has_onclick:
                    return 'button'
                if 'a' in ancestor_tags:
                    return 'link'
                if 'nav' in ancestor_tags:
                    return 'link'
                
                text_content = raw_data.get('text_content', '').strip()
                if text_content:
                    return 'text'
                return 'container'
            
            # 6. 텍스트 내용이 있으면 text
            text_content = raw_data.get('text_content', '').strip()
            if text_content:
                return 'text'
            
            # 7. 기타
            return 'other'
            
        except:
            return 'other'