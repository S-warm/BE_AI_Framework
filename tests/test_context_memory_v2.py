# tests/test_context_memory_v2.py

import pytest
from AI.layer_tier1.memory.context_memory.context_memory import ContextMemory
from normalizer.standard_ui_node import StandardUINode


class TestContextMemoryV2:
    """ContextMemory 스택 구조 테스트"""
    
    def setup_method(self):
        """각 테스트 전 초기화"""
        self.context_memory = ContextMemory()
        
        # 테스트용 노드들 (properties 추가)
        self.modal_nodes = [
            StandardUINode(
                type="button",
                content="닫기",
                properties={"font_size": 14, "position": {"x": 100, "y": 200}}
            ),
            StandardUINode(
                type="input",
                content="이메일",
                properties={"font_size": 14, "position": {"x": 100, "y": 250}}
            )
        ]
        
        self.dropdown_nodes = [
            StandardUINode(
                type="option",
                content="한국",
                properties={"font_size": 14}
            ),
            StandardUINode(
                type="option",
                content="미국",
                properties={"font_size": 14}
            ),
            StandardUINode(
                type="option",
                content="일본",
                properties={"font_size": 14}
            )
        ]
        
        self.tooltip_nodes = [
            StandardUINode(
                type="text",
                content="도움말",
                properties={"font_size": 12}
            )
        ]
    
    # ==================== 기본 동작 ====================
    
    def test_init(self):
        """초기화 테스트"""
        assert self.context_memory.incremental_layers == []
        assert not self.context_memory.has_incremental()
        assert len(self.context_memory) == 0
        assert self.context_memory.get_layer_count() == 0
    
    def test_add_single_layer(self):
        """단일 레이어 추가"""
        self.context_memory.add_incremental(
            self.modal_nodes,
            "click|elem42|로그인"
        )
        
        assert self.context_memory.has_incremental()
        assert len(self.context_memory) == 2  # modal_nodes 2개
        assert self.context_memory.get_layer_count() == 1
        
        # 레이어 구조 확인
        assert len(self.context_memory.incremental_layers) == 1
        layer = self.context_memory.incremental_layers[0]
        assert layer['nodes'] == self.modal_nodes
        assert layer['trigger'] == "click|elem42|로그인"
    
    def test_add_multiple_layers(self):
        """여러 레이어 추가 (중첩)"""
        # 레이어 1: 모달
        self.context_memory.add_incremental(
            self.modal_nodes,
            "click|elem42|로그인"
        )
        
        # 레이어 2: 드롭다운
        self.context_memory.add_incremental(
            self.dropdown_nodes,
            "click|elem50|국가선택"
        )
        
        assert self.context_memory.get_layer_count() == 2
        assert len(self.context_memory) == 5  # 2 + 3
        
        # 스택 순서 확인
        assert self.context_memory.incremental_layers[0]['trigger'] == "click|elem42|로그인"
        assert self.context_memory.incremental_layers[1]['trigger'] == "click|elem50|국가선택"
    
    def test_clear_incremental(self):
        """전체 클리어"""
        self.context_memory.add_incremental(self.modal_nodes, "click|elem42|로그인")
        self.context_memory.add_incremental(self.dropdown_nodes, "click|elem50|국가선택")
        
        self.context_memory.clear_incremental()
        
        assert not self.context_memory.has_incremental()
        assert len(self.context_memory) == 0
        assert self.context_memory.get_layer_count() == 0
        assert self.context_memory.incremental_layers == []
    
    # ==================== 스택 동작 ====================
    
    def test_remove_last_incremental(self):
        """최상위 레이어 제거 (pop)"""
        # 2개 레이어 추가
        self.context_memory.add_incremental(self.modal_nodes, "click|elem42|로그인")
        self.context_memory.add_incremental(self.dropdown_nodes, "click|elem50|국가선택")
        
        # 최상위 제거
        self.context_memory.remove_last_incremental()
        
        assert self.context_memory.get_layer_count() == 1
        assert len(self.context_memory) == 2  # modal_nodes만
        assert self.context_memory.incremental_layers[0]['trigger'] == "click|elem42|로그인"
    
    def test_remove_last_on_empty(self):
        """빈 스택에서 pop (에러 안 남)"""
        self.context_memory.remove_last_incremental()
        
        assert self.context_memory.get_layer_count() == 0
        assert not self.context_memory.has_incremental()
    
    def test_nested_incremental_flow(self):
        """중첩 증분 시나리오"""
        # 1. 모달 열림
        self.context_memory.add_incremental(self.modal_nodes, "click|elem42|로그인")
        assert self.context_memory.get_layer_count() == 1
        
        # 2. 드롭다운 열림
        self.context_memory.add_incremental(self.dropdown_nodes, "click|elem51|국가")
        assert self.context_memory.get_layer_count() == 2
        
        # 3. 툴팁 열림
        self.context_memory.add_incremental(self.tooltip_nodes, "hover|elem60|한국")
        assert self.context_memory.get_layer_count() == 3
        assert len(self.context_memory) == 6  # 2 + 3 + 1
        
        # 4. 툴팁 닫힘
        self.context_memory.remove_last_incremental()
        assert self.context_memory.get_layer_count() == 2
        assert len(self.context_memory) == 5  # 2 + 3
        
        # 5. 드롭다운 닫힘
        self.context_memory.remove_last_incremental()
        assert self.context_memory.get_layer_count() == 1
        assert len(self.context_memory) == 2  # 2
        
        # 6. 모달 닫힘
        self.context_memory.remove_last_incremental()
        assert not self.context_memory.has_incremental()
    
    # ==================== 노드 조회 ====================
    
    def test_get_top_layer_nodes(self):
        """최상위 레이어 노드만 반환"""
        self.context_memory.add_incremental(self.modal_nodes, "click|elem42|로그인")
        self.context_memory.add_incremental(self.dropdown_nodes, "click|elem50|국가")
        
        top_nodes = self.context_memory.get_top_layer_nodes()
        
        assert len(top_nodes) == 3  # dropdown_nodes
        assert top_nodes == self.dropdown_nodes
    
    def test_get_top_layer_nodes_empty(self):
        """빈 스택에서 최상위 조회"""
        top_nodes = self.context_memory.get_top_layer_nodes()
        
        assert top_nodes == []
    
    def test_get_all_nodes(self):
        """모든 레이어 flatten"""
        self.context_memory.add_incremental(self.modal_nodes, "click|elem42|로그인")
        self.context_memory.add_incremental(self.dropdown_nodes, "click|elem50|국가")
        
        all_nodes = self.context_memory.get_all_nodes()
        
        assert len(all_nodes) == 5  # 2 + 3
        assert all_nodes[:2] == self.modal_nodes
        assert all_nodes[2:] == self.dropdown_nodes
    
    def test_get_all_nodes_empty(self):
        """빈 스택에서 전체 조회"""
        all_nodes = self.context_memory.get_all_nodes()
        
        assert all_nodes == []
    
    # ==================== Summary ====================
    
    def test_get_incremental_summary_single_layer(self):
        """단일 레이어 요약"""
        self.context_memory.add_incremental(self.modal_nodes, "click|elem42|로그인")
        
        summary = self.context_memory.get_incremental_summary()
        
        assert "새로 나타남_1" in summary
        assert "elem42" in summary
        assert "로그인" in summary
        assert "2개 요소" in summary
    
    def test_get_incremental_summary_multiple_layers(self):
        """여러 레이어 요약"""
        self.context_memory.add_incremental(self.modal_nodes, "click|elem42|로그인")
        self.context_memory.add_incremental(self.dropdown_nodes, "click|elem50|국가선택")
        
        summary = self.context_memory.get_incremental_summary()
        
        # 레이어별 출력 확인
        assert "새로 나타남_1" in summary
        assert "elem42" in summary
        assert "2개 요소" in summary
        
        assert "새로 나타남_2" in summary
        assert "elem50" in summary
        assert "3개 요소" in summary
        
        # 줄바꿈 확인
        lines = summary.split('\n')
        assert len(lines) == 2
    
    def test_get_incremental_summary_empty(self):
        """빈 스택 요약"""
        summary = self.context_memory.get_incremental_summary()
        
        assert summary == ""
    
    def test_get_incremental_summary_malformed_trigger(self):
        """잘못된 trigger 형식"""
        self.context_memory.add_incremental(self.modal_nodes, "invalid_trigger")
        
        summary = self.context_memory.get_incremental_summary()
        
        # 파싱 실패 시 원본 그대로
        assert "invalid_trigger" in summary
    
    # ==================== Utilities ====================
    
    def test_len(self):
        """__len__ 테스트"""
        assert len(self.context_memory) == 0
        
        self.context_memory.add_incremental(self.modal_nodes, "click|elem42|로그인")
        assert len(self.context_memory) == 2
        
        self.context_memory.add_incremental(self.dropdown_nodes, "click|elem50|국가")
        assert len(self.context_memory) == 5
        
        self.context_memory.remove_last_incremental()
        assert len(self.context_memory) == 2
    
    def test_repr(self):
        """__repr__ 테스트"""
        # 빈 상태
        repr_str = repr(self.context_memory)
        assert "layers=0" in repr_str
        assert "total_nodes=0" in repr_str
        
        # 레이어 추가 후
        self.context_memory.add_incremental(self.modal_nodes, "click|elem42|로그인")
        self.context_memory.add_incremental(self.dropdown_nodes, "click|elem50|국가")
        
        repr_str = repr(self.context_memory)
        assert "layers=2" in repr_str
        assert "total_nodes=5" in repr_str
    
    def test_get_layer_count(self):
        """레이어 개수 조회"""
        assert self.context_memory.get_layer_count() == 0
        
        self.context_memory.add_incremental(self.modal_nodes, "click|elem42|로그인")
        assert self.context_memory.get_layer_count() == 1
        
        self.context_memory.add_incremental(self.dropdown_nodes, "click|elem50|국가")
        assert self.context_memory.get_layer_count() == 2
        
        self.context_memory.remove_last_incremental()
        assert self.context_memory.get_layer_count() == 1
        
        self.context_memory.clear_incremental()
        assert self.context_memory.get_layer_count() == 0
    
    # ==================== Edge Cases ====================
    
    def test_multiple_remove_last(self):
        """연속 pop"""
        self.context_memory.add_incremental(self.modal_nodes, "click|elem42|로그인")
        
        self.context_memory.remove_last_incremental()
        self.context_memory.remove_last_incremental()  # 빈 스택
        self.context_memory.remove_last_incremental()  # 빈 스택
        
        # 에러 안 남
        assert self.context_memory.get_layer_count() == 0
    
    def test_add_after_clear(self):
        """클리어 후 재추가"""
        self.context_memory.add_incremental(self.modal_nodes, "click|elem42|로그인")
        self.context_memory.clear_incremental()
        self.context_memory.add_incremental(self.dropdown_nodes, "click|elem50|국가")
        
        assert self.context_memory.get_layer_count() == 1
        assert len(self.context_memory) == 3
        
        top = self.context_memory.get_top_layer_nodes()
        assert top == self.dropdown_nodes