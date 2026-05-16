"""
NavigationLoop - 메인 탐색 오케스트레이션
"""
from typing import Dict, List, Optional
from playwright.sync_api import Page
from urllib.parse import unquote
from pathlib import Path

import boto3
import json
import os

from normalizer.standard_ui_node import StandardUINode
from normalizer.mcp.web_normalizer.web_normalizer_incremental.web_normalizer_incremental import WebNormalizerIncremental

from AI.cache.parsing_cache import ParsingCache
from AI.cache.incremental_cache import IncrementalCache
from AI.cache.cache_stats import get_cache_report
from AI.layer_tier1.scanning_pattern.utils.prompt_builder import build_incremental_prompt

from AI.layer_tier1.fatigue.fatigue_manager import FatigueManager
from AI.layer_tier1.memory.context_memory.context_memory import ContextMemory
from AI.layer_tier1.scanning_pattern.section.section_grouper import group_by_html_tag
from AI.layer_tier1.scanning_pattern.element.element_classify import classify_by_percentile
from AI.layer_tier1.scanning_pattern.utils.sorter import sort_by_y_position
from AI.layer_tier1.scanning_pattern.page_scanning_loop import SectionNavigator
from AI.layer_tier1.scanning_pattern.incremental_scanner import IncrementalScanner
from AI.layer_tier1.scanning_pattern.utils.prompt_builder import build_prompt

from AI.navigation_AI.AI_action.action_executor import ActionExecutor
from AI.navigation_AI.AI_memory.navigation_memory import NavigationMemory
from AI.navigation_AI.AI_memory.page_history import PageHistory
from AI.navigation_AI.AI_memory.section_memory import SectionMemory
from AI.navigation_AI.navigation_loop.task_parse import parse_goal
from AI.layer_tier1.pre_attentive import pre_attentive

from AI.layer_tier2.persona.age.age_config import get_age_config
from AI.layer_tier2.base_persona import BasePersona

from AI.logger.navigation_AI_log import NavigationAILog

from AI.Auditor_AI.utils.s3_uploader import S3Uploader

