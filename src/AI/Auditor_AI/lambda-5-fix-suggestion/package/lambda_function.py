"""
Lambda 5 - URL별 Fix 제안 생성

역할:
    final_issues.json의 URL 기준으로 S3 DOM HTML을 가져와
    GPT-4o로 Fix 제안을 생성하고 URL별 fix.json으로 저장.

입력 (S3):
    - raw/logs/{date_prefix}/analyzed/final_issues.json
    - raw/logs/{date_prefix}/dom/{url_encoded}.html

출력 (S3):
    - raw/logs/{date_prefix}/analyzed/fixes/{url_encoded}/fix.json

Step Functions 입력:
    {
        "date_prefix": "2026-05-03_23-10-12"
    }
"""

import json
import boto3
from urllib.parse import quote, unquote
from typing import List, Dict, Optional
from pathlib import Path
from botocore.exceptions import ClientError
import anthropic
import os
import re

s3 = boto3.client("s3")
BUCKET = os.environ.get("S3_BUCKET")


def lambda_handler(event: Dict, context) -> Dict:
    """
    Lambda 진입점

    흐름:
    1. final_issues.json 읽기
    2. URL 기준으로 이슈 그루핑
    3. URL별 DOM 읽기
    4. URL별 Claude Fix 제안 생성
    5. URL별 fix.json S3 저장

    Args:
        event: Step Functions에서 받는 입력 {"date_prefix": "..."}
        context: Lambda context (미사용)

    Returns:
        {"status": "ok", "fix_count": N}
    """
    date_prefix = event["date_prefix"]

    # 1. final_issues 읽기
    issues = load_final_issues(date_prefix)

    # 2. URL 기준 그루핑
    grouped = group_by_url(issues)

    fix_count = 0
    for url, url_issues in grouped.items():
        # 3. DOM 읽기
        dom_data = load_dom(date_prefix, url)
        if not dom_data:
            print(f"[Lambda5] DOM 없음 스킵: {url}")
            continue

        # 4. Fix 제안 생성
        fix = generate_fix(url, url_issues, dom_data)

        # 5. S3 저장
        save_fix(date_prefix, url, fix)
        fix_count += 1

    return {"status": "ok", "fix_count": fix_count}


def load_final_issues(date_prefix: str) -> List[Dict]:
    """
    S3에서 final_issues.json 읽기

    Args:
        date_prefix: S3 경로용 날짜 prefix

    Returns:
        issues 리스트
    """
    s3_key = f"raw/logs/{date_prefix}/analyzed/final_issues.json"
    
    response = s3.get_object(Bucket=BUCKET, Key=s3_key)
    data = json.loads(response["Body"].read().decode("utf-8"))
    
    return data.get("issues", [])


def group_by_url(issues: List[Dict]) -> Dict[str, List[Dict]]:
    """
    이슈를 URL 기준으로 그루핑

    Args:
        issues: final_issues의 issues 리스트

    Returns:
        {url: [issue, ...]} dict
    """
    grouped = {}

    for issue in issues:
        url = issue.get("url")
        if not url:
            continue
        if url not in grouped:
            grouped[url] = []
        grouped[url].append(issue)

    return grouped


def load_dom(date_prefix: str, url: str) -> Optional[Dict]:
    """
    S3에서 URL에 해당하는 DOM 데이터 읽기

    Args:
        date_prefix: S3 경로용 날짜 prefix
        url: 원본 URL

    Returns:
        {"html": ..., "styles": [...]} dict. 없으면 None
    """
    s3_key = f"raw/logs/{date_prefix}/dom/{encode_url(url)}.json"

    try:
        response = s3.get_object(Bucket=BUCKET, Key=s3_key)
        return json.loads(response["Body"].read().decode("utf-8"))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print(f"[Lambda5] DOM 없음: {s3_key}")
            return None
        raise
    

def extract_json(text: str) -> dict:
    """응답에서 JSON 부분만 추출"""
    import re
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"JSON을 찾을 수 없음: {text}")


