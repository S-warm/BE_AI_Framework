"""
NavigationLoop E2E 테스트 (실제 AI + 실제 웹사이트)
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
import time as _time



# .env 로드
load_dotenv()

# 공유 캐시 DB (가이드 → 루프 간 캐시 히트 확인용)
DB_PATH = "test_cache.db"


class MockNavigatorAI:
    """OpenAI GPT-4o-mini 래퍼 (토큰/비용 추적)"""
    
    def __init__(self, log_dir: Optional[str] = None):
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in .env")
        
        self.client = OpenAI(
            api_key=api_key,
            timeout=30.0,
            max_retries=2
        )
        self.model = "gpt-4o-mini"
        
        # 토큰/비용 추적
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        
        # GPT-4o-mini 가격 (2025년 기준)
        self.price_per_1k_prompt = 0.00015  # $0.15/1M tokens
        self.price_per_1k_completion = 0.0006  # $0.60/1M tokens
        
        self.step_logs = []  # 스텝별 로그 저장
        
        # logs 디렉토리 생성
        self.log_dir = Path(log_dir) if log_dir else Path("logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def call(self, prompt: str) -> dict:
        """AI 호출 + 토큰/비용 추적"""
        import json

        print(f"📏 프롬프트 길이: {len(prompt)} chars")
        print(f"📏 예상 토큰: ~{len(prompt) // 4}")
        print(f"\n📋 프롬프트 내용:\n{prompt[:500]}")

        enhanced_prompt = f"{prompt}\n\n**응답 형식: JSON**"

        response = None
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "UX 탐색 AI. 응답은 항상 JSON 형식으로 제공."},
                        {"role": "user", "content": enhanced_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                break  # 성공하면 루프 탈출
            except Exception as e:
                if '429' in str(e):
                    print(f"[RATE_LIMIT] 429 감지, 60초 대기 후 재시도 ({attempt+1}/3)")
                    _time.sleep(60)
                else:
                    raise

        if response is None:
            raise RuntimeError("3회 재시도 후 실패")

        usage = response.usage
        self.total_prompt_tokens += usage.prompt_tokens
        self.total_completion_tokens += usage.completion_tokens
        self.total_tokens += usage.total_tokens

        prompt_cost = (usage.prompt_tokens / 1000) * self.price_per_1k_prompt
        completion_cost = (usage.completion_tokens / 1000) * self.price_per_1k_completion
        self.total_cost += prompt_cost + completion_cost

        raw_response = response.choices[0].message.content
        print(f"\n🤖 AI 원본 응답:\n{raw_response}\n")

        result = json.loads(raw_response)
        print(f"📦 파싱된 결과: {result}\n")

        step_num = len(self.step_logs)
        step_log = {
            'step': step_num,
            'prompt_chars': len(prompt),
            'has_target': 'More information' in prompt,
            'visible_count': prompt.count('['),
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
        """통계 반환"""
        return {
            'prompt_tokens': self.total_prompt_tokens,
            'completion_tokens': self.total_completion_tokens,
            'total_tokens': self.total_tokens,
            'total_cost_usd': round(self.total_cost, 4)
        }
        
    def set_log_dir(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.step_logs = []


@pytest.fixture(scope="function")
def playwright_browser():
    """Playwright 브라우저"""
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=False, channel="chrome")
    context = browser.new_context()
    page = context.new_page()
    page.on("console", lambda msg: print(f"[JS] {msg.text}"))  # ← 추가
    
    yield page
    
    # 정리
    time.sleep(2)
    page.close()
    context.close()
    browser.close()
    p.stop()
    
@pytest.fixture(scope="session")
def session_dir():
    # 순차 실행 기준 - 병렬(pytest-xdist) 전환 시 worker_id로 교체 필요
    dir_path = Path(f"logs/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}")
    dir_path.mkdir(parents=True, exist_ok=True)
    return str(dir_path)


@pytest.fixture
def real_navigator_ai(session_dir):
    return MockNavigatorAI(log_dir=session_dir)

@pytest.fixture(scope="session")
def uploader():
    return S3Uploader(bucket_name=os.getenv('S3_BUCKET'))

@pytest.fixture
def real_normalizer():
    """실제 WebNormalizerIncremental"""
    return WebNormalizerIncremental()

@pytest.fixture(scope="session", autouse=True)
def trigger_step_functions_after_all(session_dir):
    yield  # 모든 테스트 실행
    # 모든 테스트 끝난 후 1회 트리거
    import boto3, json
    client = boto3.client('stepfunctions', region_name='ap-northeast-2')
    client.start_execution(
        stateMachineArn='arn:aws:states:ap-northeast-2:195765661361:stateMachine:swarm-auditor-pipeline',
        input=json.dumps({"prefix": f"raw/{session_dir}"})
    )
    print(f"[STEP_FUNCTIONS] 트리거: raw/{session_dir}")

"""
@pytest.fixture
def navigation_loop_e2e(playwright_browser, real_normalizer, real_navigator_ai, session_dir, request):
    age_group = request.param  # parametrize에서 받아야 함 - 아래 참고
    loop = NavigationLoop(
        page=playwright_browser,
        normalizer=real_normalizer,
        navigator_ai=real_navigator_ai,
        db_path=DB_PATH,  # 공유 DB
        log_dir=f"{session_dir}/{age_group}/sim_1",  # sim 번호: 순차 고정, 추후 카운터로 교체
    )
    loop.max_steps = 100
    return loop
