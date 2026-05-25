"""
GPT-4o-mini 래퍼 (토큰/비용 추적)
worker.py와 테스트 코드 둘 다 여기서 임포트해서 사용
"""
import os
import json
import time
from pathlib import Path
from typing import Optional


class NavigatorAI:
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

        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.total_cost = 0.0

        # GPT-4o-mini 가격 (2025년 기준)
        self.price_per_1k_prompt = 0.00015
        self.price_per_1k_completion = 0.0006

        self.step_logs = []

        self.log_dir = Path(log_dir) if log_dir else Path("logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def call(self, prompt: str) -> dict:
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
                break
            except Exception as e:
                if '429' in str(e):
                    print(f"[RATE_LIMIT] 429 감지, 60초 대기 후 재시도 ({attempt+1}/3)")
                    time.sleep(60)
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
        
    def reset_session_stats(self):
        """세션 시작 시 토큰/비용 카운터 리셋"""
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.total_cost = 0.0