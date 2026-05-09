# src/AI/navigation_AI/navigation_loop/task_parser.py

"""
목표 파싱 - 자연어 목표를 구조화된 Task로 변환
"""
import json
from typing import Dict


TASK_PARSING_PROMPT = """
사용자가 입력한 목표를 분석하여 다음 JSON 형식으로 변환하세요.

**응답 형식**:
{{
    "goal": "원본 목표 그대로",
    "final_target": "최종적으로 달성해야 할 것 (간결하게)",
    "success_condition": "성공 판단 조건 (1-2문장, 구체적으로)"
}}

**작성 규칙**:
1. final_target: 목표의 핵심 결과물 (예: "링크 클릭", "주문 완료", "가격 확인")
2. success_condition: Navigator AI가 declare_success를 호출할 시점을 명확히 서술
   - "~클릭하기" → "해당 요소 클릭 완료 시 즉시 declare_success"
   - "~확인하기" → "해당 요소 발견 시 declare_success"
   - "~완료하기" → "완료 페이지 도달 또는 완료 메시지 확인 시 declare_success"
3. success_condition에 "내용이 표시된 요소 발견" 같은 모호한 표현 금지

**예시 1**:
입력: "Learn more 링크 클릭하기"
출력:
{{
    "goal": "Learn more 링크 클릭하기",
    "final_target": "Learn more 링크 클릭",
    "success_condition": "'Learn more' 링크 클릭 완료 시 즉시 declare_success"
}}

**예시 2**:
입력: "회원가입 후 로그인하고 3번째 가디건 주문"
출력:
{{
    "goal": "회원가입 후 로그인하고 3번째 가디건 주문",
    "final_target": "3번째 가디건 주문 완료",
    "success_condition": "주문 완료 페이지 도달 또는 '주문 완료' 메시지 확인 시 declare_success"
}}

**예시 3**:
입력: "상품 가격 확인"
출력:
{{
    "goal": "상품 가격 확인",
    "final_target": "상품 가격 확인",
    "success_condition": "가격 정보가 표시된 요소 발견 시 declare_success"
}}

**사용자 입력**: "{goal}"

**출력** (JSON만):
"""


def parse_goal(goal: str, navigator_ai) -> Dict:
    """
    자연어 목표를 구조화된 Task로 파싱
    
    Args:
        goal: 사용자 입력 목표 ("Learn more 링크 클릭하기")
        navigator_ai: OpenAI AI 클라이언트
    
    Returns:
        {
            'goal': str,
            'final_target': str,
            'success_condition': str
        }
    """
    prompt = TASK_PARSING_PROMPT.format(goal=goal)
    
    try:
        response = navigator_ai.call(prompt)
        
        # response가 dict면 그대로, str이면 파싱
        if isinstance(response, dict):
            parsed = response
        else:
            parsed = json.loads(response)
        
        # 필수 필드 검증
        required = ['goal', 'final_target', 'success_condition']
        for field in required:
            if field not in parsed:
                raise ValueError(f"Missing field: {field}")
        
        return parsed
    
    except Exception as e:
        # 파싱 실패 시 기본값 반환
        return {
            'goal': goal,
            'final_target': goal,
            'success_condition': f"'{goal}' 목표 달성 시 declare_success"
        }