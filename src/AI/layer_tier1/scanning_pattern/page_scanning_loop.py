from typing import Dict, List, Tuple
from normalizer.standard_ui_node import StandardUINode
from AI.layer_tier1.fatigue.fatigue_manager import FatigueManager

class SectionNavigator:
    def __init__(self, sections: Dict[str, List[StandardUINode]], fatigue_manager: FatigueManager):
        """
        Args:
            sections: {
                'header': [노드들],  # 이미 Tier 분류됨, Y좌표 정렬됨
                'nav': [...],
                'main': [...]
            }
            fatigue_manager: FatigueManager 인스턴스
        """
        self.sections = sections # 섹션별로 그룹핑된 노드들 (이미 tier 분류 + Y정렬 완료)
        self.section_order = list(sections.keys())  # ['header', 'nav', 'main', 'footer'] 순서
        self.fatigue_manager = fatigue_manager
        
        # 현재 위치
        self.current_section_idx = 0 # 지금 어느 섹션? (0=header, 1=nav, ...)
        self.current_tier_idx = 0 # 지금 어느 tier? (0=상, 1=중, 2=하)
        self.tier_order = ['상', '중', '하'] # 탐색 순서 고정
        
        # 상태
        self.found = False # 목표 찾았는지
        self.is_revisit_mode = False # 재방문 모드인지
        self.skipped_positions = []  # 스킵한 위치들 (FIFO 큐)
    
    def get_elements_for_current_turn(self) -> Tuple[List[StandardUINode], List[StandardUINode]]:
        """
        현재 턴의 요소 반환
        
        Returns:
            (visible_elements, context_elements)
            - visible: 현재 tier 요소
            - context: 다른 tier 요소
        """
        section_name = self.section_order[self.current_section_idx]
        section_nodes = self.sections[section_name]
        
        current_tier = self.tier_order[self.current_tier_idx]
        
        # 현재 tier 요소 (탐색 대상)
        visible = [n for n in section_nodes if n.properties.get('tier') == current_tier]
        
        # 다른 tier 요소 (컨텍스트)
        context = [n for n in section_nodes if n.properties.get('tier') != current_tier]
        
        return visible, context
    
    def get_current_state(self) -> Dict:
        """현재 상태 반환 (로깅용)"""
        section_name = self.section_order[self.current_section_idx]
        current_tier = self.tier_order[self.current_tier_idx]
        
        return {
            'section': section_name,
            'section_idx': self.current_section_idx,
            'tier': current_tier,
            'tier_idx': self.current_tier_idx,
            'found': self.found,
            'is_revisit_mode': self.is_revisit_mode,
            'skipped_count': len(self.skipped_positions)
        }
    
    def move_to_next_tier(self) -> bool:
        """
        다음 tier로 이동 (상→중→하)
        
        Returns:
            bool: 이동 성공 여부
            - True: 다음 tier로 이동 성공
            - False: 더 이상 tier 없음 (섹션 완료)
        """
        self.current_tier_idx += 1
        
        if self.current_tier_idx >= len(self.tier_order):
            # tier 순서 끝남 (상→중→하 다 봄)
            return False
        
        return True
    
    def move_to_next_section(self) -> bool:
        """
        다음 섹션으로 이동
        
        Returns:
            bool: 이동 성공 여부
            - True: 다음 섹션으로 이동 성공
            - False: 더 이상 섹션 없음 (페이지 끝)
        """
        self.current_section_idx += 1
        self.current_tier_idx = 0  # tier는 다시 '상'부터
        self.fatigue_manager.reset_section_fatigue()  # 섹션 피로도 리셋
        
        if self.current_section_idx >= len(self.section_order):
            # 모든 섹션 완료
            return False
        
        return True
    
    def record_skip_position(self) -> None:
        """현재 위치를 스킵 큐에 기록"""
        position = (self.current_section_idx, self.current_tier_idx)
        self.skipped_positions.append(position)
    
    def has_skipped_positions(self) -> bool:
        """재방문할 스킵 위치가 있는가"""
        return len(self.skipped_positions) > 0
    
    def move_to_next_skipped(self) -> bool:
        """
        다음 스킵 위치로 이동 (FIFO)
        
        Returns:
            bool: 이동 성공 여부
            - True: 스킵 위치로 이동 성공
            - False: 더 이상 스킵 위치 없음
        """
        if not self.skipped_positions:
            return False
        
        # FIFO: 첫 번째 요소 꺼내기
        section_idx, tier_idx = self.skipped_positions.pop(0)
        
        self.current_section_idx = section_idx
        self.current_tier_idx = tier_idx
        self.is_revisit_mode = True
        
        return True
    
    def mark_found(self) -> None:
        """목표 발견 시 호출"""
        self.found = True
    
    def is_complete(self) -> bool:
        """
        탐색 완료 여부 (성공 or 포기)
        
        Returns:
            bool: 완료 여부
            - True: found=True (성공) 또는 모든 위치 탐색 완료 (포기)
            - False: 아직 탐색 중
        """
        # 성공: 목표 찾음
        if self.found:
            return True
        
        # 포기: 모든 섹션 다 봤고, 재방문할 곳도 없음
        all_sections_done = self.current_section_idx >= len(self.section_order)
        no_skips_left = len(self.skipped_positions) == 0
        
        if all_sections_done and no_skips_left:
            return True
        
        return False