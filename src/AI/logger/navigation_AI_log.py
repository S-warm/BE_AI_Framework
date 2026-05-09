"""
NavigationAILog - Navigator 행동 로그 수집

찍는 것:
- 세션 메타데이터 (session_id, persona, 성공여부, 소요시간)
- 페이지별 체류시간 + 액션 목록
- 액션별 target_html, 좌표, timestamp

안 찍는 것 (Auditor 몫):
- issue_type, category, severity 등 해석/분류
"""

import json
import uuid
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict
from pathlib import Path


class ActionLog:
    def __init__(
        self,
        action_type: str,
        target_html: Optional[str],
        coord_x: Optional[int],
        coord_y: Optional[int],
        scroll_y: Optional[int],
        step: int = 0,
        is_failed: bool = False,  # 이 액션이 실패였는지
        hesitation_ms: Optional[int] = None, # AI 응답 → 실제 액션 사이 시간
        failure_context: Optional[Dict] = None,
        step_file: Optional[str] = None,
    ):
        self.action_type = action_type
        self.target_html = target_html
        self.coord_x = coord_x
        self.coord_y = coord_y
        self.scroll_y = scroll_y
        self.step = step
        self.is_failed = is_failed
        self.hesitation_ms = hesitation_ms
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.failure_context = failure_context 
        self.step_file = step_file

    def to_dict(self) -> Dict:
        return {
            "step": self.step,
            "action_type": self.action_type,
            "target_html": self.target_html,
            "coord_x": self.coord_x,
            "coord_y": self.coord_y,
            "scroll_y": self.scroll_y,
            "is_failed": self.is_failed,
            "hesitation_ms": self.hesitation_ms,
            "timestamp": self.timestamp,
            "failure_context": self.failure_context,
            "step_file": self.step_file,
        }


class PageLog:
    def __init__(self, step_order: int, url: str):
        self.step_order = step_order
        self.url = url
        self._start_time = time.time()
        self.page_duration_ms: Optional[int] = None
        self.status: str = "success"
        self.actions: List[ActionLog] = []

    def add_action(self, action: ActionLog):
        self.actions.append(action)

    def close(self, status: str = "success"):
        """페이지 이탈 시 호출 → 체류시간 확정"""
        self.page_duration_ms = int((time.time() - self._start_time) * 1000)
        self.status = status

    def to_dict(self) -> Dict:
        return {
            "step_order": self.step_order,
            "url": self.url,
            "page_duration_ms": self.page_duration_ms,
            "status": self.status,
            "actions": [a.to_dict() for a in self.actions],
        }


class NavigationAILog:
    """
    NavigationLoop에서 호출하는 로그 수집기

    사용:
        logger = NavigationAILog(persona_age=70)
        logger.start_page(url)
        logger.log_action(action_type, target_html, coord_x, coord_y, scroll_y)
        logger.end_page()
        logger.finalize(is_success=True)
        logger.save("/path/to/logs/")
    """

    def __init__(self, persona_age: int):
        self.session_id = f"AI-sess_{uuid.uuid4().hex[:8]}"
        self.persona_age = persona_age
        self.is_success: Optional[bool] = None
        self.total_duration_ms: Optional[int] = None

        self._start_time = time.time()
        self._step_counter = 0
        self._current_page: Optional[PageLog] = None
        self._pages: List[PageLog] = []

    def start_page(self, url: str):
        """페이지 진입 시 호출"""
        if self._current_page:
            self._current_page.close()
            self._pages.append(self._current_page)

        self._step_counter += 1
        self._current_page = PageLog(self._step_counter, url)

    def log_action(
        self,
        action_type: str,
        target_html: Optional[str] = None,
        coord_x: Optional[int] = None,
        coord_y: Optional[int] = None,
        scroll_y: Optional[int] = None,
        step: int = 0,
        is_failed: bool = False,
        hesitation_ms: Optional[int] = None,
        failure_context: Optional[Dict] = None,
        step_file: Optional[str] = None,
    ):
        """액션 발생 시 호출"""
        if not self._current_page:
            return

        action = ActionLog(
            action_type=action_type,
            target_html=target_html,
            coord_x=coord_x,
            coord_y=coord_y,
            scroll_y=scroll_y,
            step=step,
            is_failed=is_failed,
            hesitation_ms=hesitation_ms,
            failure_context=failure_context,
            step_file=step_file,
        )
        self._current_page.add_action(action)

    def end_page(self, status: str = "success"):
        """페이지 이탈 시 호출 (URL 변경 감지 시점)"""
        if self._current_page:
            self._current_page.close(status=status)
            self._pages.append(self._current_page)
            self._current_page = None

    def finalize(self, is_success: bool):
        """세션 종료 시 호출"""
        if self._current_page:
            self.end_page()

        self.is_success = is_success
        self.total_duration_ms = int((time.time() - self._start_time) * 1000)

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "persona_age": self.persona_age,
            "is_success": self.is_success,
            "total_duration_ms": self.total_duration_ms,
            "pages": [p.to_dict() for p in self._pages],
        }

    def save(self, output_dir: str = ".") -> str:
        """
        JSON 파일로 저장

        Returns:
            저장된 파일 경로
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        filename = f"{self.session_id}.json"
        filepath = Path(output_dir) / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

        print(f"✅ 로그 저장: {filepath}")
        return str(filepath)