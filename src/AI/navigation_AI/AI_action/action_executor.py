#src/AI/navigation_AI/AI_action/action_executor.py

"""
AI Tool 실행기 - Playwright 액션 수행
Stateless: 메모리/상태 관리 없이 순수 실행만 담당
"""

from typing import Dict, Any
from playwright.sync_api import Page
from normalizer.standard_ui_node import StandardUINode
from .tools import NAVIGATION_TOOLS


class ActionExecutor:
    """
    AI가 선택한 Tool을 Playwright 명령으로 실행
    
    역할:
    - TOOLS 정의 (OpenAI Function Calling 스펙)
    - Tool 실행 (click, fill, declare_success/failure)
    - 실행 결과 반환
    
    NavigationLoop와 협업:
    - NavigationLoop: 의사결정 + 메모리 관리
    - ActionExecutor: 순수 실행
    """
    
    # OpenAI Function Calling 스펙
    TOOLS = NAVIGATION_TOOLS
    
    def __init__(self, page: Page):
        """
        Args:
            page: Playwright Page 객체
        """
        self.page = page
    
    def execute_tool(
        self,
        tool_name: str,
        args: Dict,
        node_map: Dict[str, StandardUINode]
    ) -> Dict[str, Any]:
        """
        Tool 실행 및 결과 반환
        
        Args:
            tool_name: 'click_element', 'fill_input', 'declare_success', 'declare_failure'
            args: Tool 파라미터 (Function Calling arguments)
            node_map: {node_id: StandardUINode} 매핑 (NavigationLoop 제공)
        
        Returns:
            {
                'success': bool,
                'action': str,  # tool_name에서 'element' 제거한 값
                'error': str | None,
                'target_node_id': str | None  # click/fill 시에만
            }
        """
        if tool_name == 'click_element':
            return self._tool_click(args, node_map)
        elif tool_name == 'fill_input':
            return self._tool_fill(args, node_map)
        elif tool_name == 'declare_success':
            return self._tool_success(args)
        elif tool_name == 'declare_failure':
            return self._tool_failure(args)
        elif tool_name == 'go_back':
            return self._tool_go_back(args)
        elif tool_name == 'upload_file':
            return self._tool_upload_file(args, node_map)
        else:
            return {
                'success': False,
                'action': 'unknown',
                'error': f'Unknown tool: {tool_name}',
                'target_node_id': None
            }
    
    def _tool_click(self, args: Dict, node_map: Dict) -> Dict:
        """
        클릭 실행
        
        Args:
            args: {'node_id': str, 'reasoning': str}
            node_map: {node_id: StandardUINode}
        
        Returns:
            {
                'success': bool,
                'action': 'click',
                'error': str | None,
                'target_node_id': str
            }
        """
        node_id = args['node_id']
        
        # node_id 검증
        if node_id not in node_map:
            return {
                'success': False,
                'action': 'click',
                'error': f'Invalid node_id: {node_id}',
                'target_node_id': node_id
            }
        
        node = node_map[node_id]
        
        # text 타입은 클릭 차단 (단, cursor:pointer인 경우 예외)
        if node.type == 'text' and not node.properties.get('is_interactive', False):
            return {
                'success': False,
                'action': 'click',
                'error': f'Cannot click text type node: {node_id}',
                'target_node_id': node_id
            }
    
        xpath = node.metadata.get('xpath')
        
        # xpath 검증
        if not xpath:
            return {
                'success': False,
                'action': 'click',
                'error': f'No xpath for node_id: {node_id}',
                'target_node_id': node_id
            }
        
        # Playwright 클릭 실행
        try:
            context = self.page.context
            pages_before = len(context.pages)
            print(f"[EXEC_CLICK] before: {pages_before} pages, xpath={xpath[:60]}")
            
            self.page.evaluate("""
                (xpath) => {
                    const el = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    if (el) el.scrollIntoView({block: 'start'});
                }
            """, xpath)
            self.page.wait_for_timeout(300)
            
            self.page.click(f"xpath={xpath}", timeout=5000)
            self.page.wait_for_timeout(500)
            
            new_page = None
            for i in range(20):
                if len(context.pages) > pages_before:
                    new_page = context.pages[-1]
                    print(f"[EXEC_CLICK] new tab detected at iter {i}: {new_page.url}")
                    try:
                        new_page.wait_for_load_state('domcontentloaded', timeout=5000)
                    except:
                        pass
                    break
                self.page.wait_for_timeout(100)
            
            if new_page is None:
                print(f"[EXEC_CLICK] no new tab after 2s, pages={len(context.pages)}")
            
            return {
                'success': True,
                'action': 'click',
                'error': None,
                'target_node_id': node_id,
                'new_page': new_page
            }

        except Exception as e:
            return {
                'success': False,
                'action': 'click',
                'error': f'Click failed: {str(e)}',
                'target_node_id': node_id
            }
    
    def _tool_fill(self, args: Dict, node_map: Dict) -> Dict:
        """
        입력 실행
        
        Args:
            args: {'node_id': str, 'text': str}
            node_map: {node_id: StandardUINode}
        
        Returns:
            {
                'success': bool,
                'action': 'fill',
                'error': str | None,
                'target_node_id': str
            }
        """
        node_id = args['node_id']
        text = args['text']
        
        # node_id 검증
        if node_id not in node_map:
            return {
                'success': False,
                'action': 'fill',
                'error': f'Invalid node_id: {node_id}',
                'target_node_id': node_id
            }
        
        node = node_map[node_id]
        xpath = node.metadata.get('xpath')
        
        # xpath 검증
        if not xpath:
            return {
                'success': False,
                'action': 'fill',
                'error': f'No xpath for node_id: {node_id}',
                'target_node_id': node_id
            }
        
        # Playwright fill 실행
        try:
            self.page.fill(f"xpath={xpath}", text, timeout=5000)
            self.page.press(f"xpath={xpath}", "Enter")
            self.page.wait_for_timeout(3000)
            
            return {
                'success': True,
                'action': 'fill',
                'error': None,
                'target_node_id': node_id
            }
        
        except Exception as e:
            return {
                'success': False,
                'action': 'fill',
                'error': f'Fill failed: {str(e)}',
                'target_node_id': node_id
            }
    
    def _tool_success(self, args: Dict) -> Dict:
        """
        목표 달성 선언
        
        Args:
            args: {'reasoning': str}
        
        Returns:
            {
                'success': True,
                'action': 'declare_success',
                'error': None,
                'target_node_id': None
            }
        """
        return {
            'success': True,
            'action': 'declare_success',
            'error': None,
            'target_node_id': None
        }


    def _tool_failure(self, args: Dict) -> Dict:
        """
        실패 선언
        
        Args:
            args: {'reasoning': str}
        
        Returns:
            {
                'success': True,  # Tool 실행 자체는 성공 (의도적 실패 선언)
                'action': 'declare_failure',
                'error': None,
                'target_node_id': None
            }
        """
        return {
            'success': True,
            'action': 'declare_failure',
            'error': None,
            'target_node_id': None
        }
        
    def _tool_go_back(self, args: Dict) -> Dict:
        """
        브라우저 뒤로가기
        
        Args:
            args: {'reasoning': str}
        
        Returns:
            {
                'success': bool,
                'action': 'go_back',
                'error': str | None,
                'target_node_id': None
            }
        """
        try:
            self.page.go_back(timeout=5000)
            self.page.wait_for_timeout(1000)
            
            return {
                'success': True,
                'action': 'go_back',
                'error': None,
                'target_node_id': None
            }
        
        except Exception as e:
            return {
                'success': False,
                'action': 'go_back',
                'error': f'Go back failed: {str(e)}',
                'target_node_id': None
            }

    # 나중을 위해 넣음 더미 파일을 주던 파일 경로를 코딩해야함 지금은 못씀
    def _tool_upload_file(self, args: Dict, node_map: Dict) -> Dict:
        """
        파일 업로드
        
        Args:
            args: {'node_id': str, 'file_path': str}
            node_map: {node_id: StandardUINode}
        
        Returns:
            {
                'success': bool,
                'action': 'upload_file',
                'error': str | None,
                'target_node_id': str
            }
        """
        node_id = args['node_id']
        file_path = args['file_path']
        
        # node_id 검증
        if node_id not in node_map:
            return {
                'success': False,
                'action': 'upload_file',
                'error': f'Invalid node_id: {node_id}',
                'target_node_id': node_id
            }
        
        node = node_map[node_id]
        xpath = node.metadata.get('xpath')
        
        # xpath 검증
        if not xpath:
            return {
                'success': False,
                'action': 'upload_file',
                'error': f'No xpath for node_id: {node_id}',
                'target_node_id': node_id
            }
        
        # Playwright file upload
        try:
            self.page.set_input_files(f"xpath={xpath}", file_path, timeout=5000)
            
            return {
                'success': True,
                'action': 'upload_file',
                'error': None,
                'target_node_id': node_id
            }
        
        except Exception as e:
            return {
                'success': False,
                'action': 'upload_file',
                'error': f'Upload failed: {str(e)}',
                'target_node_id': node_id
            }