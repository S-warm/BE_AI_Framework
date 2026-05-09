"""
NavigationLoop 통합 테스트
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List

from AI.navigation_AI.navigation_loop.navigation_loop import NavigationLoop
from normalizer.standard_ui_node import StandardUINode


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Shared Fixtures (모든 테스트 클래스가 사용)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.fixture
def mock_page():
    """Mock Playwright Page"""
    page = Mock()
    page.url = "https://test.com"
    return page


@pytest.fixture
def mock_normalizer():
    """Mock WebNormalizerIncremental"""
    normalizer = Mock()
    
    # 기본 파싱 결과
    nodes = [
        StandardUINode(
            id="elem1",
            type="button",
            content="로그인",
            properties={'x': 100, 'y': 50, 'width': 80, 'height': 40, 'tier': '상'},
            metadata={}
        ),
        StandardUINode(
            id="elem2",
            type="link",
            content="회원가입",
            properties={'x': 200, 'y': 50, 'width': 80, 'height': 40, 'tier': '상'},
            metadata={}
        ),
        StandardUINode(
            id="elem3",
            type="input",
            content="",
            properties={'x': 150, 'y': 100, 'width': 200, 'height': 30, 'tier': '중'},
            metadata={}
        )
    ]
    normalizer.normalize.return_value = nodes
    return normalizer


@pytest.fixture
def mock_navigator_ai():
    """Mock OpenAI client"""
    ai = Mock()
    
    # side_effect 제거, return_value만 사용
    ai.call.return_value = {
        'found': False,
        'element_id': 0,
        'action_type': 'declare_success',
        'reasoning': '목표 달성'
    }
    
    return ai


@pytest.fixture
def navigation_loop(mock_page, mock_normalizer, mock_navigator_ai, tmp_path):
    """NavigationLoop 인스턴스"""
    db_file = tmp_path / "test_cache.db"
    return NavigationLoop(
        page=mock_page,
        normalizer=mock_normalizer,
        navigator_ai=mock_navigator_ai,
        db_path=str(db_file)  # 파일 경로 사용
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 테스트 클래스들
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestNavigationLoopIntegration:
    """NavigationLoop 통합 테스트"""

    def test_initialization(self, navigation_loop):
        """초기화 테스트"""
        # 캐싱 시스템
        assert navigation_loop.parsing_cache is not None
        assert navigation_loop.incremental_cache is not None
        
        # 메모리 시스템
        assert navigation_loop.context_memory is not None
        assert navigation_loop.page_history is not None
        assert navigation_loop.section_memory is not None
        
        # 액션 실행기
        assert navigation_loop.executor is not None
        
        # run() 전에는 None
        assert navigation_loop.fatigue_manager is None
        assert navigation_loop.navigation_memory is None
        assert navigation_loop.incremental_scanner is None

    def test_run_success_scenario(self, navigation_loop, mock_page):
        """성공 시나리오 테스트"""
        persona = {
            'age_group': '50s',
            'digital_literacy': 'medium'
        }
        
        with patch.object(navigation_loop.executor, 'execute_tool') as mock_execute:
            mock_execute.return_value = {
                'success': True,
                'action': 'declare_success',
                'error': None,
                'target_node_id': 'elem1'
            }
            
            result = navigation_loop.run("로그인하기", persona)
        
        assert result['status'] == 'success'
        assert result['total_steps'] >= 0
        assert 'actions' in result
        assert 'cache_stats' in result

    def test_run_creates_persona_dependent_components(self, navigation_loop):
        """Persona 의존 컴포넌트 생성 테스트"""
        persona = {
            'age_group': '70s',
            'digital_literacy': 'low'
        }
        
        with patch.object(navigation_loop.executor, 'execute_tool') as mock_execute:
            mock_execute.return_value = {
                'success': True,
                'action': 'declare_success',
                'error': None,
                'target_node_id': 'elem1'
            }
            
            navigation_loop.run("테스트", persona)
        
        assert navigation_loop.fatigue_manager is not None
        assert navigation_loop.navigation_memory is not None
        assert navigation_loop.incremental_scanner is not None
        assert navigation_loop.working_memory_limit == 5

    def test_working_memory_limit_by_age(self, navigation_loop, mock_navigator_ai):
        """연령대별 Working Memory 한계 테스트"""
        test_cases = [
            ('20s', 9),
            ('50s', 7),
            ('70s', 5)
        ]
        
        for age_group, expected_limit in test_cases:
            persona = {'age_group': age_group, 'digital_literacy': 'medium'}
            
            # AI 응답 재설정
            mock_navigator_ai.call.return_value = {
                'found': False,
                'element_id': 0,
                'action_type': 'declare_success',
                'reasoning': '목표 달성'
            }
            
            with patch.object(navigation_loop.executor, 'execute_tool') as mock_execute:
                mock_execute.return_value = {
                    'success': True,
                    'action': 'declare_success',
                    'error': None,
                    'target_node_id': 'elem1'
                }
                
                navigation_loop.run("테스트", persona)
                assert navigation_loop.working_memory_limit == expected_limit

    def test_url_changed_detection(self, navigation_loop, mock_page):
        """URL 변경 감지 테스트"""
        navigation_loop.current_url = "https://test.com"
        
        mock_page.url = "https://test.com"
        assert navigation_loop._url_changed() is False
        
        mock_page.url = "https://test.com/login"
        assert navigation_loop._url_changed() is True

    def test_parsing_cache_hit(self, navigation_loop, mock_normalizer):
        """파싱 캐시 히트 테스트"""
        url = "https://test.com"
        
        # 첫 호출
        nodes1 = navigation_loop._parse_with_cache(url)
        
        # DB 직접 확인
        import sqlite3
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        print("테이블:", cursor.fetchall())
        conn.close()
        
        # 실제 캐시 DB 확인
        conn2 = sqlite3.connect(navigation_loop.parsing_cache.db_path)
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT COUNT(*) FROM parsing_cache")
        count = cursor2.fetchone()[0]
        print(f"캐시된 항목 수: {count}")
        conn2.close()
        
        cached = navigation_loop.parsing_cache.get(url)
        assert cached is not None, "캐시 저장 실패"

    def test_tier1_processing(self, navigation_loop, mock_normalizer):
        """Tier 1 처리 테스트"""
        nodes = mock_normalizer.normalize.return_value
        
        sections = navigation_loop._process_tier1(nodes)
        
        assert isinstance(sections, dict)
        assert 'header' in sections or 'main' in sections
        
        for section_nodes in sections.values():
            for node in section_nodes:
                assert 'tier' in node.properties

    def test_execute_action_invalid_element_id(self, navigation_loop):
        """잘못된 element_id 처리 테스트"""
        response = {
            'element_id': 999,
            'action_type': 'click',
            'reasoning': '테스트'
        }
        
        visible = [
            StandardUINode(
                id="elem1",
                type="button",
                content="테스트",
                properties={},
                metadata={}
            )
        ]
        
        result = navigation_loop._execute_action(response, visible, '상')
        
        assert result['success'] is False
        assert result['action'] == 'error'
        assert 'Invalid element_id' in result['error']

    def test_build_full_prompt_includes_memory(self, navigation_loop):
        """프롬프트에 메모리 컨텍스트 포함 테스트"""
        from AI.navigation_AI.AI_memory.navigation_memory import NavigationMemory
        navigation_loop.navigation_memory = NavigationMemory("테스트")
        navigation_loop.navigation_memory.add_action(
            action='click',
            element_id='elem1',
            element_text='로그인',
            result='success'
        )
        
        visible = []
        context = []
        
        prompt = navigation_loop._build_full_prompt(visible, context, '상', "테스트")
        
        assert '<최근_행동>' in prompt
        assert '<페이지_히스토리>' in prompt
        assert '<이미_확인한_섹션>' in prompt

    def test_make_trigger(self, navigation_loop):
        """trigger 문자열 생성 테스트"""
        result = {
            'action': 'click',
            'target_node_id': 'elem42',
            'text': '로그인'
        }
        
        trigger = navigation_loop._make_trigger(result)
        assert trigger == "click|elem42|로그인"

    def test_timeout_scenario(self, navigation_loop, mock_navigator_ai):
        """타임아웃 시나리오 테스트"""
        navigation_loop.max_steps = 2
        
        mock_navigator_ai.call.return_value = {
            'found': True,
            'found_tier': '상',
            'element_id': 0,
            'action_type': 'click',
            'reasoning': '계속 클릭'
        }
        
        with patch.object(navigation_loop.executor, 'execute_tool') as mock_execute:
            mock_execute.return_value = {
                'success': True,
                'action': 'click',
                'error': None,
                'target_node_id': 'elem1'
            }
            
            persona = {'age_group': '50s', 'digital_literacy': 'medium'}
            result = navigation_loop.run("테스트", persona)
        
        assert result['status'] == 'timeout'
        assert result['total_steps'] == navigation_loop.max_steps


class TestNavigationLoopIncrementalHandling:
    """증분 처리 테스트"""

    @pytest.fixture
    def setup_with_incremental(self, mock_page, mock_normalizer, mock_navigator_ai):
        """증분 처리 테스트용 설정"""
        loop = NavigationLoop(
            page=mock_page,
            normalizer=mock_normalizer,
            navigator_ai=mock_navigator_ai,
            db_path=":memory:"
        )
        
        delta_nodes = [
            StandardUINode(
                id="modal_elem1",
                type="button",
                content="확인",
                properties={'tier': '상'},
                metadata={}
            )
        ]
        loop.context_memory.add_incremental(delta_nodes, "click|elem1|로그인")
        
        return loop

    def test_incremental_detection(self, setup_with_incremental):
        """증분 감지 테스트"""
        loop = setup_with_incremental
        assert loop.context_memory.has_incremental() is True

    def test_incremental_cache(self, navigation_loop, mock_page):
        """증분 캐시 테스트"""
        result = {
            'action': 'click',
            'target_node_id': 'elem1',
            'text': ''
        }
        mock_page.url = "https://test.com"
        
        delta1 = navigation_loop._parse_incremental_with_cache(result)
        delta2 = navigation_loop._parse_incremental_with_cache(result)
        
        assert delta1 == delta2


class TestNavigationLoopMemoryIntegration:
    """메모리 시스템 통합 테스트"""

    @pytest.fixture
    def loop_with_memory(self, mock_page, mock_normalizer, mock_navigator_ai):
        """메모리 설정된 NavigationLoop"""
        loop = NavigationLoop(
            page=mock_page,
            normalizer=mock_normalizer,
            navigator_ai=mock_navigator_ai,
            db_path=":memory:"
        )
        
        from AI.navigation_AI.AI_memory.navigation_memory import NavigationMemory
        from AI.layer_tier1.fatigue.fatigue_manager import FatigueManager  # 추가
        
        loop.navigation_memory = NavigationMemory("테스트 목표")
        loop.fatigue_manager = FatigueManager({'age_group': '50s', 'digital_literacy': 'medium'})  # 추가
        
        return loop

    def test_navigation_memory_recording(self, loop_with_memory):
        """행동 기록 테스트"""
        response = {
            'element_id': 0,
            'action_type': 'click',
            'reasoning': '로그인 클릭'
        }
        
        visible = [
            StandardUINode(
                id="elem1",
                type="button",
                content="로그인",
                properties={},
                metadata={}
            )
        ]
        
        with patch.object(loop_with_memory.executor, 'execute_tool') as mock_execute:
            mock_execute.return_value = {
                'success': True,
                'action': 'click',
                'error': None,
                'target_node_id': 'elem1'
            }
            
            loop_with_memory._execute_action(response, visible, '상')
        
        actions = loop_with_memory.navigation_memory.get_all_actions()
        assert len(actions) > 0
        assert actions[0]['action'] == 'click'

    def test_page_history_update(self, loop_with_memory, mock_page):
        """페이지 히스토리 업데이트 테스트"""
        mock_page.url = "https://test.com/page1"
        loop_with_memory.current_url = "https://test.com/page1"
        
        loop_with_memory._update_page_history()
        
        assert loop_with_memory.page_history.get_page_count() > 0

    def test_section_memory_caching(self, loop_with_memory, mock_page):
        """섹션 메모리 캐싱 테스트"""
        url = "https://test.com"
        mock_page.url = url
        
        loop_with_memory.section_memory.set_current_url(url)
        loop_with_memory.section_memory.save_section_result(
            section='header',
            summary='로고, 메뉴',
            found_target=False,
            ux_issues=[],
            explored_tiers=['상'],
            visited_elements=['elem1']
        )
        
        assert loop_with_memory.section_memory.has_visited('header') is True
        assert '상' in loop_with_memory.section_memory.get_explored_tiers('header')


class TestNavigationLoopEdgeCases:
    """엣지 케이스 테스트"""

    def test_empty_page(self, mock_page, mock_navigator_ai):
        """빈 페이지 처리"""
        mock_normalizer = Mock()
        mock_normalizer.normalize.return_value = []
        
        loop = NavigationLoop(
            page=mock_page,
            normalizer=mock_normalizer,
            navigator_ai=mock_navigator_ai,
            db_path=":memory:"
        )
        
        persona = {'age_group': '50s', 'digital_literacy': 'medium'}
        
        with patch.object(loop.executor, 'execute_tool') as mock_execute:
            mock_execute.return_value = {
                'success': True,
                'action': 'declare_failure',
                'error': None,
                'target_node_id': None
            }
            
            result = loop.run("테스트", persona)
        
        assert result['status'] in ['timeout', 'failure']

    def test_url_change_during_navigation(self, mock_page, mock_normalizer, mock_navigator_ai):
        """탐색 중 URL 변경"""
        loop = NavigationLoop(
            page=mock_page,
            normalizer=mock_normalizer,
            navigator_ai=mock_navigator_ai,
            db_path=":memory:"
        )
        
        urls = ["https://test.com", "https://test.com/login"]
        mock_page.url = urls[0]
        loop.current_url = urls[0]
        
        with patch.object(loop.executor, 'execute_tool') as mock_execute:
            def side_effect(*args, **kwargs):
                mock_page.url = urls[1]
                return {
                    'success': True,
                    'action': 'click',
                    'error': None,
                    'target_node_id': 'elem1'
                }
            
            mock_execute.side_effect = side_effect
            
            assert loop._url_changed() is False
            mock_execute(tool_name='click_element', args={}, node_map={})
            assert loop._url_changed() is True




if __name__ == '__main__':
    pytest.main([__file__, '-v'])