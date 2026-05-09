#src/normalizer/mcp/web_normalizer/web_normalizer_incremental/cache_manager.py

from normalizer.standard_ui_node import StandardUINode
from typing import List, Optional

class CacheManager:
    """
    XPath 기반 캐시 관리
    증분 파싱을 위한 노드 저장소
    
    이건 같은 페이지 내에서 최적화를 위해 하는 캐싱임
    """
    
    def __init__(self):
        self.cache_map = {}
        
    def build_cache(self, nodes: List[StandardUINode]):
        """
        전체 파싱 후 XPath 기반 캐시 구축
        
        캐시 구조:
            self.cache_map = {
                '/html/body/div[1]/button[1]': StandardUINode,
                '/html/body/div[2]/input[1]': StandardUINode,
            }
        """
        
        print(f"캐시 구축 시작: {len(nodes)}개 노드")
        
        # === Step 1: 기존 캐시 초기화 ===
        # 페이지가 바뀌었으므로 이전 캐시는 무효
        # TODO : 기억력 , 디지털 리터리시 레이어 함수 만들때 초기화 하기전에 캐시 중요도 함수에서 캐시 사용하는 방향으로 수정해야함
        self.cache_map.clear()
        
        # === Step 2: 각 노드를 XPath 키로 저장 ===
        for node in nodes:
            # XPath 추출 (metadata에 있음)
            xpath = node.metadata.get('xpath')
            
            # XPath 없으면 스킵 (예외 상황)
            if not xpath:
                print(f"WARNING: XPath 없는 노드 발견 (type={node.type}, content={node.content[:20]})")
                continue
            
            # 캐시에 저장
            self.cache_map[xpath] = node
        
        print(f"캐시 구축 완료: {len(self.cache_map)}개 저장됨")
        
    def update_cache(self, delta_nodes: List[StandardUINode], removed_selectors: List[str]):
        """
        캐시 업데이트: 추가/수정/삭제 반영 
        
        added modified는 구분 안함
        이미 있으면 -> 수정(덮어쓰기)
        파이썬 dict는 자동으로 처리
        """
        
        print("=== 캐시 업데이트 시작 ===")
        
        initial_count = len(self.cache_map)
        
        # === Step 1: added/modified 반영 ===
        # XPath 키로 저장 (덮어쓰기)
        
        for node in delta_nodes:
            xpath = node.metadata.get('xpath')
            
            if not xpath:
                print(f"WARNING: XPath 없는 노드 (type={node.type})")
                continue
            
            # 이미 있으면 수정, 없으면 추가
            if xpath in self.cache_map:
                print(f"  [수정] {xpath}")
            else:
                print(f"  [추가] {xpath}")
            
            self.cache_map[xpath] = node
        
        # === Step 2: removed 반영 ===
        # selector로 찾아서 삭제
        
        removed_count = 0
        
        for selector in removed_selectors:
            # selector로 XPath 찾기
            # cache_map은 XPath가 키니까 역검색 필요
            
            found_xpath = None
            
            for xpath, node in list(self.cache_map.items()):
                # metadata에서 selector 비교
                if node.metadata.get('selector') == selector:
                    found_xpath = xpath
                    break
            
            # 찾았으면 삭제
            if found_xpath:
                del self.cache_map[found_xpath]
                removed_count += 1
                print(f"  [삭제] {found_xpath} (selector: {selector})")
            else:
                # 못 찾음 (이미 삭제됐거나 캐시에 없었음)
                print(f"  [삭제 실패] selector {selector} 못 찾음")
        
        # === Step 3: 결과 출력 ===
        final_count = len(self.cache_map)
        
        print(f"캐시 업데이트 완료:")
        print(f"  - 이전: {initial_count}개")
        print(f"  - 추가/수정: {len(delta_nodes)}개")
        print(f"  - 삭제: {removed_count}개")
        print(f"  - 최종: {final_count}개")
        
    def get_node(self, xpath: str) -> Optional[StandardUINode]:
        """
        XPath로 노드 조회
        
        Args:
            xpath: 조회할 노드의 XPath
            
        Returns:
            StandardUINode 또는 None
        """
        return self.cache_map.get(xpath)
    
    def get_all_nodes(self) -> List[StandardUINode]:
        """
        캐시된 전체 노드 반환 (증분 파싱용)
        
        Returns:
            캐시에 저장된 모든 노드 리스트
        
        사용:
            # 증분 파싱 후 전체 노드 필요 시
            all_nodes = incremental.get_all_cached_nodes()
        """
        return list(self.cache_map.values())
    
    def clear(self):
        """캐시 초기화"""
        self.cache_map.clear()
        print("캐시 초기화 완료")