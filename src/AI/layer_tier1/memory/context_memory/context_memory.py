#src/AI/layer_tier1/memory/context_memory.py

from normalizer.standard_ui_node import StandardUINode
from typing import List, Dict

class ContextMemory:
    
    
    def __init__(self):
        """초기화"""
        self.incremental_layers: List[Dict] = []
    
    def add_incremental(self, nodes: List[StandardUINode], trigger: str) -> None:
        """
        증분 레이어 추가 (스택 push)
        
        Args:
            nodes: 새로 나타난/변경된 노드들
            trigger: 어떤 액션으로 나타났는지
                    형식: "action|element_id|element_text"
        
        Example:
            # 모달 열림
            context_memory.add_incremental([모달창, 배경], "click|elem42|회원가입")
            # incremental_layers = [{'nodes': [모달창, 배경], 'trigger': '...'}]
            
            # 모달 안에서 드롭다운 클릭
            context_memory.add_incremental([옵션1, 옵션2], "click|elem50|언어선택")
            # incremental_layers = [
            #     {'nodes': [모달창, 배경], 'trigger': '...'},
            #     {'nodes': [옵션1, 옵션2], 'trigger': '...'}
            # ]
        """
        new_layer = {
            'nodes': nodes,
            'trigger': trigger
        }
        self.incremental_layers.append(new_layer)
    
    def clear_incremental(self) -> None:
        """
        모든 증분 레이어 제거 (페이지 전환 시)
        
        호출 시점:
        - 페이지 전환 (URL 바뀜)
        - 전체 증분 초기화 필요할 때
        
        Example:
            # 페이지 전환 시
            context_memory.clear_incremental()
            # incremental_layers = []
        """
        self.incremental_layers = []
        
    def has_incremental(self) -> bool:
        """
        증분 레이어 존재 여부
        
        Returns:
            True: 증분 변화 있음 (레이어 1개 이상)
            False: 증분 변화 없음
        
        Example:
            if context_memory.has_incremental():
                prompt += context_memory.get_incremental_summary()
        """
        return len(self.incremental_layers) > 0
    
    def get_incremental_summary(self) -> str:
        """
        프롬프트용 증분 레이어 요약 (레이어별 전부 출력)
        
        Returns:
            프롬프트 문자열 또는 빈 문자열
        
        Example:
            >>> context_memory.get_incremental_summary()
            "새로 나타남_1 (elem42 '로그인' click): 2개 요소
            새로 나타남_2 (elem50 '국가선택' click): 3개 요소"
        """
        if not self.has_incremental():
            return ""
        
        summaries = []
        for i, layer in enumerate(self.incremental_layers):
            order = i + 1
            trigger = layer['trigger']
            node_count = len(layer['nodes'])
            
            # "click|elem42|로그인" 파싱
            parts = trigger.split('|')
            if len(parts) >= 3:
                action = parts[0]
                elem_id = parts[1]
                elem_text = parts[2]
                trigger_text = f"{elem_id} '{elem_text}' {action}"
            else:
                trigger_text = trigger
            
            summaries.append(f"새로 나타남_{order} ({trigger_text}): {node_count}개 요소")
        
        return '\n'.join(summaries)
    
    # ==================================== 중첩 처리 함수 =========================================
    
    def remove_last_incremental(self) -> None:
        """
        최상위 증분 레이어 제거 (스택 pop)
        
        호출 시점:
        - 드롭다운/모달 닫힘 감지 시
        - MutationObserver로 removed nodes 확인 후
        
        Example:
            # 드롭다운 닫힘
            context_memory.remove_last_incremental()
            # 최상위 레이어 제거, 하위 레이어는 유지
            
            # 빈 스택에서 호출해도 에러 안 남
            context_memory.remove_last_incremental()  # 조용히 무시
        """
        if self.incremental_layers:
            self.incremental_layers.pop()
            
    def get_layer_count(self) -> int:
        """
        현재 증분 레이어 개수 (중첩 깊이)
        
        Returns:
            레이어 개수 (0 = 증분 없음)
        
        Example:
            >>> context_memory.get_layer_count()
            2  # 모달 + 드롭다운
            
            >>> if context_memory.get_layer_count() > 1:
            ...     print("중첩 증분 있음")
        """
        return len(self.incremental_layers)
    
    def get_top_layer_nodes(self) -> List[StandardUINode]:
        """
        최상위 레이어 노드만 반환 (LIFO)
        
        Returns:
            최상위 레이어의 노드 리스트 (빈 리스트 가능)
        
        Example:
            # incremental_loop()에서 사용
            top_nodes = context_memory.get_top_layer_nodes()
            processed = cognitive_layer.process(top_nodes, persona)
        """
        if not self.incremental_layers:
            return []
        return self.incremental_layers[-1]['nodes']
    
    def get_all_nodes(self) -> List[StandardUINode]:
        """
        모든 레이어의 노드를 flatten해서 반환
        
        Returns:
            전체 증분 노드 리스트 (빈 리스트 가능)
        
        Example:
            # 전체 증분 요소 순회
            all_incremental = context_memory.get_all_nodes()
            for node in all_incremental:
                process_node(node)
        """
        all_nodes = []
        for layer in self.incremental_layers:
            all_nodes.extend(layer['nodes'])
        return all_nodes
    
    # ==================================== 유틸 함수 =========================================
    
    def __len__(self) -> int:
        """
        전체 증분 노드 개수 (모든 레이어 합계)
        
        Returns:
            전체 노드 개수
        
        Example:
            >>> len(context_memory)
            5
            >>> if len(context_memory) > 0:
            ...     print("증분 변화 있음")
        """
        total = 0
        for layer in self.incremental_layers:
            total += len(layer['nodes'])
        return total
    
    def __repr__(self) -> str:
        """
        print(context_memory) 예쁘게 출력
        
        Returns:
            읽기 쉬운 문자열
        
        Example:
            >>> print(context_memory)
            ContextMemory(layers=2, total_nodes=5)
        """
        layer_count = len(self.incremental_layers)
        total_nodes = len(self)
        return f"ContextMemory(layers={layer_count}, total_nodes={total_nodes})"