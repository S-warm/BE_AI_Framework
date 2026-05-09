"""
Phase 1 통합 테스트
DOM → Preattentive → Scanning Pattern → Navigator 전체 파이프라인 검증
"""

import pytest
from playwright.sync_api import sync_playwright
from pathlib import Path
from dotenv import load_dotenv
import os

# .env 로드
load_dotenv()  # 추가

from normalizer.mcp.web_normalizer.web_normalizer_incremental import WebNormalizerIncremental
from AI.layer_tier1.pre_attentive.pre_attentive import apply_preattentive_priority
from AI.layer_tier1.scanning_pattern.section.section_grouper import group_by_html_tag
from AI.layer_tier1.scanning_pattern.element.element_classify import classify_by_percentile
from AI.layer_tier1.scanning_pattern.utils.sorter import sort_by_y_position
from AI.layer_tier1.scanning_pattern.page_scanning_loop import SectionNavigator
from AI.layer_tier1.fatigue.fatigue_manager import FatigueManager
from AI.layer_tier1.scanning_pattern.utils.prompt_builder import build_prompt


@pytest.fixture
def test_html_path():
    """테스트 HTML 파일 경로"""
    return Path(__file__).parent.parent / "fixtures" / "test_page.html"


@pytest.fixture
def parsed_nodes(test_html_path):
    """HTML 파싱 → StandardUINode 리스트"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"file://{test_html_path.absolute()}")
        
        normalizer = WebNormalizerIncremental()
        nodes = normalizer.normalize(page)
        
        browser.close()
        return nodes


def test_1_dom_parsing(parsed_nodes):
    """1단계: DOM 파싱 성공"""
    assert len(parsed_nodes) > 0, "노드가 파싱되어야 함"
    
    # 기본 속성 존재 확인
    for node in parsed_nodes:
        assert hasattr(node, 'type')
        assert hasattr(node, 'content')
        assert hasattr(node, 'properties')
        assert hasattr(node, 'metadata')


def test_2_preattentive_priority(parsed_nodes):
    """2단계: Preattentive 우선순위 계산"""
    nodes, stats = apply_preattentive_priority(
        nodes=parsed_nodes,
        viewport_size=(1920, 1080)
    )
    
    # visual_priority 추가되었는지
    for node in nodes:
        assert 'visual_priority' in node.properties
        priority = node.properties['visual_priority']
        assert 0.0 <= priority <= 1.0, "우선순위는 0~1 범위"
    
    # 통계 반환 확인
    assert 'avg_size' in stats
    assert 'avg_weight' in stats
    assert 'page_bg' in stats


def test_3_section_grouping(parsed_nodes):
    """3단계: 섹션 그룹핑"""
    # preattentive 먼저 적용
    nodes, _ = apply_preattentive_priority(parsed_nodes, (1920, 1080))
    
    sections = group_by_html_tag(nodes)
    
    # 섹션 존재 확인
    assert 'header' in sections, "header 섹션 있어야 함"
    assert 'main' in sections, "main 섹션 있어야 함"
    assert len(sections['header']) > 0
    assert len(sections['main']) > 0


def test_4_tier_classification(parsed_nodes):
    """4단계: Tier 분류"""
    nodes, _ = apply_preattentive_priority(parsed_nodes, (1920, 1080))
    sections = group_by_html_tag(nodes)
    
    # 각 섹션별 tier 분류
    for section_name, section_nodes in sections.items():
        classified = classify_by_percentile(section_nodes)
        
        # tier 할당 확인
        for node in classified:
            assert 'tier' in node.properties
            assert node.properties['tier'] in ['상', '중', '하']


def test_5_sorting(parsed_nodes):
    """5단계: Y좌표 정렬"""
    nodes, _ = apply_preattentive_priority(parsed_nodes, (1920, 1080))
    
    sorted_nodes = sort_by_y_position(nodes)
    
    # Y좌표 오름차순 확인
    y_coords = [n.properties.get('y', 0) for n in sorted_nodes]
    assert y_coords == sorted(y_coords), "Y좌표 오름차순이어야 함"


def test_6_section_navigator(parsed_nodes):
    """6단계: SectionNavigator 순회"""
    # 파이프라인 전체 실행
    nodes, _ = apply_preattentive_priority(parsed_nodes, (1920, 1080))
    sections = group_by_html_tag(nodes)
    
    # 각 섹션 tier 분류 + 정렬
    for section_name in sections:
        sections[section_name] = classify_by_percentile(sections[section_name])
        sections[section_name] = sort_by_y_position(sections[section_name])
    
    # Navigator 초기화
    persona = {'age_group': '70s'}
    fatigue_mgr = FatigueManager(persona)
    navigator = SectionNavigator(sections, fatigue_mgr)
    
    # 초기 상태 확인
    state = navigator.get_current_state()
    assert state['section_idx'] == 0
    assert state['tier_idx'] == 0
    assert state['tier'] == '상'
    
    # 요소 가져오기
    visible, context = navigator.get_elements_for_current_turn()
    assert isinstance(visible, list)
    assert isinstance(context, list)
    
    # tier 이동
    moved = navigator.move_to_next_tier()
    assert moved == True
    assert navigator.get_current_state()['tier'] == '중'


def test_7_fatigue_accumulation(parsed_nodes):
    """7단계: 피로도 누적"""
    persona = {'age_group': '70s'}
    fatigue_mgr = FatigueManager(persona)
    
    # 초기 피로도 0
    assert fatigue_mgr.section_fatigue == 0.0
    assert fatigue_mgr.global_fatigue == 0.0
    
    # 상 tier 읽기
    fatigue_mgr.add_fatigue('상', is_revisit=False)
    assert fatigue_mgr.section_fatigue == 0.05
    assert fatigue_mgr.global_fatigue == 0.05
    
    # 중 tier 재방문 (2배 비용)
    fatigue_mgr.add_fatigue('중', is_revisit=True)
    expected = 0.075 * 2.0  # 0.15
    assert fatigue_mgr.section_fatigue == 0.05 + expected
    
    # 임계값 확인
    assert fatigue_mgr.section_threshold == 0.5  # 70s 기준
    assert fatigue_mgr.global_threshold == 1.5


def test_8_prompt_generation(parsed_nodes):
    """8단계: 프롬프트 생성"""
    # 파이프라인 실행
    nodes, _ = apply_preattentive_priority(parsed_nodes, (1920, 1080))
    sections = group_by_html_tag(nodes)
    
    for section_name in sections:
        sections[section_name] = classify_by_percentile(sections[section_name])
        sections[section_name] = sort_by_y_position(sections[section_name])
    
    persona = {'age_group': '70s'}
    fatigue_mgr = FatigueManager(persona)
    navigator = SectionNavigator(sections, fatigue_mgr)
    
    visible, context = navigator.get_elements_for_current_turn()
    
    # 프롬프트 생성
    prompt = build_prompt(
        visible_elements=visible,
        context_elements=context,
        current_tier='상',
        goal="로그인 버튼 찾기"
    )
    
    # 프롬프트 내용 확인
    assert "상 tier" in prompt
    assert "로그인 버튼 찾기" in prompt
    assert "found" in prompt
    assert len(prompt) > 0


def test_9_full_pipeline_integration(parsed_nodes):
    """9단계: 전체 파이프라인 통합 테스트"""
    # 1. Preattentive
    nodes, stats = apply_preattentive_priority(parsed_nodes, (1920, 1080))
    assert all('visual_priority' in n.properties for n in nodes)
    
    # 2. Section Grouping
    sections = group_by_html_tag(nodes)
    assert len(sections) > 0
    
    # 3. Tier Classification + Sorting
    for section_name in sections:
        sections[section_name] = classify_by_percentile(sections[section_name])
        sections[section_name] = sort_by_y_position(sections[section_name])
        
        # 모든 노드에 tier 할당 확인
        for node in sections[section_name]:
            assert 'tier' in node.properties
    
    # 4. Navigator + Fatigue
    persona = {'age_group': '20s'}
    fatigue_mgr = FatigueManager(persona)
    navigator = SectionNavigator(sections, fatigue_mgr)
    
    # 5. 순회 시뮬레이션
    iteration_count = 0
    max_iterations = 20
    
    while not navigator.is_complete() and iteration_count < max_iterations:
        # 현재 턴 요소 가져오기
        visible, context = navigator.get_elements_for_current_turn()
        state = navigator.get_current_state()
        
        # 프롬프트 생성
        prompt = build_prompt(
            visible_elements=visible,
            context_elements=context,
            current_tier=state['tier'],
            goal="테스트 목표"
        )
        
        assert len(prompt) > 0
        
        # 피로도 추가
        fatigue_mgr.add_fatigue(state['tier'], is_revisit=False)
        
        # 다음 tier 이동
        if not navigator.move_to_next_tier():
            # tier 끝나면 섹션 이동
            if not navigator.move_to_next_section():
                break
        
        iteration_count += 1
    
    # 최소 몇 번은 순회했는지 확인
    assert iteration_count > 0, "최소 1번은 순회해야 함"
    assert fatigue_mgr.global_fatigue > 0, "피로도가 누적되어야 함"
    
    print(f"\n✅ 전체 파이프라인 {iteration_count}회 순회 완료")
    print(f"✅ 최종 피로도: {fatigue_mgr.get_current_fatigue()}")