class NavigationLoop:
    """메인 탐색 루프 오케스트레이터"""

    def __init__(
        self,
        page: Page,
        normalizer: WebNormalizerIncremental,
        navigator_ai,  # OpenAI client
        db_path: Optional[str] = None,
        log_dir: Optional[str] = None,
        uploader: Optional[S3Uploader] = None,
        session_dir: Optional[str] = None,
    ):
        """
        Args:
            page: Playwright Page 객체
            normalizer: WebNormalizerIncremental 인스턴스
            navigator_ai: OpenAI AI 클라이언트
            db_path: SQLite 캐시 DB 경로 (None이면 기본 경로)
        """
        self.page = page
        self.normalizer = normalizer
        self.navigator_ai = navigator_ai

        # 캐싱 시스템 (get/save 내부에서 hit/miss 통계 자동 처리)
        self.parsing_cache = ParsingCache(db_path)
        self.incremental_cache = IncrementalCache(db_path)

        # 액션 실행기
        self.executor = ActionExecutor(page)

        # 메모리 시스템
        self.context_memory = ContextMemory()
        self.page_history = PageHistory()
        self.section_memory = SectionMemory()

        # frozen_state (증분 프롬프트용)
        self.last_section_name: Optional[str] = None
        self.last_tier: Optional[str] = None
        self.last_visible: List[StandardUINode] = []
        self.last_context: List[StandardUINode] = []

        # 상태
        self.current_url: Optional[str] = None
        self.step_count = 0
        self.max_steps = 40

        # run() 시점에 설정 (persona 필요)
        self.fatigue_manager: Optional[FatigueManager] = None
        self.navigation_memory: Optional[NavigationMemory] = None
        self.incremental_scanner: Optional[IncrementalScanner] = None
        self.persona: Optional[BasePersona] = None
        
        # Task 파싱 결과 저장용
        self.parsed_task: Optional[Dict] = None
        
        # success 검증
        self.success_condition: Optional[Dict] = None
        self.last_verify_fail_reason: Optional[str] = None
        self.verify_fail_count: int = 0
        self.max_verify_fail = 3
        
        # 티어 순회시 최적화 요약용
        self.last_explored_tiers: List[str] = []
        
        # 로깅용
        self.logger: Optional[NavigationAILog] = None
        self.log_dir = log_dir
        self.uploader = uploader
        
        # 결과 ai
        self.session_dir = session_dir

    def run(self, goal: str, persona: BasePersona, success_condition: Optional[Dict] = None, warmup: bool = False) -> Dict:
        """
        메인 탐색 루프

        Args:
            goal: 사용자 목표 ("회원가입하고 로그인")
            persona: {'age_group': '50s', 'digital_literacy': 'medium'}

        Returns:
            {
                'status': 'success' | 'failure' | 'timeout',
                'total_steps': int,
                'actions': List[Dict],
                'cache_stats': Dict
            }
        """
        # ━━━ 초기화 ━━━
        self.current_url = self.page.url
        self.navigation_memory = NavigationMemory(goal)
        self.success_condition = success_condition
        self.last_verify_fail_reason = None
        self.verify_fail_count = 0
        age = int(persona.age_group.replace('s', ''))
        self.logger = NavigationAILog(persona_age=age)
        self.logger.start_page(self.current_url)
        
        # 목표 파싱 (최초 1회)
        self.parsed_task = parse_goal(goal, self.navigator_ai)
        print(f"\n📋 파싱된 목표:")
        print(f"  - final_target: {self.parsed_task['final_target']}")
        print(f"  - success_condition: {self.parsed_task['success_condition']}\n")

        # BasePersona 생성
        self.persona = persona
        
        # persona 의존 컴포넌트는 run() 시점에 생성
        self.fatigue_manager = FatigueManager(self.persona.to_dict())
        self.incremental_scanner = IncrementalScanner(
            prompt_builder=build_incremental_prompt,
            executor=self.executor,
            navigator_ai=self.navigator_ai,
            fatigue_manager=self.fatigue_manager
        )

        # Persona별 working memory limit
        self.working_memory_limit = self.persona.age_config['working_memory']['memory_slots']

        # ━━━ 메인 루프 ━━━
        section_navigator = None  # URL 변경 시에만 재생성

        while self.step_count < self.max_steps:
            print(f"[LOOP] step={self.step_count}, url={self.page.url}")
            
            # ★ 광고/모달 자동 닫기
            self._dismiss_overlays()
            
            # URL 도달 체크 (매 턴 시작 시) -> 나중에 액션도 추가
            if self.success_condition and self._verify_success() is None:
                print(f"[AUTO_SUCCESS] URL 도달: {self.page.url}")
                return self._finalize('declare_success')

            # [1] 증분 우선 처리
            if self.context_memory.has_incremental():
                result = self._handle_incremental(goal, persona)

                # 증분 처리 중 URL 변경 시 클리어
                if self._url_changed():
                    self.context_memory.clear_incremental()
                    self.current_url = self.page.url
                    section_navigator = None  # URL 바뀌면 navigator 재생성
                    continue

                if result['complete']:
                    return self._finalize(result['action'])

                if result['closed']:
                    moved = section_navigator.move_to_next_section()
                    print(f"[CLOSED] move_to_next_section={moved}, current={section_navigator.current_section_idx}")
                    continue

            # [2] 페이지 파싱 + SectionNavigator 생성 (URL 변경 시에만)
            if self._url_changed() or section_navigator is None:
                print(f"[NAV_REBUILD] url_changed={self._url_changed()}, nav_is_none={section_navigator is None}")
                if self._url_changed():
                    self.context_memory.clear_incremental()
                    self._update_page_history()
                    self.section_memory.set_current_url(self.page.url)
                    self.current_url = self.page.url
                    self.logger.end_page()
                    self.logger.start_page(self.page.url)

                nodes = self._parse_with_cache(self.current_url)
                viewport_h = self.page.viewport_size.get('height', 1080) if self.page.viewport_size else 1080
                sections = self._process_tier1(nodes, viewport_h, None if warmup else self.persona)
                section_navigator = SectionNavigator(sections, self.fatigue_manager)

            # [3] 섹션 탐색 완료 시 스텝 증가 후 continue
            if section_navigator.is_complete():
                self.step_count += 1
                break

            # [4] 현재 턴 요소 가져오기
            visible, context = section_navigator.get_elements_for_current_turn()

            # frozen_state 업데이트 (증분 대비)
            self.last_visible = visible
            self.last_context = context
            self.last_section_name = section_navigator.section_order[section_navigator.current_section_idx]
            self.last_tier = section_navigator.tier_order[section_navigator.current_tier_idx]
            self.last_explored_tiers = section_navigator.tier_order[:section_navigator.current_tier_idx]

            explored_tiers = section_navigator.tier_order[:section_navigator.current_tier_idx]

            # [5] 프롬프트 생성
            prompt = self._build_full_prompt(
                visible=visible,
                context=context,
                tier=self.last_tier,
                goal=goal,
                explored_tiers=explored_tiers
            )

            # [6] AI 호출
            response = self.navigator_ai.call(prompt)

            # [7] 액션 실행
            result = self._execute_action(response, visible, self.last_tier, context=context)

            # [8] 종료 조건
            if result['action'] == 'declare_success':
                return self._finalize(result['action'])

            if result['action'] == 'declare_failure':
                self.step_count += 1
                print(f"[DECLARE_FAILURE] verify_fail_count={self.verify_fail_count}")
                self.verify_fail_count = 0
                if not section_navigator.move_to_next_tier():
                    moved = section_navigator.move_to_next_section()
                    print(f"[SECTION_MOVE] moved={moved}, next={section_navigator.section_order[section_navigator.current_section_idx] if moved else 'END'}")
                    if not moved:
                        return self._finalize(result['action'])
                continue

            if result['action'] == 'verify_failed':
                if not section_navigator.move_to_next_tier():
                    if not section_navigator.move_to_next_section():
                        # 모든 섹션 완료 → 다음 외부 루프에서 is_complete() 처리
                        pass
                continue

            element_id = response.get('element_id', 0)
            if element_id is None:
                element_id = 0
            target_node = visible[element_id] if element_id < len(visible) else None

            # [9] 증분 감지: 클릭 후 URL 유지
            if result['action'] == 'click' and not self._url_changed():
                target_node = visible[element_id] if element_id < len(visible) else None
                clicked_xpath = target_node.metadata.get('xpath') if target_node else None
                
                # 새 탭 처리 (executor에서 이미 감지)
                new_page = result.get('new_page')
                print(f"[NAV_SWAP] result.new_page = {new_page}")
                if new_page:
                    self.page = new_page
                    self.executor.page = new_page
                    self.normalizer.last_url = None
                    self.current_url = new_page.url
                    self.logger.end_page()
                    self.logger.start_page(new_page.url)
                    print(f"[NEW_TAB] 새 탭으로 swap: {self.page.url}")
                    section_navigator = None
                    continue
                
                # URL 변경 대기
                try:
                    self.page.wait_for_url(lambda url: url != self.current_url, timeout=3000)
                except:
                    pass
                
                if self._url_changed():
                    print(f"[URL_CHANGED] {self.current_url} → {self.page.url}")
                    section_navigator = None
                    continue
                
                delta = self._parse_incremental_with_cache(result, target_node, clicked_xpath)
                
                # WEAK_DELTA: 증분이 빈약하면 normalizer.last_url이 None으로 세팅됨
                # → section_navigator를 None으로 초기화해서 다음 루프에서 전체 파싱 실행
                
                if not delta and self.normalizer.last_url is None:
                    print("[WEAK_DELTA_FALLBACK] 전체 파싱으로 전환")
                    self.context_memory.clear_incremental()
                    self.incremental_cache.clear_all() # 캐시도 클리어
                    if self._url_changed():
                        # URL 변경 → 메인 루프에 위임
                        section_navigator = None
                        continue
                    # 같은 URL일 때만 기존 로직
                    prev_section_idx = section_navigator.current_section_idx if section_navigator else 0
                    self.parsing_cache.delete(self.page.url)
                    nodes = self._parse_with_cache(self.page.url)
                    viewport_h = self.page.viewport_size.get('height', 1080) if self.page.viewport_size else 1080
                    new_sections = self._process_tier1(nodes, viewport_h, self.persona)
                    section_navigator = SectionNavigator(new_sections, self.fatigue_manager)
                    section_navigator.current_section_idx = prev_section_idx  # 0 아니라 현재 섹션 유지
                    section_navigator.current_tier_idx = 0
                    print(f"[WEAK_DELTA_FALLBACK] section_idx={section_navigator.current_section_idx}부터 재개")
                    continue
                
                # 정상 증분: ContextMemory에 추가 후 증분 서브루프로 진입
                if delta:
                    trigger = self._make_trigger(result, target_node)
                    self.context_memory.add_incremental(delta, trigger)
                    continue

            # [10] 페이지 전환 감지
            if self._url_changed():
                print(f"[URL_CHANGED] {self.current_url} → {self.page.url}")
                section_navigator = None  # 다음 루프에서 재생성
                continue

            # [11] 다음 tier/섹션으로 이동
            if result['action'] == 'fill':
                continue  # fill 후엔 같은 tier에서 다시 AI 호출

            if not section_navigator.move_to_next_tier():
                if not section_navigator.move_to_next_section():
                    self.step_count += 1  # 모든 섹션 완료

        # 타임아웃
        return self._finalize('timeout')

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # success 검증
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def _verify_success(self) -> Optional[str]:
        
        if not self.success_condition:
            return None  # 조건 없으면 통과
        
        current_url = self.page.url
        cond = self.success_condition
        
        # path 체크
        if cond.get('path') and cond['path'] not in current_url:
            return f"아직 목표 페이지 아님 (현재: {current_url})"
        
        # 파라미터 체크
        import urllib.parse
        parsed = urllib.parse.urlparse(current_url)
        params = urllib.parse.parse_qs(parsed.query)
            
        for key, value in (cond.get('required_params') or {}).items():
            actual = params.get(key, [None])[0]
            if unquote(actual or '') != unquote(value):
                return f"아직 목표 페이지가 아닙니다. 계속 탐색하세요.."
        
        return None  # 전부 통과

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 캐싱
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _url_changed(self) -> bool:
        """URL 변경 감지 (fragment 무시)"""
        from urllib.parse import urlparse
        
        def normalize(url: str) -> str:
            p = urlparse(url)
            return f"{p.scheme}://{p.netloc}{p.path}?{p.query}"
        
        return normalize(self.page.url) != normalize(self.current_url)
    
    def _dismiss_overlays(self):
        """광고, 모달, 쿠키 배너 등 자동 닫기. 실패해도 조용히 넘김."""
        try:
            # Google AdSense vignette ad
            self.page.evaluate("""
                () => {
                    // google_vignette fragment 제거
                    if (window.location.hash === '#google_vignette') {
                        history.replaceState(null, '', window.location.pathname + window.location.search);
                    }
                    // 광고 iframe 제거
                    document.querySelectorAll('iframe[id*="google_ads"], iframe[id*="aswift"]').forEach(el => el.remove());
                    // 광고 컨테이너 제거
                    document.querySelectorAll('[id*="google_vignette"], .adsbygoogle').forEach(el => el.remove());
                    // 일반 모달 close 버튼 시도
                    const closeSelectors = [
                        '[aria-label="Close ad" i]',
                        '[aria-label="Close" i]',
                        'button.dismiss-button',
                        '.modal-close',
                        '#dismiss-button',
                    ];
                    for (const sel of closeSelectors) {
                        const btn = document.querySelector(sel);
                        if (btn) btn.click();
                    }
                }
            """)
        except Exception as e:
            print(f"[DISMISS_OVERLAY] skip: {e}")

    def _parse_with_cache(self, url: str) -> List[StandardUINode]:
        cached = self.parsing_cache.get(url)
        if cached:
            matches = [n for n in cached if 'Cloud' in (n.content or '') or 'Fleece' in (n.content or '')]
            print(f"[TARGET_SEARCH] 캐시히트 - 'Cloud/Fleece' {len(matches)}개: {[(n.type, n.content[:30]) for n in matches]}")
            return cached

        nodes = self.normalizer.normalize(self.page)
        self.parsing_cache.save(url, nodes)
        
        matches = [n for n in nodes if 'Cloud' in (n.content or '') or 'Fleece' in (n.content or '')]
        print(f"[TARGET_SEARCH] 신규파싱 - 'Cloud/Fleece' {len(matches)}개: {[(n.type, n.content[:30]) for n in matches]}")
        
        return nodes
    
    def _is_weak_delta(self, delta: List[StandardUINode]) -> bool:
        if not delta or len(delta) <= 3:
            print(f"[WEAK_DELTA] True - nodes={len(delta) if delta else 0}")
            return True
        
        viewport_h = self.page.viewport_size.get('height', 1080) if self.page.viewport_size else 1080
        visible = [n for n in delta if 0 <= n.properties.get('y', -1) <= viewport_h]
        if len(visible) == 0:
            print(f"[WEAK_DELTA] True - no visible nodes")
            return True
        
        # 리스트 구조 감지: text 없고 container 3개 이상
        has_text = any(n.type == 'text' for n in delta)
        container_count = sum(1 for n in delta if n.type == 'container')
        text_count = sum(1 for n in delta if n.type == 'text')
        button_count = sum(1 for n in delta if n.type == 'button')
        if container_count >= 3 and text_count <= 1 and button_count <= 2:
            print(f"[WEAK_DELTA] True - list structure detected (containers={container_count}, no text)")
            return True
        
        print(f"[WEAK_DELTA] False - nodes={len(delta)}, visible={len(visible)}")
        return False

    def _parse_incremental_with_cache(self, result: Dict, node: Optional[StandardUINode] = None, clicked_xpath: str = None) -> List[StandardUINode]:
        print(f"clicked_xpath: {clicked_xpath}")
        
        debug = self.page.evaluate('''
            (clickedXpath) => {
                const getEl = (xpath) => document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                const clickedEl = getEl(clickedXpath);
                const slickEl = document.getElementById('slick-slide00');
                if (!clickedEl || !slickEl) return 'element not found';
                return `contains: ${clickedEl.contains(slickEl)}, parent contains: ${clickedEl.parentElement?.contains(slickEl)}`;
            }
        ''', clicked_xpath)
        #print(f"필터링 결과: {debug}")

        trigger = self._make_trigger(result, node)  # 수정
        cached = self.incremental_cache.get(self.page.url, trigger)
        if cached:
            return cached

        self.page.wait_for_timeout(1000) # 렌더링 전에 파싱되는거 방식 시간 텀 줌
        delta = self.normalizer.normalize(self.page, clicked_xpath)
        print(f"[DELTA_TYPES] {[(n.type, n.content[:20] if n.content else '') for n in delta]}")
        
        if self._is_weak_delta(delta):
            print("[WEAK_DELTA] 증분 빈약 → 전체 파싱 fallback")
            self.normalizer.last_url = None
            # self.parsing_cache.delete(self.page.url)
            return []
        
        if delta:
            self.incremental_cache.save(self.page.url, trigger, delta)
        return delta

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Tier 1 처리
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _process_tier1(
        self,
        nodes: List[StandardUINode],
        viewport_height: int = 1080,
        persona: Optional[BasePersona] = None
    ) -> Dict[str, List[StandardUINode]]:
        """
        Tier 1 처리 (그룹핑 + 분류 + 정렬)

        Returns:
            {
                'header': [노드들],  # tier 분류 + Y정렬 완료
                'main': [...],
                'footer': [...]
            }
        """
        
        # visual_priority 계산
        nodes, _ = pre_attentive.apply_preattentive_priority(nodes)
        
        """
        # 임시 디버그
        for node in nodes:
            if 'GNB' in node.id:
                print(f"[SECTION DEBUG] {node.id} | xpath:{node.metadata.get('xpath')} | parent_tag:{node.metadata.get('parent_tag')} | ancestors:{node.metadata.get('ancestor_tags')}")
        """
        
        # 디버그: 목표 논문 추적
        target_kw = "프롬프트 기반 감성"
        matches = [n for n in nodes if target_kw in (n.content or "")]
        print(f"[TRACK] after pre_attentive: {len(matches)}개 매칭")
        for m in matches:
            print(f"  - type={m.type}, y={m.properties.get('y')}, content={m.content[:50]}")
        
        sections_raw = group_by_html_tag(nodes, viewport_height)
        
        # 디버그: 섹션 분리 후
        for section_name, raw_nodes in sections_raw.items():
            matches = [n for n in raw_nodes if target_kw in (n.content or "")]
            print(f"[TRACK] section={section_name}: {len(matches)}개 매칭")

        sections_processed = {}
        for section_name, raw_nodes in sections_raw.items():
            if section_name == 'nav':
                for n in raw_nodes:
                    print(f"[NAV_RAW] {n.type} '{n.content}' y={n.properties.get('y')} h={n.properties.get('height')}")
                    
            classified = classify_by_percentile(raw_nodes)
            
            if section_name == 'nav':
                for n in classified:
                    print(f"[NAV_CLASSIFIED] {n.type} '{n.content}' tier={n.properties.get('tier')}")
            
            # 디버그: tier 분류 후
            matches = [n for n in classified if target_kw in (n.content or "")]
            for m in matches:
                print(f"[TRACK] {section_name}/{m.properties.get('tier')}: {m.content[:50]}")
            
            sorted_nodes = sort_by_y_position(classified)
            if persona:
                filtered = persona.filter_nodes(sorted_nodes)
                print(f"[VISION_FILTER] {section_name}: {len(sorted_nodes)} → {len(filtered)} ({persona.age_group})")
                sections_processed[section_name] = filtered
                
                # 디버그: persona 필터 후
                matches = [n for n in filtered if target_kw in (n.content or "")]
                print(f"[TRACK] {section_name} after persona: {len(matches)}개 매칭")
                
                print(f"[VISION_FILTER] {section_name}: {len(sorted_nodes)} → {len(filtered)} ({persona.age_group})")
                sections_processed[section_name] = filtered
                
            else:
                sections_processed[section_name] = sorted_nodes
        
        print(f"[SECTIONS] {list(sections_processed.keys())}")
        for k, v in sections_processed.items():
            print(f"  {k}: {len(v)}개")
            
        for k, v in sections_processed.items():
            for i, node in enumerate(v):
                if node.properties.get('tier') == '상':
                    print(f"  [{k}][상][{i}] {node.type} '{node.content[:30] if node.content else '[no text]'}'")

        for k, v in sections_processed.items():
            for n in v:
                if 'Cloud' in (n.content or '') or 'Fleece' in (n.content or ''):
                    print(f"[TARGET_TIER] {k} tier={n.properties.get('tier')} type={n.type} content={n.content[:40]}")

        return sections_processed

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 증분 처리
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _handle_incremental(self, goal: str, persona: BasePersona) -> Dict:
        """
        증분 서브루프 위임

        Returns:
            {
                'complete': bool,
                'closed': bool,
                'action': str
            }
        """
        frozen_state = {
            'section_name': self.last_section_name,
            'tier': self.last_tier,
            'visible_elements': self.last_visible,
            'context_elements': self.last_context,
            'explored_tiers': self.last_explored_tiers
        }

        return self.incremental_scanner.scan(
            context_memory=self.context_memory,
            navigation_memory=self.navigation_memory,
            normalizer=self.normalizer,
            page=self.page,
            persona=persona,
            goal=goal,
            current_url=self.page.url,
            frozen_section_state=frozen_state,
            parsed_task=self.parsed_task
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 액션 실행
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _execute_action(
        self,
        response: Dict,
        visible: List[StandardUINode],
        tier: str,
        context: List[StandardUINode] = None
    ) -> Dict:
        element_id = response.get('element_id')
        action_type = response.get('action_type')
        reasoning = response.get('reasoning', '')
        """
        액션 실행 + 기록 + 피로도 증가

        Args:
            response: AI 응답 {'element_id': int, 'action_type': str, 'reasoning': str}
            visible: 현재 visible 요소들
            tier: 현재 탐색 tier ('상'/'중'/'하')

        Returns:
            {'success': bool, 'action': str, 'error': str, 'target_node_id': str}
        """
        element_id = response.get('element_id', 0)
        action_type = response.get('action_type', 'click')
        reasoning = response.get('reasoning', '')

        # None 체크 추가
        if element_id is None or action_type is None:
            return {
                'success': False,
                'action': 'error',
                'error': f'Invalid AI response: element_id={element_id}, action_type={action_type}',
                'target_node_id': None
            }
        
        # 인덱스 검증
        if element_id >= len(visible):
            return {
                'success': False,
                'action': 'error',
                'error': f'Invalid element_id {element_id}',
                'target_node_id': None
            }

        # ★ 같은 노드 반복 click 차단
        if action_type == 'click':
            target_node = visible[element_id]
            recent_actions = self.navigation_memory.get_recent(3)
            same_node_clicks = sum(
                1 for a in recent_actions
                if a.get('action') == 'click' and a.get('element_id') == target_node.id
            )
            if same_node_clicks >= 2:
                print(f"[REPEAT_BLOCK] {target_node.id} click {same_node_clicks}회 반복 → declare_failure 강제")
                return {
                    'success': False,
                    'action': 'declare_failure',
                    'error': f'Same element clicked {same_node_clicks} times without progress',
                    'target_node_id': target_node.id
                }

        target_node = visible[element_id]
        node_id = target_node.id

        # action_type → tool_name 매핑
        tool_map = {
            'click': 'click_element',
            'fill': 'fill_input',
            'upload': 'upload_file',
            'back': 'go_back',
            'declare_success': 'declare_success',
            'declare_failure': 'declare_failure'
        }
        tool_name = tool_map.get(action_type, 'click_element')
        
        # declare_success 가로채기
        if tool_name == 'declare_success':
            reason = self._verify_success()
            if reason:
                print(f"[VERIFY] fail #{self.verify_fail_count + 1}: {reason}")
                self.last_verify_fail_reason = reason
                self.verify_fail_count += 1
                if self.verify_fail_count >= self.max_verify_fail:
                    return self.executor.execute_tool('declare_failure', {'reasoning': f'success 검증 {self.max_verify_fail}회 실패: {reason}'}, {})  # node_map → {}
                return {
                    'success': False,
                    'action': 'verify_failed',
                    'error': reason,
                    'target_node_id': None
                }
            # 검증 통과
            self.verify_fail_count = 0
            print(f"[VERIFY_PASS] 검증 통과, tool_name={tool_name}")  # 추가

        # args 구성
        args = {'reasoning': reasoning}
        if tool_name in ['click_element', 'fill_input', 'upload_file']:
            args['node_id'] = node_id
        if tool_name == 'fill_input':
            args['text'] = response.get('text', '')

        # 실행
        node_map = {node.id: node for node in visible}
        result = self.executor.execute_tool(
            tool_name=tool_name,
            args=args,
            node_map=node_map
        )

        # 기록
        self.navigation_memory.add_action(
            action=result['action'],
            element_id=node_id,
            element_text=target_node.content or reasoning,
            result='success' if result['success'] else 'failure',
            error=result.get('error') if not result['success'] else None
        )
        
        # 로깅
        step_file = response.get('_step_file')
        
        if action_type == 'declare_failure':
            tier_elements = {}
            for tier_name in ['상', '중', '하']:
                tier_nodes = [n for n in (context or []) if n.properties.get('tier') == tier_name]
                tier_elements[f'{tier_name}_tier'] = [
                    node.content or '[no text]' for node in tier_nodes
                ]
            
            self.logger.log_action(
                action_type='declare_failure',
                target_html=None,
                coord_x=None,
                coord_y=None,
                scroll_y=int(self.page.evaluate('window.scrollY')),
                step=self.step_count,
                step_file=step_file,
                is_failed=True,
                failure_context=tier_elements
            )

        elif action_type != 'declare_success':
            self.logger.log_action(
                action_type=action_type,
                target_html=f"<{target_node.metadata.get('html_tag', '')} id='{target_node.metadata.get('html_id', '')}' class='{target_node.metadata.get('html_class', '')}'>" if target_node else None,
                coord_x=int(target_node.properties.get('x', 0)) if target_node else None,
                coord_y=int(target_node.properties.get('y', 0)) if target_node else None,
                scroll_y=int(self.page.evaluate('window.scrollY')),
                step=self.step_count,
                step_file=step_file,
            )

        # 피로도 증가
        self.fatigue_manager.add_fatigue(tier)
        self.step_count += 1

        return result

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 프롬프트
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _build_full_prompt(
        self,
        visible: List[StandardUINode],
        context: List[StandardUINode],
        tier: str,
        goal: str,
        explored_tiers: List[str] = None
    ) -> str:
        """메모리 통합된 프롬프트 생성"""

        # 1. 기본 프롬프트 (success_condition 추가)
        base = build_prompt(
            visible, 
            context, 
            tier, 
            goal,
            explored_tiers=explored_tiers,
            success_condition=self.parsed_task['success_condition'],
            verify_fail_reason=self.last_verify_fail_reason
        )
        
        self.last_verify_fail_reason = None # 여기서 클리어

        # 2. 메모리 컨텍스트
        recent_actions = self.navigation_memory.get_recent(self.working_memory_limit)
        page_summary = self.page_history.get_history_summary(self.working_memory_limit)
        section_summary = self.section_memory.get_previous_summaries()

        memory_context = f"""
<최근_행동>
{self._format_actions(recent_actions)}
</최근_행동>

<페이지_히스토리>
{page_summary}
</페이지_히스토리>

<이미_확인한_섹션>
{section_summary}
</이미_확인한_섹션>
""" 

        return base + "\n\n" + memory_context

    def _format_actions(self, actions: List[Dict]) -> str:
        """행동 리스트 포맷팅"""
        lines = []
        for action in actions:
            lines.append(
                f"{action['step']}. {action['action']} "
                f"{action['element_id']} '{action['element_text']}' "
                f"→ {action['result']}"
                + (f" (실패이유: {action['error']})" if action.get('error') else "")
            )
        return "\n".join(lines)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 유틸리티
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _make_trigger(self, result: Dict, node: Optional[StandardUINode] = None) -> str:
        action = result.get('action', 'click')
        
        if node:
            meta = node.metadata or {}
            html_id = meta.get('html_id', '')
            if html_id:
                stable_id = html_id
            else:
                tag = meta.get('html_tag', '')
                content = node.content[:20]
                stable_id = f"{tag}:{content}"
        else:
            stable_id = result.get('target_node_id', 'unknown')
        
        return f"{action}|{stable_id}"

    def _update_page_history(self):
        """페이지 히스토리 업데이트"""
        summary = self.section_memory.get_previous_summaries()
        recent = self.navigation_memory.get_recent(1)
        action_text = recent[0]['action'] if recent else "직접 접속"
        self.page_history.add_page(self.page.url, summary, action_text)

    def _finalize(self, status: str) -> Dict:
        """
        결과 반환

        Args:
            status: 'declare_success' | 'declare_failure' | 'timeout'
        """
        # 현재 페이지 히스토리에 추가 (마지막 페이지 누락 방지)
        self.page_history.add_page(self.page.url, "", "finalize")
        
        status_map = {
            'declare_success': 'success',
            'declare_failure': 'failure',
            'timeout': 'timeout'
        }
        final_status = status_map.get(status, status)
        
        self.logger.finalize(is_success=(final_status == 'success'))
        saved_path = self.logger.save(self.log_dir or "logs/")
        print(f"[DEBUG] saved_path: {saved_path}")

        if self.uploader:
            s3_prefix = f"raw/{self.session_dir or 'logs'}"
            
            print(f"[s3_prefix]: {s3_prefix}")
            print(f"[logs_dir]: {Path(self.session_dir)}") 
            
            uploaded_prefix = self.uploader.upload_session_logs(
                s3_prefix=s3_prefix,
                logs_dir=Path(self.session_dir)
            )

        return {
            'status': final_status,
            'total_steps': self.step_count,
            'actions': self.navigation_memory.get_all_actions(),
            'cache_stats': get_cache_report(),
            'visited_urls': self.page_history.get_all_urls()
        }
        
    def _trigger_step_functions(self, prefix: str):
        client = boto3.client('stepfunctions', region_name='ap-northeast-2')
        client.start_execution(
            stateMachineArn=os.getenv('STEP_FUNCTIONS_ARN'),
            input=json.dumps({"prefix": prefix})
        )