"""


class TestNavigatorGuideE2E:
    
    def test_navigator_guide_warmup(self, playwright_browser, real_navigator_ai, session_dir, uploader):
        """
        url = "https://test-web-fe-kiosk.vercel.app/"
        goal = "매장에서 먹고, 아메리카노 선택해서 온도 아이스, 농도 샷추가, 컵 종이컵 버튼 선택하고 장바구니담기 버튼 선택하고, 포인트 번호는 010-1234-1234, KT 멤버십 선택, 신용카드로 결제해줘. 결제 완료 팝업이 뜨면 확인 버튼 눌러줘."
        success_condition = {'path': '/payment'}
        
        url = "https://www.dbpia.co.kr/"
        goal = "검색창에 '파운데이션 모델' 검색하고 '프롬프트 기반 감성 분석에서 파운데이션 모델의 설명 가능성 및 효율성 비교 연구' 게시글 링크 클릭해줘"
        success_condition = {'path': '/journal/articleDetail', 'required_params': {'nodeId': 'NODE12728926'}}
        """
        
        url = "https://test-web-fe-shopping-mall.vercel.app/shop"
        goal = "상단 네비게이션에서 'Bottom' 카테고리를 클릭해. 상품 목록에서 'Cloud Soft Fleece Pants'를 찾아 클릭해. 상품 상세 페이지에서 '옵션을 선택해 주세요' 드롭박스를 먼저 클릭해서 열면 내부에 색상과 사이즈 드롭박스가 나타나. 색상 드롭박스에서 'White'를 선택하고, 사이즈 드롭박스에서 'Free'를 선택한 후 '바로구매' 버튼을 클릭해."
        success_condition = {'path': '/payment'}
        
        
        uploader = S3Uploader(bucket_name=os.getenv('S3_BUCKET'))
        
        guide = NavigatorGuide(
            page=playwright_browser,
            navigator_ai=real_navigator_ai,
            db_path=DB_PATH,
            uploader=uploader,
        )
        
        start_time = time.time()
        real_navigator_ai.set_log_dir(f"{session_dir}/guide")
        date_prefix = Path(session_dir).name
        result = guide.run(goal=goal, url=url, success_condition=success_condition, session_dir=session_dir, date_prefix=date_prefix)
        elapsed = time.time() - start_time
        
        ai_stats = real_navigator_ai.get_stats()
        
        print("\n" + "="*60)
        print(f"📊 NavigatorGuide 결과")
        print("="*60)
        print(f"상태: {result['status']}")
        print(f"시도 횟수: {result['attempts']}")
        print(f"실행 시간: {elapsed:.2f}초")
        print(f"총 토큰: {ai_stats['total_tokens']:,}")
        print(f"총 비용: ${ai_stats['total_cost_usd']}")
        print("="*60)
        
        assert result['status'] in ['success', 'skipped']
        assert result['attempts'] >= 1

class TestNavigationLoopE2E:
    """E2E 테스트 (실제 AI + 실제 웹사이트)"""
    
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
        """
        실제 웹사이트 탐색 테스트
        
        사용법:
            pytest tests/integration/test_navigation_loop_e2e.py::TestNavigationLoopE2E::test_real_navigation -v -s
        
        커스텀 실행:
            pytest tests/integration/test_navigation_loop_e2e.py -v -s \
                --url="https://naver.com" \
                --goal="검색창 찾기" \
                --age_group="70s" \
                --digital_literacy="low"
        """
        
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

        ai_stats = real_navigator_ai.get_stats()

        print("\n" + "="*60)
        print("📊 실행 결과")
        print("="*60)
        print(f"상태: {result['status']}")
        print(f"총 스텝: {result['total_steps']}")
        print(f"실행 시간: {elapsed_time:.2f}초")
        print()
        print("💰 토큰 & 비용")
        print(f"  - Prompt 토큰: {ai_stats['prompt_tokens']:,}")
        print(f"  - Completion 토큰: {ai_stats['completion_tokens']:,}")
        print(f"  - 총 토큰: {ai_stats['total_tokens']:,}")
        print(f"  - 총 비용: ${ai_stats['total_cost_usd']}")
        print()
        print("🗂️ 캐시 통계")
        for key, value in result['cache_stats'].items():
            print(f"  - {key}: {value}")
        print("="*60)

        assert result['status'] in ['success', 'failure', 'timeout']
        assert result['total_steps'] > 0
        assert ai_stats['total_tokens'] > 0


def pytest_addoption(parser):
    """커스텀 CLI 옵션"""
    parser.addoption("--url", action="store", default=None)
    parser.addoption("--goal", action="store", default=None)
    parser.addoption("--age_group", action="store", default="50s")
    parser.addoption("--digital_literacy", action="store", default="medium")


def pytest_generate_tests(metafunc):
    """CLI 옵션으로 파라미터 오버라이드"""
    if "url" in metafunc.fixturenames:
        url = metafunc.config.getoption("url", default=None)  # default 추가
        if url:
            metafunc.parametrize(
                "url,goal,persona",
                [(
                    url,
                    metafunc.config.getoption("goal", default="페이지 탐색"),
                    {
                        'age_group': metafunc.config.getoption("age_group", default="50s"),
                        'digital_literacy': metafunc.config.getoption("digital_literacy", default="medium")
                    }
                )],
                indirect=False
            )

if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
    
    
    
"""
        pytest.param(
            "https://www.dbpia.co.kr/",
            "검색창에 '파운데이션 모델' 검색하고 '프롬프트 기반 감성 분석에서 파운데이션 모델의 설명 가능성 및 효율성 비교 연구' 게시글 링크 클릭해줘",
            BasePersona('20s'),
            {'path': '/journal/articleDetail', 'required_params': {'nodeId': 'NODE12728926'}},
            id="dbpia_20s"
        ),
        pytest.param(
            "https://www.dbpia.co.kr/",
            "검색창에 '파운데이션 모델' 검색하고 '프롬프트 기반 감성 분석에서 파운데이션 모델의 설명 가능성 및 효율성 비교 연구' 게시글 링크 클릭해줘",
            BasePersona('20s'),
            {'path': '/journal/articleDetail', 'required_params': {'nodeId': 'NODE12728926'}},
            id="dbpia_20s_2"
        ),
        pytest.param(
            "https://www.dbpia.co.kr/",
            "검색창에 '파운데이션 모델' 검색하고 '프롬프트 기반 감성 분석에서 파운데이션 모델의 설명 가능성 및 효율성 비교 연구' 게시글 링크 클릭해줘",
            BasePersona('70s'),
            {'path': '/journal/articleDetail', 'required_params': {'nodeId': 'NODE12728926'}},
            id="dbpia_70s"
        ),




        pytest.param(
            "https://test-web-fe-kiosk.vercel.app/",
            "매장에서 먹고, 아메리카노 선택해서 온도 아이스, 농도 샷추가, 컵 종이컵 버튼 선택하고 장바구니담기 버튼 선택하고, 포인트 번호는 010-1234-1234, KT 멤버십 선택, 신용카드로 결제해줘. 결제 완료 팝업이 뜨면 확인 버튼 눌러줘.",
            BasePersona('20s'),
            {'path': '/payment'},
            id="kiosk_20s"
        ),
        
        pytest.param(
            "https://test-web-fe-shopping-mall.vercel.app/shop",
            "상단 네비게이션에서 'Bottom' 카테고리를 클릭해. 상품 목록에서 'Cloud Soft Fleece Pants'를 찾아 클릭해. 상품 상세 페이지에서 '옵션을 선택해 주세요' 드롭박스를 먼저 클릭해서 열면 내부에 색상과 사이즈 드롭박스가 나타나. 색상 드롭박스에서 'White'를 선택하고, 사이즈 드롭박스에서 'Free'를 선택한 후 '바로구매' 버튼을 클릭해.",
            BasePersona('20s'),
            {'path': '/payment'},
            id="shopping_20s"
        ),
"""
