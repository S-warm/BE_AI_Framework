"""
NavigatorGuide: 길잡이 AI

목적:
- 페르소나 시뮬레이션 전 캐시 워밍업
- parsing_cache + 이미지 캐시 미리 적재
- 10회 실패 시 사용자에게 재입력 요청

사용:
    guide = NavigatorGuide(page, navigator_ai, db_path)
    result = guide.run(goal, url)
"""

from typing import Optional, Dict, List, Tuple
from playwright.sync_api import Page

from AI.cache.screenshot_cache import ScreenshotCache
from AI.navigation_AI.navigation_loop.navigation_loop import NavigationLoop
from normalizer.mcp.web_normalizer.web_normalizer_incremental.web_normalizer_incremental import WebNormalizerIncremental
from AI.layer_tier2.base_persona import BasePersona
from wcag.wcag_checker import WCAGChecker

from AI.Auditor_AI.utils.s3_uploader import S3Uploader
from AI.cache.parsing_cache import ParsingCache
from fix_code.DOM_extractors import DOMExtractor

class NavigatorGuide:

    MAX_ATTEMPTS = 3 # 최대 실행 횟수 / 너무 길면 줄이기

    def __init__(self, page: Page, navigator_ai, db_path: Optional[str] = None, uploader: Optional[S3Uploader] = None):
        self.page = page
        self.navigator_ai = navigator_ai
        self.db_path = db_path
        
        # 스크린샷 캐시 (워밍업 핵심)
        self.screenshot_cache = ScreenshotCache(db_path)
        
        # normalizer에 screenshot_cache 주입
        self.normalizer = WebNormalizerIncremental(screenshot_cache=self.screenshot_cache)

        # s3 업로드
        self.uploader = uploader

    def run(self, goal: str, url: str, success_condition: Optional[Dict] = None, session_dir: Optional[str] = None, date_prefix: Optional[str] = None) -> Dict:
        """
        캐시 워밍업 실행
        
        Args:
            goal: 사용자 목표
            url: 시작 URL
        
        Returns:
            {'status': 'success' | 'skipped', 'attempts': int}
        """
        self.persona = BasePersona('20s')
        self.success_condition = success_condition
        self.session_dir = session_dir
        
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            print(f"\n[GUIDE] 시도 {attempt}/{self.MAX_ATTEMPTS}")
            
            self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
            success, urls = self._run_once(goal, attempt)
            
            if success:
                print(f"[GUIDE] 성공 ({attempt}회 시도)")
                
                if date_prefix and urls:
                    post_page = self.page.context.new_page()
                    try:
                        # WCAG 검사
                        checker = WCAGChecker(page=post_page, uploader=self.uploader, navigator_ai=self.navigator_ai)
                        checker.run(urls=urls, date_prefix=date_prefix)
                        
                        # DOM 추출 (HTML 백업)
                        dom_extractor = DOMExtractor(page=post_page, uploader=self.uploader)
                        dom_extractor.run(urls=urls, date_prefix=date_prefix)
                        
                        # 스크린샷 캐시 업로드
                        self.screenshot_cache.upload_to_s3(urls=urls, uploader=self.uploader, date_prefix=date_prefix)
                    finally:
                        post_page.close()
                
                return {'status': 'success', 'attempts': attempt}
        
        # 10회 전부 실패
        new_goal = self._request_new_goal(goal)
        return {'status': 'skipped', 'attempts': self.MAX_ATTEMPTS, 'new_goal': new_goal}

    def _run_once(self, goal: str, attempt: int) -> Tuple[bool, List[str]]:
        """
        NavigationLoop 1회 실행
        
        Returns:
            True: success
            False: failure or timeout
        """
        ParsingCache(self.db_path).clear_all()
        self.normalizer.last_url = None
        log_dir = f"{self.session_dir}/guide/attempt_{attempt}" if self.session_dir else None
        
        # MockNavigatorAI에 경로 업데이트
        if hasattr(self.navigator_ai, 'set_log_dir') and log_dir:
            self.navigator_ai.set_log_dir(log_dir)
        
        loop = NavigationLoop(
            page=self.page,
            normalizer=self.normalizer,
            navigator_ai=self.navigator_ai,
            db_path=self.db_path,
            log_dir=log_dir,
            uploader=self.uploader,
            session_dir=self.session_dir,
        )
        loop.max_steps = 35 # 최대 스텝 수
        
        result = loop.run(goal=goal, persona=self.persona, success_condition=self.success_condition, warmup=True)
        
        if result['status'] == 'success':
            urls = list(dict.fromkeys(p.url for p in loop.logger._pages))  # 순서 유지 중복 제거
            return True, urls
        return False, []

    def _request_new_goal(self, goal: str) -> str:
        """
        10회 실패 시 사용자에게 재입력 요청
        
        Args:
            goal: 실패한 원래 목표
        
        Returns:
            사용자가 새로 입력한 목표
        """
        print(f"\n{'='*50}")
        print(f"[GUIDE FAIL] 10회 시도 모두 실패")
        print(f"실패한 목표: '{goal}'")
        print(f"목표가 너무 모호하거나 달성 불가능할 수 있습니다.")
        print(f"{'='*50}")
        
        print(f"[GUIDE FAIL] {self.MAX_ATTEMPTS}회 시도 모두 실패")
        return goal
    
    
"""
guide.run(goal, url)
    │
    ├── page.goto(url)  # 최초 1회
    │
    ├── 시도 1~10회
    │     └── _run_once(goal)
    │           ├── NavigationLoop 새로 생성 (매번 초기화)
    │           ├── loop.run() 실행
    │           └── 성공 → True, 실패 → False
    │
    ├── 성공 → {'status': 'success', 'attempts': N} 반환
    │
    └── 10회 전부 실패
          └── _request_new_goal()
                ├── 실패 메시지 출력
                ├── 사용자에게 새 목표 input() 요청
                └── {'status': 'skipped', 'attempts': 10, 'new_goal': ...} 반환
"""