def generate_fix(url: str, issues: List[Dict], dom_data: Dict) -> Dict:
    """
    Claude로 URL별 Fix 제안 생성

    흐름:
    1. Claude에게 HTML + issue 넘겨서 해당 요소 selector 찾기
    2. selector로 styles에서 현재 CSS 추출
    3. Claude에게 현재 CSS + issue 넘겨서 before/after 생성

    Args:
        url: 대상 URL
        issues: 해당 URL의 이슈 리스트
        dom_data: DOMExtractor가 저장한 {"html": ..., "styles": [...]}

    Returns:
        {
            "url": url,
            "fixes": [
                {
                    "issue_title": "...",
                    "selector": "...",
                    "before": "...",
                    "after": "...",
                    "description": "...",
                    "impact": "..."
                }
            ]
        }
    """
    client = anthropic.Anthropic()
    html = dom_data.get("html", "")
    body_start = html.find('<body')
    html_body = html[body_start:body_start+5000] if body_start != -1 else html[:5000]
    styles = dom_data.get("styles", [])
    fixes = []

    for issue in issues:
        try:
            # === 1차 호출: 요소 selector 찾기 ===
            selector_prompt = f"""다음 HTML에서 아래 UX 이슈와 관련된 요소의 CSS selector를 찾아줘.

이슈 정보:
- 제목: {issue.get('title')}
- 설명: {issue.get('description')}
- 대상 요소: {issue.get('targetHtml')}
- 카테고리: {issue.get('category')} / {issue.get('subCategory')}

HTML (일부):
{html_body}

JSON으로만 응답:
{{"selector": "찾은 CSS selector"}}"""

            selector_response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{"role": "user", "content": selector_prompt}]
            )
            raw_text = selector_response.content[0].text
            raw_text = raw_text.strip().removeprefix("```json").removesuffix("```").strip()
            print(f"[Lambda5] 1차 응답: {raw_text}")
            selector_data = extract_json(raw_text)
            selector = selector_data.get("selector", "")

            # === selector로 현재 CSS 추출 ===
            current_styles = {}
            for el in styles:
                if el.get("selector") == selector:
                    current_styles = el.get("styles", {})
                    break

            # === 2차 호출: before/after CSS 생성 ===
            fix_prompt = f"""다음 UX 이슈를 해결하는 CSS 수정 코드를 생성해줘.

이슈 정보:
- 제목: {issue.get('title')}
- 설명: {issue.get('description')}
- 심각도: {issue.get('severity')}
- 실패율: {issue.get('fail_rate')}
- 영향받은 연령대: {list(set(issue.get('persona_ages', [])))}

현재 CSS ({selector}):
{json.dumps(current_styles, ensure_ascii=False)}

규칙:
1. before는 현재 CSS 그대로
2. after는 이슈 해결을 위한 수정 CSS
3. CSS 클래스 형태로 작성 (예: .selector {{ property: value; }})
4. description은 한국어로 무엇이 왜 변경되었는지 1-2문장
5. impact는 한국어로 예상 개선 효과 1문장

JSON으로만 응답:
{{
    "before": "CSS 코드",
    "after": "CSS 코드",
    "description": "...",
    "impact": "..."
}}"""

            fix_response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
                messages=[{"role": "user", "content": fix_prompt}]
            )
            raw_fix_text = fix_response.content[0].text
            raw_fix_text = raw_fix_text.strip().removeprefix("```json").removesuffix("```").strip()
            print(f"[Lambda5] 2차 응답: {raw_fix_text}")
            fix_data = extract_json(raw_fix_text)

            fixes.append({
                "issue_title": issue.get("title"),
                "selector": selector,
                "before": fix_data.get("before", ""),
                "after": fix_data.get("after", ""),
                "description": fix_data.get("description", ""),
                "impact": fix_data.get("impact", "")
            })

        except Exception as e:
            print(f"[Lambda5] Fix 생성 실패: {issue.get('title')} → {e}")
            fixes.append({
                "issue_title": issue.get("title"),
                "error": str(e)
            })

    return {"url": url, "fixes": fixes}


def save_fix(date_prefix: str, url: str, fix: Dict) -> str:
    """
    fix.json S3 저장

    Args:
        date_prefix: S3 경로용 날짜 prefix
        url: 원본 URL (경로 생성용)
        fix: 저장할 fix 결과 dict

    Returns:
        S3 key 문자열
    """
    encoded = encode_url(url)
    local_path = Path(f"/tmp/fix_{encoded}.json")

    with open(local_path, "w", encoding="utf-8") as f:
        json.dump(fix, f, ensure_ascii=False, indent=2)

    s3_key = f"raw/logs/{date_prefix}/analyzed/fixes/{encoded}/fix.json"

    s3.put_object(
        Bucket=BUCKET,
        Key=s3_key,
        Body=open(local_path, "rb").read(),
        ContentType="application/json"
    )
    print(f"[Lambda5] S3 저장: {s3_key}")

    return s3_key


def encode_url(url: str) -> str:
    """URL을 S3 키로 사용 가능한 문자열로 인코딩"""
    return quote(url, safe='')