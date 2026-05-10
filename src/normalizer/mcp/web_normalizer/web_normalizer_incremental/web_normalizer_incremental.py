#src/normalizer/mcp/web_normalizer/web_normalizer_incremental/web_normalizer_incremental.py

from playwright.sync_api import Page
from ..web_normalizer import WebNormalizer
from ..validators.web_node_validator import WebNodeValidator
from ..utils.web_node_converter import WebNodeConverter
from normalizer.standard_ui_node import StandardUINode
from typing import List, Dict, Any

from .mutation_observer import MutationObserver
from .cache_manager import CacheManager

class WebNormalizerIncremental(WebNormalizer):
    """
    MutationObserver 기반 증분 파싱
    WebNormalizer_test의 파싱 로직 재사용
    """
    
    def __init__(self, screenshot_cache=None):
        super().__init__()
        super().__init__(screenshot_cache=screenshot_cache)
        self.mutation_observer = MutationObserver()
        self.cache_manager = CacheManager()
        self.last_url = None
        self.cached_stats = None

    def _should_full_parse(self, page: Page) -> bool:
        """
        전체 파싱이 필요한지 판단
        
        전체 파싱 필요한 경우:
        1. URL이 바뀜 (새 페이지)
        2. Observer가 아직 설치 안 됨
        """
        
        current_url = page.url
        
        # 케이스 1: Observer 미설치
        if not self.mutation_observer.is_installed():
            print("Observer 미설치 → 전체 파싱")
            return True
        
        # 케이스 2: 첫 방문 (last_url이 None)
        if self.last_url is None:
            print("첫 방문 → 전체 파싱")
            return True
        
        # 케이스 3: URL 변경
        if current_url != self.last_url:
            print(f"URL 변경 ({self.last_url} → {current_url}) → 전체 파싱")
            return True
        
        # 케이스 4: 같은 페이지
        print("같은 페이지 → 증분 파싱")
        return False
    
    def _is_changed(self, new_node: StandardUINode, old_node: StandardUINode) -> bool:
        """
        노드가 실제로 의미있게 변경되었는지 확인
        
        비교 대상:
        1. content (텍스트)
        2. 핵심 속성들
        
        Returns:
            True: 의미있는 변경 있음
            False: 변경 없거나 사소한 변경
        """
        
        # 1. 내용(텍스트) 변경
        if new_node.content != old_node.content:
            return True
        
        # 2. 핵심 속성 변경 체크
        # AI가 봐야 하는 중요한 속성들만
        key_props = [
            # 시각적 변화
            'font_size',        # 글씨 크기 바뀜
            'font_weight',      # 글씨 굵기 바뀜 (bold)
            'color',            # 글자 색상 바뀜
            'background_color', # 배경색 바뀜
            'background_image', # 배경 이미지 추가/제거
            'opacity',          # 투명도 바뀜
            'display',          # 보임/안보임 바뀜
            'visibility',       # 보임/안보임 바뀜
            
            # 크기/위치 변화
            'width',            # 가로 크기 바뀜
            'height',           # 세로 크기 바뀜
            'x',                # 가로 위치 바뀜
            'y',                # 세로 위치 바뀜
            'position',         # 레이아웃 방식 바뀜 (static/absolute/fixed)
            
            # 간격 변화 (요소 크기에 영향)
            'padding_top',
            'padding_right',
            'padding_bottom',
            'padding_left',
            'margin_top',
            'margin_right',
            'margin_bottom',
            'margin_left',
            
            # 테두리 변화
            'border_width',     # 테두리 두께 바뀜
            'border_color',     # 테두리 색 바뀜
            'border_style',     # 테두리 스타일 바뀜 (solid/dashed/dotted)
            'border_radius',    # 모서리 둥글기 바뀜
            
            # 텍스트 스타일
            'text_decoration',  # 밑줄/취소선 생김
            
            # 레이어
            'z_index'           # 레이어 순서 바뀜
        ]
        
        for prop in key_props:
            new_val = new_node.properties.get(prop)
            old_val = old_node.properties.get(prop)
            
            if new_val != old_val:
                return True  # 하나라도 다르면 변경됨
        
        # 3. 메타데이터 변경 체크 (상태 변화)
        # disabled, readonly, checked, selected 같은 상태
        state_props = ['disabled', 'readonly', 'checked', 'selected']
        
        for prop in state_props:
            new_val = new_node.metadata.get(prop)
            old_val = old_node.metadata.get(prop)
            
            if new_val != old_val:
                return True  # 상태 바뀜 (중요!)
        
        # 4. 아무것도 안 바뀜
        return False
    
    def normalize(self, page: Page,clicked_xpath: str = None) -> List[StandardUINode]:
        """
        메인 진입점: 전체 파싱 vs 증분 파싱 분기점 - 페이지 url 기준
        
            전체 파싱: 전체 노드 리스트 (5000개)
            증분 파싱: 변경된 노드만 (100개)
        """
        
        # === Step 1: 전체 vs 증분 판단 ===
        if self._should_full_parse(page):
            print("=== 전체 파싱 ===")
            
            # Step 1-1: Observer 설치 (처음이거나 페이지 바뀌었을 때)
            if self._should_full_parse(page):
                page.wait_for_selector('body', timeout=5000)
                if not self.mutation_observer.is_installed() or page.url != (self.last_url or ''):
                    self.mutation_observer.setup_observer(page)
                    page.evaluate("window.scrollTo(0, 0)")
            
            # Step 1-2: 부모 클래스의 전체 파싱 실행
            all_nodes = super().normalize(page)
            # all_nodes = [StandardUINode, StandardUINode, ...] 5000개
            
            # Step 1-3: 전체를 XPath 기반 캐시에 저장
            self.cache_manager.build_cache(all_nodes)
            
            # Step 1-4: URL 기록 (다음에 비교용)
            self.last_url = page.url
            
            # Step 1-5: 전체 반환
            return all_nodes
        
        else:
            print("=== 증분 파싱 ===")
            
            # Step 2-1: JS 버퍼에서 변경사항 가져오기
            changes = self.mutation_observer.get_changes(page, clicked_xpath)
            # changes = {
            #     'added': [element1, element2, ...],
            #     'modified': [element3, element4, ...],
            #     'removed': ['#btn-1', '.modal', ...]  # selector들
            # }
            
            # Step 2-2: 변경된 요소들만 파싱
            delta_nodes = self._parse_delta_elements(page, changes)
            # delta_nodes = [StandardUINode, ...] 100개
            
            # Step 2-3: 캐시 업데이트
            self.cache_manager.update_cache(delta_nodes, changes['removed'])
            
            # Step 2-4: JS 버퍼 비우기 (다음 변경 감지 준비)
            self.mutation_observer.clear_buffers(page)
            
            # Step 2-5: 변경분만 반환
            return delta_nodes
        
        
    
    def _parse_delta_elements(self, page: Page, changes: Dict[str, Any]) -> List[StandardUINode]:
        """
        변경된 요소들만 파싱해서 StandardUINode로 변환
        
        Args:
            page: Playwright Page 객체
            changes: get_changes()가 반환한 변경사항
            
        Returns:
            변경된 노드들 (added + modified + removed)
            removed 노드는 properties['removed'] = True 플래그 포함
        """
        
        print(f"=== 증분 파싱 시작 ===")
        
        delta_nodes = []
        
        # === Step 1: added/modified 요소 파싱 ===
        print(f"변경된 요소 파싱: {len(changes['added'])}개")

        for raw_data in changes['added']:
            # 유효성 검사
            if not WebNodeValidator._is_valid_node(raw_data):
                continue
            
            # StandardUINode로 변환
            node = WebNodeConverter._convert_to_node(raw_data)
            if not node:
                continue
            
            # removed 플래그 추가 (added/modified는 False)
            node.properties['removed'] = False
            
            # added/modified 구분
            xpath = node.metadata.get('xpath')
            old_node = self.cache_manager.get_node(xpath)
            
            if old_node:
                # 캐시에 있음 → modified (변경 여부 확인)
                if self._is_changed(node, old_node):
                    delta_nodes.append(node)
                    print(f"  - 변경 감지: {xpath}")
                else:
                    # print(f"  - 변경 없음 (스킵): {xpath}")
                    # 임시: 스킵 말고 추가
                    delta_nodes.append(node)
                    print(f"  - 강제 추가 (원래 스킵): {xpath}")
            else:
                # 캐시에 없음 → added
                delta_nodes.append(node)
                print(f"  - 신규 추가: {xpath}")
        
        # === Step 2: removed 요소 처리 (NEW) ===
        print(f"제거된 요소 처리: {len(changes['removed'])}개")
        
        for selector in changes['removed']:
            # 캐시에서 해당 노드 찾기
            found_xpath = None
            removed_node = None
            
            for xpath, node in list(self.cache_manager.cache_map.items()):
                if node.metadata.get('selector') == selector:
                    found_xpath = xpath
                    removed_node = node
                    break
            
            if removed_node:
                # removed 플래그 True로 설정
                removed_node.properties['removed'] = True
                delta_nodes.append(removed_node)
                print(f"  - 제거 감지: {found_xpath}")
            else:
                print(f"  - 제거 대상 못 찾음: {selector}")
        
        print(f"파싱 완료: {len(delta_nodes)}개 노드 반환")
        
        # 이미지 처리 파이프라인 (removed 제외)
        non_removed = [n for n in delta_nodes if not n.properties.get('removed', False)]
        self.image_processor.process_images(page, non_removed)
        
        return delta_nodes