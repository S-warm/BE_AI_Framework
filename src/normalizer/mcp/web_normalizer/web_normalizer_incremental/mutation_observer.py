#src/normalizer/mcp/web_normalizer/web_normalizer_incremental/mutation_observer.py

from playwright.sync_api import Page
from typing import Dict, Any

class MutationObserver:
    """
    MutationObserver 기반 증분 파싱
    WebNormalizer_test의 파싱 로직 재사용
    """
    
    def __init__(self):
        self.observer_installed = False
    
    def setup_observer(self, page: Page):
        """
        Phase 0.5.1: JavaScript MutationObserver 설치
        
        Step A: 버퍼 초기화
        Step B: 단일 요소 추출 함수
        """
        
        # JavaScript 코드 실행
        page.evaluate("""
            () => {
                // ===== Step A: 버퍼 초기화 =====
                
                window.__ui_delta_buffer__ = new Set();
                window.__ui_removed_buffer__ = new Set();
                
                console.log('버퍼 초기화 완료');
                
                // === Step B: 헬퍼 함수들 (원본과 동일) ===
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
                
                const getLineHeight = (style) => {
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
                
                const getSelector = (elem, parent) => {
                        if (elem.id) return '#' + elem.id;
                        
                        if (elem.className && typeof elem.className === 'string') {
                            const classes = elem.className.trim().split(/\\s+/).join('.');
                            if (classes) return elem.tagName.toLowerCase() + '.' + classes;
                        }
                        
                        if (elem.name) return elem.tagName.toLowerCase() + '[name="' + elem.name + '"]';
                        
                        if (parent) {
                            const siblings = Array.from(parent.children);
                            const index = siblings.indexOf(elem) + 1;
                            return elem.tagName.toLowerCase() + ':nth-child(' + index + ')';
                        }
                        
                        return elem.tagName.toLowerCase();
                    };
                
                const getXPath = (elem) => {
                        if (elem.id) return 'id("' + elem.id + '")';
                        
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
                            parts.unshift(tagName + '[' + index + ']');
                            current = current.parentElement;
                        }
                        
                        return '/' + parts.join('/');
                    };
                
                const getCheckboxLabel = (el) => {
                        if (el.id) {
                            const label = document.querySelector('label[for="' + el.id + '"]');
                            if (label) return label.textContent.trim();
                        }
                        const parentLabel = el.closest('label');
                        if (parentLabel) return parentLabel.textContent.trim();
                        return el.name || "";
                    };
                
                const getLabelText = (el) => {
                        if (el.id) {
                            const label = document.querySelector('label[for="' + el.id + '"]');
                            if (label) return label.textContent.trim();
                        }
                        const parentLabel = el.closest('label');
                        if (parentLabel) return parentLabel.textContent.trim();
                        return "";
                    };
                
                const getSrcFilename = (el) => {
                        const src = el.src || "";
                        if (!src) return "";
                        const parts = src.split('/');
                        const filename = parts[parts.length - 1];
                        return filename.replace(/\\.[^.]+$/, '');
                    };
                
                const getSelectedOption = (el) => {
                        const selected = el.options?.[el.selectedIndex];
                        if (selected) return selected.text.trim();
                        if (el.options?.length > 0) return el.options[0].text.trim();
                        return "";
                    };
                
                const getContainerText = (el) => {
                    return Array.from(el.childNodes)
                        .filter(n => n.nodeType === Node.TEXT_NODE)
                        .map(n => n.textContent.trim())
                        .filter(t => t)
                        .join(' ');
                };
                
                // ===== Step C: 단일 요소 추출 함수 =====
                // 원본 web_normalizer.py와 100% 동일한 로직
                
                window.__extract_single__ = (el) => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    const parent = el.parentElement;
                    
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
                        label_text: getLabelText(el),
                        
                        // 이미지
                        alt: el.alt || '',
                        title: el.title || '',
                        src_filename: getSrcFilename(el),
                        
                        // Select
                        selected_option: getSelectedOption(el),
                        
                        // Checkbox/Radio
                        checkbox_label: getCheckboxLabel(el),
                        
                        // Container
                        container_text: getContainerText(el),
                        
                        // Properties (전체)
                        properties: {
                            // 폰트
                            font_size: parseFloat(style.fontSize) || 0,
                            font_weight: style.fontWeight || 'normal',
                            font_family: style.fontFamily || '',
                            line_height: getLineHeight(style),
                            
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
                            selector: getSelector(el, parent),
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
                            
                            // 폼 유효성 제약
                            required: el.required || false,
                            pattern: el.pattern || '',
                            minlength: el.minLength || null,
                            maxlength: el.maxLength || null,
                            min: el.min || '',
                            max: el.max || '',
                            step: el.step || '',
                            inputmode: el.inputMode || '',
                            autocomplete: el.autocomplete || '',
                            has_onclick: el.onclick !== null || el.hasAttribute('onclick')
                        }
                    };
                };
                
                console.log('단일 추출 함수 준비 완료');
                
                // ===== Step D: MutationObserver 설치 =====
                
                const observer = new MutationObserver((mutations) => {
                    // mutations = 변경 내역 배열
                    
                    mutations.forEach(mutation => {
                        // 1. 노드 추가/삭제 (childList)
                        if (mutation.type === 'childList') {
                            
                            // 추가된 노드들
                            mutation.addedNodes.forEach(node => {
                                if (node.nodeType === 1) {
                                    window.__ui_delta_buffer__.add(node);
                                    node.querySelectorAll('a, button, input, select, li').forEach(child => {
                                        window.__ui_delta_buffer__.add(child);
                                    });
                                }
                            });
                            
                            // 삭제된 노드들
                            mutation.removedNodes.forEach(node => {
                                if (node.nodeType === 1) {
                                    try {
                                        // 삭제 전에 selector 기록
                                        const selector = getSelector(node, node.parentElement);
                                        window.__ui_removed_buffer__.add(selector);
                                    } catch (e) {
                                        // 이미 DOM에서 제거되어 접근 불가능한 경우 무시
                                    }
                                }
                            });
                        }
                        
                        // 2. 속성 변경 (attributes)
                        // 예: class 추가, disabled 변경 등
                        else if (mutation.type === 'attributes') {
                            const attr = mutation.attributeName;
                            if (attr === 'style' || attr === 'class' || attr === 'hidden') {
                                const el = mutation.target;
                                const style = window.getComputedStyle(el);
                                if (style.display !== 'none' && style.visibility !== 'hidden') {
                                    window.__ui_delta_buffer__.add(el);
                                    el.querySelectorAll('a, button, input, select, li').forEach(child => {
                                        window.__ui_delta_buffer__.add(child);
                                    });
                                }
                            }
                        }
                        
                        // 3. 텍스트 변경 (characterData)
                        // 예: "로그인" → "로그인 중..."
                        else if (mutation.type === 'characterData') {
                            // textNode면 부모 Element 담기
                            const target = mutation.target.nodeType === 3 
                                ? mutation.target.parentElement 
                                : mutation.target;
                            
                            if (target) {
                                window.__ui_delta_buffer__.add(target);
                            }
                        }
                    });
                });
                
                // Observer 시작
                observer.observe(document.body, {
                    childList: true,       // 자식 노드 추가/삭제 감시
                    attributes: true,      // 속성 변경 감시
                    characterData: true,   // 텍스트 변경 감시
                    subtree: true          // 모든 하위 요소 감시
                });
                
                console.log('MutationObserver 설치 완료');
            }
        """)
        
        self.observer_installed = True
        print("MutationObserver 설치 완료")
        
    def get_changes(self, page: Page, clicked_xpath: str = None) -> Dict[str, Any]:
        print("=== 변경사항 수집 시작 ===")
        
        changes_data = page.evaluate('''
            (clickedXpath) => {
                // 버퍼 없으면 빈 결과 반환
                if (!window.__ui_delta_buffer__) {
                    return { added: [], removed: [] };
                }
                
                console.log('버퍼 사이즈:', window.__ui_delta_buffer__.size);
                console.log('clickedXpath 받음:', clickedXpath);
                const added = Array.from(window.__ui_delta_buffer__ || new Set());
                const removed = Array.from(window.__ui_removed_buffer__ || new Set());
                
                if (!clickedXpath) {
                    return {
                        added: added.map(el => window.__extract_single__(el)),
                        removed: removed
                    };
                }
                
                const normalizeXpath = (xpath) => {
                    return xpath.replace(/^id\("(.+)"\)$/, '//*[@id="$1"]');
                };
                
                const getElementByXpath = (xpath) => {
                    try {
                        return document.evaluate(
                            xpath, document, null,
                            XPathResult.FIRST_ORDERED_NODE_TYPE, null
                        ).singleNodeValue;
                    } catch(e) {
                        return null;
                    }
                };
                
                const clickedEl = getElementByXpath(clickedXpath);
                const clickedParent = clickedEl ? clickedEl.parentElement : null;
                
                const isRelated = (el) => {
                    if (!clickedEl) return true;
                    if (clickedEl.contains(el)) return true;
                    if (clickedParent && clickedParent.contains(el)) return true;
                    if (el.parentElement === document.body) return true;
                    if (el.contains(clickedEl)) return true;
                    
                    return false;
                };
                
                const filteredAdded = added
                    .filter(isRelated)
                    .filter(el => {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) return true;
                        const tag = el.tagName.toLowerCase();
                        return ['a', 'button', 'input', 'select'].includes(tag);
                    });
                
                return {
                    added: filteredAdded.map(el => window.__extract_single__(el)),
                    removed: removed,
                    raw_count: added.length
                };
            }
        ''', clicked_xpath)
        
        print(f"변경 감지: raw={changes_data.get('raw_count', '?')}, filtered={len(changes_data['added'])}, removed={len(changes_data['removed'])}")
        
        return changes_data
    
    def clear_buffers(self, page: Page):
        """
        JavaScript 버퍼 비우기
        다음 변경 감지를 위해 초기화
        
        MutationObserver는 계속 실행 중이므로
        버퍼만 비우면 다음 변경부터 다시 쌓임
        """
        
        print("=== 버퍼 초기화 ===")
        
        page.evaluate('''
            () => {
                // Set의 clear() 메서드로 비우기
                if (window.__ui_delta_buffer__) {
                    window.__ui_delta_buffer__.clear();
                }
                
                if (window.__ui_removed_buffer__) {
                    window.__ui_removed_buffer__.clear();
                }
                
                console.log('버퍼 초기화 완료');
            }
        ''')
        
        print("버퍼 초기화 완료 - 다음 변경 감지 준비됨")
    
    def is_installed(self) -> bool:
        """
        Observer가 설치되어 있는지 확인
        
        Returns:
            True: 설치됨
            False: 미설치
        """
        return self.observer_installed