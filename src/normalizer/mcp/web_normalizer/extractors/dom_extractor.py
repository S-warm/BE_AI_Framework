#src/normalizer/mcp/web_normalizer/extractors/dom_extractor.py

from playwright.sync_api import Page
from typing import List, Dict, Any

class DomExtractor:
    """
    Playwright Page에서 모든 요소의 raw data 한번에 추출
    
    - 브라우저에서 JS 실행으로 DOM 데이터 bulk 추출
    - Python-JS 통신 1회로 성능 최적화
    """
    
    @staticmethod
    def _extract_dom(page: Page) -> List[Dict[str, Any]]:
        """
        한 페이지의 모든 렌더링 된 요소의 raw data 추출
        
        Returns:
            List[Dict]: 각 요소의 raw data
        """
        
        try:
            all_raw_data = page.evaluate('''
                () => {
                    // 모든 요소 선택
                    const elements = Array.from(document.querySelectorAll('*'));
                    
                    return elements.map(el => {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        const parent = el.parentElement;
                        
                        // === 헬퍼 함수들 ===
                        
                        // 실제 배경색 찾기 (투명하면 부모 탐색)
                        const getActualBG = (element) => {
                            let current = element;
                            while (current) {
                                const bg = window.getComputedStyle(current).backgroundColor;
                                if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') {
                                    return bg;
                                }
                                current = current.parentElement;
                            }
                            return 'rgb(255, 255, 255)';
                        };
                        
                        // line_height 계산
                        const getLineHeight = () => {
                            const fontSize = parseFloat(style.fontSize) || 0;
                            const lineHeight = style.lineHeight;
                            
                            if (lineHeight === 'normal') {
                                return fontSize * 1.2;
                            } else if (lineHeight.endsWith('px')) {
                                return parseFloat(lineHeight);
                            } else if (lineHeight.endsWith('%')) {
                                return fontSize * (parseFloat(lineHeight) / 100);
                            } else if (!isNaN(parseFloat(lineHeight))) {
                                return fontSize * parseFloat(lineHeight);
                            } else {
                                return fontSize * 1.2;
                            }
                        };
                        
                        // CSS Selector 생성
                        const getSelector = (elem) => {
                            if (elem.id) return `#${elem.id}`;
                            
                            if (elem.className && typeof elem.className === 'string') {
                                const classes = elem.className.trim().split(/\\s+/).join('.');
                                if (classes) return `${elem.tagName.toLowerCase()}.${classes}`;
                            }
                            
                            if (elem.name) return `${elem.tagName.toLowerCase()}[name="${elem.name}"]`;
                            
                            if (parent) {
                                const siblings = Array.from(parent.children);
                                const index = siblings.indexOf(elem) + 1;
                                return `${elem.tagName.toLowerCase()}:nth-child(${index})`;
                            }
                            
                            return elem.tagName.toLowerCase();
                        };
                        
                        // XPath 생성
                        const getXPath = (elem) => {
                            if (elem.id) return `id("${elem.id}")`;
                            
                            const parts = [];
                            let current = elem;
                            
                            while (current && current.nodeType === Node.ELEMENT_NODE) {
                                let index = 1;
                                let sibling = current.previousSibling;
                                
                                while (sibling) {
                                    if (sibling.nodeType === Node.ELEMENT_NODE && 
                                        sibling.nodeName === current.nodeName) {
                                        index++;
                                    }
                                    sibling = sibling.previousSibling;
                                }
                                
                                const tagName = current.nodeName.toLowerCase();
                                parts.unshift(`${tagName}[${index}]`);
                                current = current.parentElement;
                            }
                            
                            return '/' + parts.join('/');
                        };
                        
                        // Label 찾기 (input용)
                        const getLabelText = () => {
                            if (el.id) {
                                const label = document.querySelector(`label[for="${el.id}"]`);
                                if (label) return label.textContent.trim();
                            }
                            const parentLabel = el.closest('label');
                            if (parentLabel) return parentLabel.textContent.trim();
                            return "";
                        };
                        
                        // Checkbox/Radio Label 찾기
                        const getCheckboxLabel = () => {
                            if (el.id) {
                                const label = document.querySelector(`label[for="${el.id}"]`);
                                if (label) return label.textContent.trim();
                            }
                            const parentLabel = el.closest('label');
                            if (parentLabel) return parentLabel.textContent.trim();
                            return el.name || "";
                        };
                        
                        // src 파일명 추출
                        const getSrcFilename = () => {
                            const src = el.src || "";
                            if (!src) return "";
                            const parts = src.split('/');
                            const filename = parts[parts.length - 1];
                            return filename.replace(/\\.[^.]+$/, '');
                        };
                        
                        // Select 선택된 옵션
                        const getSelectedOption = () => {
                            const selected = el.options?.[el.selectedIndex];
                            if (selected) return selected.text.trim();
                            if (el.options?.length > 0) return el.options[0].text.trim();
                            return "";
                        };
                        
                        const getContainerText = () => {
                            return Array.from(el.childNodes)
                                .filter(n => n.nodeType === Node.TEXT_NODE)
                                .map(n => n.textContent.trim())
                                .filter(t => t)
                                .join(' ');
                        };
                        
                        // === 실제 데이터 추출 ===
                        
                        const actualBackground = getActualBG(el);
                        
                        return {
                            // 기본
                            tag: el.tagName.toLowerCase(),
                            
                            // 위치/크기
                            rect: {
                                x: rect.x || 0,
                                y: rect.y || 0,
                                width: rect.width || 0,
                                height: rect.height || 0
                            },
                            
                            // 스타일 (필요한 것만)
                            styles: {
                                visibility: style.visibility || 'visible',
                                display: style.display || '',
                                opacity: parseFloat(style.opacity) || 1
                            },
                            
                            // 타입 판단용
                            input_type: el.type || '',
                            role: el.getAttribute('role') || '',
                            
                            // 텍스트 관련
                            text_content: (el.textContent || "").trim(),
                            value: el.value || '',
                            placeholder: el.placeholder || '',
                            
                            // Label
                            label_text: getLabelText(),
                            
                            // 이미지
                            alt: el.alt || '',
                            title: el.title || '',
                            src_filename: getSrcFilename(),
                            
                            // Select
                            selected_option: getSelectedOption(),
                            
                            // Checkbox/Radio
                            checkbox_label: getCheckboxLabel(),
                            
                            // Container
                            container_text: getContainerText(),
                            
                            // Properties (전체)
                            properties: {
                                // 폰트
                                font_size: parseFloat(style.fontSize) || 0,
                                font_weight: style.fontWeight || 'normal',
                                font_family: style.fontFamily || '',
                                line_height: getLineHeight(),
                                
                                // 색상
                                color: style.color || '',
                                background_color: actualBackground,
                                border_color: style.borderColor || '',
                                
                                // 위치 (viewport 기준)
                                x: rect.x || 0,
                                y: rect.y || 0,
                                width: rect.width || 0,
                                height: rect.height || 0,
                                
                                // 간격
                                padding_top: parseFloat(style.paddingTop) || 0,
                                padding_right: parseFloat(style.paddingRight) || 0,
                                padding_bottom: parseFloat(style.paddingBottom) || 0,
                                padding_left: parseFloat(style.paddingLeft) || 0,
                                
                                margin_top: parseFloat(style.marginTop) || 0,
                                margin_right: parseFloat(style.marginRight) || 0,
                                margin_bottom: parseFloat(style.marginBottom) || 0,
                                margin_left: parseFloat(style.marginLeft) || 0,
                                
                                // 테두리
                                border_width: parseFloat(style.borderWidth) || 0,
                                border_style: style.borderStyle || 'none',
                                border_radius: parseFloat(style.borderRadius) || 0,
                                
                                // 표시
                                opacity: parseFloat(style.opacity) || 1,
                                visibility: style.visibility || 'visible',
                                display: style.display || '',
                                z_index: parseInt(style.zIndex) || 0,
                                cursor: style.cursor || 'auto',
                                
                                // 텍스트
                                text_align: style.textAlign || 'left',
                                text_decoration: style.textDecoration || 'none',
                                
                                // 배경
                                background_image: style.backgroundImage || 'none',
                                
                                // 포지션
                                position: style.position || 'static'
                            },
                            
                            // Metadata (전체)
                            metadata: {
                                // 기본 정보
                                page_url: window.location.href,
                                html_tag: el.tagName.toLowerCase(),
                                id: el.id || '',
                                class_list: el.className && typeof el.className === 'string' 
                                    ? el.className.trim().split(/\\s+/) 
                                    : [],
                                name: el.name || '',
                                
                                // 클릭용
                                selector: getSelector(el),
                                xpath: getXPath(el),
                                
                                // 접근성
                                aria_label: el.getAttribute('aria-label') || '',
                                aria_role: el.getAttribute('role') || '',
                                title: el.title || '',
                                alt: el.alt || '',
                                
                                // 링크/미디어
                                href: el.href || '',
                                src: el.src || '',
                                
                                // 구조
                                parent_tag: parent ? parent.tagName.toLowerCase() : '',
                                parent_id: parent ? parent.id : '',
                                parent_class: parent && parent.className && typeof parent.className === 'string'
                                    ? parent.className.trim().split(/\\s+/)
                                    : [],
                                    
                                // 조상 태그 목록 (추가)
                                ancestor_tags: (() => {
                                    const tags = [];
                                    let current = el.parentElement;
                                    while (current && current.tagName !== 'BODY') {
                                        tags.push(current.tagName.toLowerCase());
                                        current = current.parentElement;
                                    }
                                    return tags;
                                })(),
                                
                                // 상태
                                disabled: el.disabled || false,
                                readonly: el.readOnly || false,
                                checked: el.checked || false,
                                selected: el.selected || false,
                                
                                // 입력 타입
                                input_type: el.type || '',
                                placeholder: el.placeholder || '',
                                value: el.value || '',
                                
                                // 폼 유효성 제약
                                required: el.required || false,
                                pattern: el.pattern || '',
                                minlength: el.minLength || null,
                                maxlength: el.maxLength || null,
                                min: el.min || '',
                                max: el.max || '',
                                step: el.step || '',
                                inputmode: el.inputMode || '',
                                autocomplete: el.autocomplete || ''
                            }
                        };
                    });
                }
            ''')
            
            return all_raw_data
        
        except Exception as e:
            print(f"Error extracting all raw data: {e}")
            return []