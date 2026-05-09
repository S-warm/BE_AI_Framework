"""
NavigationLoop E2E 테스트 - Gemini 버전
"""
import pytest
import os
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from pathlib import Path
from typing import Optional

from AI.navigation_AI.navigation_loop.navigation_loop import NavigationLoop
from normalizer.mcp.web_normalizer.web_normalizer_incremental.web_normalizer_incremental import WebNormalizerIncremental
from AI.navigation_AI.navigation_loop.navigator_guide import NavigatorGuide
from AI.layer_tier2.base_persona import BasePersona
from datetime import datetime
from AI.Auditor_AI.utils.s3_uploader import S3Uploader
from fix_code.DOM_extractors import DOMExtractor
import uuid
import re

load_dotenv()
DB_PATH = "test_cache.db"


class ClaudeNavigatorAI:
    """Anthropic Claude Haiku 래퍼"""

    def __init__(self, log_dir: Optional[str] = None):
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in .env")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-haiku-4-5-20251001"

        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.step_logs = []
        self.log_dir = Path(log_dir) if log_dir else Path("logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def call(self, prompt: str) -> dict:
        import json
        print(f"📏 프롬프트 길이: {len(prompt)} chars")
        print(f"\n📋 프롬프트 내용:\n{prompt[:500]}")

        enhanced_prompt = f"{prompt}\n\n**응답 형식: JSON**"

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system="UX 탐색 AI. 응답은 항상 JSON 형식으로 제공.",
            messages=[{"role": "user", "content": enhanced_prompt}]
        )

        self.total_input_tokens += response.usage.input_tokens
        self.total_output_tokens += response.usage.output_tokens

        raw_response = response.content[0].text
        print(f"\n🤖 AI 원본 응답:\n{raw_response}\n")

        # JSON 펜스 제거
        clean = raw_response.strip()
        # 첫 번째 JSON 객체만 추출
        match = re.search(r'\{.*\}', clean, re.DOTALL)
        if not match:
            raise ValueError(f"JSON 파싱 실패: {clean}")
        result = json.loads(match.group())
        print(f"📦 파싱된 결과: {result}\n")

        step_num = len(self.step_logs)
        step_log = {
            'step': step_num,
            'prompt_chars': len(prompt),
            'prompt': prompt,
            'ai_response': result
        }
        self.step_logs.append(step_log)

        log_file = self.log_dir / f"step_{step_num + 1:03d}.json"
        with open(log_file, 'w') as f:
            json.dump(step_log, f, indent=2)

        result['_step_file'] = log_file.name
        return result

    def get_stats(self) -> dict:
        total = self.total_input_tokens + self.total_output_tokens
        cost = (self.total_input_tokens / 1_000_000) * 1.0 + (self.total_output_tokens / 1_000_000) * 5.0
        return {
            'prompt_tokens': self.total_input_tokens,
            'completion_tokens': self.total_output_tokens,
            'total_tokens': total,
            'total_cost_usd': round(cost, 4)
        }

    def set_log_dir(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.step_logs = []

    def get_stats(self) -> dict:
        return {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': self.total_tokens,
            'total_cost_usd': 0.0
        }

    def set_log_dir(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.step_logs = []


@pytest.fixture(scope="function")
def playwright_browser():
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=False, channel="chrome")
    context = browser.new_context()
    page = context.new_page()
    page.on("console", lambda msg: print(f"[JS] {msg.text}"))
    yield page
    time.sleep(2)
    page.close()
    context.close()
    browser.close()
    p.stop()


@pytest.fixture(scope="session")
def session_dir():
    dir_path = Path(f"logs/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}")
    dir_path.mkdir(parents=True, exist_ok=True)
    return str(dir_path)


@pytest.fixture
def real_navigator_ai(session_dir):
    return ClaudeNavigatorAI(log_dir=session_dir)


@pytest.fixture(scope="session")
def uploader():
    return S3Uploader(bucket_name=os.getenv('S3_BUCKET'))


@pytest.fixture
def real_normalizer():
    return WebNormalizerIncremental()


@pytest.fixture(scope="session", autouse=True)
def trigger_step_functions_after_all(session_dir):
    yield
    import boto3, json
    client = boto3.client('stepfunctions', region_name='ap-northeast-2')
    client.start_execution(
        stateMachineArn='arn:aws:states:ap-northeast-2:195765661361:stateMachine:swarm-auditor-pipeline',
        input=json.dumps({"prefix": f"raw/{session_dir}"})
    )
    print(f"[STEP_FUNCTIONS] 트리거: raw/{session_dir}")


class TestNavigationLoopE2E:

    @pytest.mark.parametrize("url,goal,persona,success_condition", [
        pytest.param(
            "https://test-web-fe-shopping-mall.vercel.app/shop",
            "상단 네비게이션에서 'Bottom' 카테고리를 클릭해. 상품 목록에서 'Cloud Soft Fleece Pants'를 찾아 클릭해. 상품 상세 페이지에서 '옵션을 선택해 주세요' 드롭박스를 먼저 클릭해서 열면 내부에 색상과 사이즈 드롭박스가 나타나. 색상 드롭박스에서 'White'를 선택하고, 사이즈 드롭박스에서 'Free'를 선택한 후 '바로구매' 버튼을 클릭해.",
            BasePersona('20s'),
            {'path': '/payment'},
            id="shopping_20s"
        ),
    ])
    def test_real_navigation(self, playwright_browser, real_normalizer, real_navigator_ai, session_dir, uploader, url, goal, persona, success_condition):

        print(f"\n🌐 URL: {url}")
        print(f"🎯 목표: {goal}")
        print(f"👤 Persona: {persona}")

        persona_dir = Path(session_dir) / persona.age_group
        sim_id = uuid.uuid4().hex[:6]
        log_dir = str(persona_dir / f"sim_{sim_id}")

        real_navigator_ai.set_log_dir(log_dir)
        uploader = S3Uploader(bucket_name=os.getenv('S3_BUCKET'))

        loop = NavigationLoop(
            page=playwright_browser,
            normalizer=real_normalizer,
            navigator_ai=real_navigator_ai,
            db_path=DB_PATH,
            log_dir=log_dir,
            session_dir=session_dir,
            uploader=uploader,
        )
        loop.max_steps = 100

        playwright_browser.goto(url, wait_until="networkidle")
        start_time = time.time()
        result = loop.run(goal, persona, success_condition)
        elapsed_time = time.time() - start_time

        visited_urls = result.get('visited_urls', [])
        date_prefix = Path(session_dir).name
        dom_extractor = DOMExtractor(page=playwright_browser, uploader=uploader)
        dom_extractor.run(urls=visited_urls, date_prefix=date_prefix)

        ai_stats = real_navigator_ai.get_stats()

        print("\n" + "="*60)
        print("📊 실행 결과")
        print("="*60)
        print(f"상태: {result['status']}")
        print(f"총 스텝: {result['total_steps']}")
        print(f"실행 시간: {elapsed_time:.2f}초")
        print(f"총 토큰: {ai_stats['total_tokens']:,}")
        print(f"총 비용: ${ai_stats['total_cost_usd']}")
        print("="*60)

        assert result['status'] in ['success', 'failure', 'timeout']
        assert result['total_steps'] > 0
        assert ai_stats['total_tokens'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])