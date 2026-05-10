"""
IncrementalScanner - 증분 레이어 탐색 패턴
"""

from typing import Dict, List, Optional
from normalizer.standard_ui_node import StandardUINode
from AI.layer_tier1.scanning_pattern.element.element_classify import classify_by_percentile
from AI.layer_tier1.scanning_pattern.utils.sorter import sort_by_y_position
from AI.layer_tier2.base_persona import BasePersona


class IncrementalScanner:
    """증분 레이어 탐색 패턴"""
    
    def __init__(
        self,
        prompt_builder,
        executor,
        navigator_ai,
        fatigue_manager
    ):
        self.prompt_builder = prompt_builder
        self.executor = executor
        self.navigator_ai = navigator_ai
        self.fatigue_manager = fatigue_manager
    
    def scan(
        self,
        context_memory,
        navigation_memory,
        normalizer,
        page,
        persona: BasePersona,
        goal: str,
        current_url: str,
        frozen_section_state: Dict,
        parsed_task: Dict = None,
        success_condition: Dict = None
    ) -> Dict:
        """
        최상위 증분 레이어 탐색
        
        Args:
            frozen_section_state: {
                'section_name': 'header',
                'tier': '상',
                'visible_elements': [...],
                'context_elements': [...]
            }
        """
        # 1. 최상위 레이어 노드
        top_nodes = context_memory.get_top_layer_nodes()
        
        if not top_nodes:
            return {
                'action': 'none',
                'closed': False,
                'nested': False,
                'complete': False
            }
        
        # 2. Tier 분류
        classified_nodes = classify_by_percentile(top_nodes)
        
        # 3. Y축 정렬
        sorted_nodes = sort_by_y_position(classified_nodes)
        
        # 4. node_map 생성
        node_map = {node.id: node for node in sorted_nodes}
        
        # 5. Tier별 순회
        for tier in ['상', '중', '하']:
            
            # 피로도 체크
            if self.fatigue_manager.is_globally_exhausted():
                return {
                    'action': 'fatigue_exhausted',
                    'closed': False,
                    'nested': False,
                    'complete': False
                }
            
            # 현재 tier 노드만
            tier_nodes = [n for n in sorted_nodes if n.properties.get('tier') == tier]
            
            if not tier_nodes:
                continue
            
            # 6. 프롬프트 생성
            prompt = self.prompt_builder(
                visible_elements=tier_nodes,
                all_layers=context_memory.incremental_layers,
                frozen_section_state=frozen_section_state,
                current_tier=tier,
                goal=goal,
                recent_actions=navigation_memory.get_recent(7),
                explored_tiers=frozen_section_state.get('explored_tiers', []),
                success_condition=parsed_task['success_condition'] if parsed_task else None
            )
            
            # 7. AI 호출
            response = self.navigator_ai.call(prompt)
            
            # found=false면 다음 tier
            if not response.get('found', False):
                if response.get('action_type') != 'click':
                    continue
            
            # 8. 응답 파싱
            element_id = response['element_id']
            action_type = response.get('action_type', 'click')
            reasoning = response.get('reasoning', '')
            
            # 9. 인덱스 → node_id 변환
            if element_id >= len(tier_nodes):
                # 잘못된 인덱스
                continue
            
            target_node = tier_nodes[element_id]
            node_id = target_node.id
            
            # 10. action_type → tool_name 매핑
            tool_map = {
                'click': 'click_element',
                'close': 'click_element',
                'declare_success': 'declare_success',
                'declare_failure': 'declare_failure'
            }
            tool_name = tool_map.get(action_type, 'click_element')
            
            # 11. 액션 실행
            result = self.executor.execute_tool(
                tool_name=tool_name,
                args={'node_id': node_id, 'reasoning': reasoning},
                node_map=node_map
            )
            
            # 12. 행동 기록
            navigation_memory.add_action(
                action=result['action'],
                element_id=node_id,
                element_text=reasoning,
                result='success' if result['success'] else 'failure'
            )
            
            # 13. 피로도 증가
            self.fatigue_manager.add_fatigue(tier)
            
            # 14. 종료 조건
            if result['action'] == 'declare_success':
                reason = self._verify_success(page, success_condition)
                if reason:
                    # 실패 → complete=False로 반환, NavigationLoop에서 피드백 처리
                    return {
                        'action': 'verify_failed',
                        'closed': False,
                        'nested': False,
                        'complete': False,
                        'verify_fail_reason': reason
                    }
            
            # 15. 중첩 증분 감지
            if result['action'] == 'click' and page.url == current_url:
                page.wait_for_timeout(1000)
                clicked_xpath = target_node.metadata.get('xpath') if target_node else None
                delta = normalizer.normalize(page, clicked_xpath)
                
                if delta:
                    meta = target_node.metadata or {}
                    html_id = meta.get('html_id', '')
                    stable_id = html_id if html_id else f"{meta.get('html_tag', '')}:{target_node.content[:20]}"
                    trigger = f"{result['action']}|{stable_id}"
                    context_memory.add_incremental(delta, trigger)
                    
                    # 재귀
                    nested_result = self.scan(
                        context_memory=context_memory,
                        navigation_memory=navigation_memory,
                        normalizer=normalizer,
                        page=page,
                        persona=persona,
                        goal=goal,
                        current_url=current_url,
                        frozen_section_state=frozen_section_state
                    )
                    
                    return {
                        'action': nested_result['action'],
                        'closed': nested_result['closed'],
                        'nested': True,
                        'complete': nested_result['complete']
                    }
            
            # 16. 닫힘 감지
            if action_type == 'close':  # AI 응답의 action_type 체크
                delta = normalizer.normalize(page)
                
                if delta and self._has_removed_nodes(delta):
                    context_memory.remove_last_incremental()
                    
                    return {
                        'action': result['action'],
                        'closed': True,
                        'nested': False,
                        'complete': False
                    }
        
        # 모든 tier 탐색 완료
        return {
            'action': 'scan_complete',
            'closed': False,
            'nested': False,
            'complete': False
        }
    
    # 성공 검증 메서드
    def _verify_success(self, page, success_condition) -> Optional[str]:
        import urllib.parse
        if not success_condition:
            return None
        current_url = page.url
        if success_condition.get('path') and success_condition['path'] not in current_url:
            return f"아직 목표 페이지 아님 (현재: {current_url})"
        parsed = urllib.parse.urlparse(current_url)
        params = urllib.parse.parse_qs(parsed.query)
        for key, value in success_condition.get('required_params', {}).items():
            actual = params.get(key, [None])[0]
            if actual != value:
                return f"파라미터 불일치: {key}={actual} (필요: {value})"
        return None
    
    def _has_removed_nodes(self, delta_nodes: List[StandardUINode]) -> bool:
        """removed 노드 확인"""
        return any(node.properties.get('removed', False) for node in delta_nodes)