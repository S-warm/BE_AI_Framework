import json
import math
import boto3
import os

s3 = boto3.client('s3')
BUCKET = os.environ.get('S3_BUCKET')
SIMILARITY_THRESHOLD = 0.9

def lambda_handler(event, context):
    date_prefix = event['date_prefix']
    age_list = event['age_list']

    all_issues, total_sessions = load_all_issues(date_prefix, age_list)   # 전 연령대 issues.json 읽기
    url_groups = group_by_url(all_issues)                  # URL 기준 그루핑
    merged_issues = merge_by_similarity(url_groups)        # 유사도 병합
    save_final_issues(date_prefix, merged_issues)          # S3 저장
    
    # fail_rate 재계산
    for issue in merged_issues:
        issue['fail_rate'] = round(issue['fail_count'] / total_sessions, 4)

    save_final_issues(date_prefix, merged_issues)
    return {'status': 'ok', 'issue_count': len(merged_issues), 'date_prefix': date_prefix, 'age_list': age_list}


def load_all_issues(date_prefix: str, age_list: list) -> list:
    """
    전 연령대 issues.json을 S3에서 읽어 하나의 리스트로 합침.
    없는 연령대는 스킵 (시뮬레이션 안 돌린 케이스 대비).
    각 이슈에 age 태깅해서 나중에 affected_personas 구성할 때 사용.
    """
    all_issues = []
    total_sessions = 0
    for age in age_list:
        key = f"raw/logs/{date_prefix}/analyzed/{age}/issues.json"
        try:
            obj = s3.get_object(Bucket=BUCKET, Key=key)
            data = json.loads(obj['Body'].read())
            for issue in data.get('issues', []):
                issue['_age'] = age  # 내부 태깅용 (출력엔 포함 안 함)
            all_issues.extend(data.get('issues', []))
            total_sessions += data.get('total_sessions', 0)
        except Exception as e:
            print(f"[SKIP] {key}: {e}")
    return all_issues, total_sessions  # tuple 반환

def group_by_url(issues: list) -> dict:
    """
    URL 기준으로 이슈 그루핑.
    같은 URL 내에서만 유사도 비교할 거라 먼저 묶어둠.
    Lambda 3에서 이미 URL별로 분석했으니 자연스럽게 묶임.
    """
    url_groups = {}
    for issue in issues:
        url = issue['url']
        if url not in url_groups:
            url_groups[url] = []
        url_groups[url].append(issue)
    return url_groups

def merge_by_similarity(url_groups: dict) -> list:
    """
    URL별로 이슈들을 embedding 유사도 기준으로 병합.
    Lambda 3 클러스터링과 동일한 greedy 방식 사용.
    embedding 없는 이슈는 병합 대상에서 제외하고 그냥 추가.
    """
    merged = []

    for url, issues in url_groups.items():
        assigned = [False] * len(issues)

        for i in range(len(issues)):
            if assigned[i]:
                continue

            base = issues[i].copy()
            assigned[i] = True

            # embedding 없으면 병합 시도 안 함
            if not base.get('embedding'):
                merged.append(base)
                continue

            for j in range(i + 1, len(issues)):
                if assigned[j]:
                    continue
                if not issues[j].get('embedding'):
                    continue

                similarity = _cosine_similarity(base['embedding'], issues[j]['embedding'])
                if similarity >= SIMILARITY_THRESHOLD:
                    base = _merge_two_issues(base, issues[j])
                    assigned[j] = True

            # 출력에 embedding 제거 (내부 계산용이라 프론트에 불필요)
            base.pop('embedding', None)
            base.pop('_age', None)
            merged.append(base)

    return merged

def _merge_two_issues(base: dict, target: dict) -> dict:
    """
    두 이슈를 하나로 병합.
    대표값은 fail_count 높은 base 기준으로 사용.
    affected_personas는 두 이슈의 session_ids + persona_ages 합산.
    """
    # session_ids, persona_ages 합산
    merged_session_ids = base.get('session_ids', []) + target.get('session_ids', [])
    merged_persona_ages = base.get('persona_ages', []) + target.get('persona_ages', [])

    # affected_personas 구성 ({session_id, persona_age} 쌍)
    affected_personas = [
        {'session_id': sid, 'persona_age': age}
        for sid, age in zip(merged_session_ids, merged_persona_ages)
    ]

    base['fail_count'] = base.get('fail_count', 0) + target.get('fail_count', 0)
    base['session_ids'] = merged_session_ids
    base['persona_ages'] = merged_persona_ages
    base['affected_personas'] = affected_personas

    return base

def _cosine_similarity(a: list, b: list) -> float:
    """
    저장된 embedding 벡터 두 개로 코사인 유사도 계산.
    Lambda 3에서 저장한 representative_embedding 사용하므로
    재임베딩 없이 순수 Python으로 처리.
    """
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

def save_final_issues(date_prefix: str, issues: list):
    """
    병합된 이슈를 final_issues.json으로 S3 저장.
    경로: raw/logs/{date_prefix}/analyzed/final_issues.json
    """
    output_key = f"raw/logs/{date_prefix}/analyzed/final_issues.json"

    doc = {
        'total_issues': len(issues),
        'issues': issues,
    }

    s3.put_object(
        Bucket=BUCKET,
        Key=output_key,
        Body=json.dumps(doc, ensure_ascii=False, indent=2),
        ContentType='application/json',
    )

    print(f"[SAVED] {output_key} ({len(issues)} issues)")