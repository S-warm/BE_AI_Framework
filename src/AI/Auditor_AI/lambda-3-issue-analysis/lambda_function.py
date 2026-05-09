import json
import boto3
import os
from typing import Optional

s3 = boto3.client('s3')
BUCKET = os.environ.get('S3_BUCKET')
SIMILARITY_THRESHOLD = 0.9 # 코사인 유사도 0.9 기준 클러스터링 / url 내에 패턴 묶는 기준임 패턴이 너무 뭉뜨그려 묶이면 수정해야함
SAMPLE_SIZE = 3 # 샘플 context 갯수
THRESHOLD = 0.05 # 패턴 묶고 하위 5%는 제거함 나중에 수정

def lambda_handler(event, context):
    age = event['age']
    issue_keys = event['issue_keys']
    
    # Step 1: 데이터 수집
    sessions = load_sessions(issue_keys)
    
    # Step 2: 집계 대상 필터링
    url_failures = collect_failures(sessions)
    
    # Step 3: Embedding 클러스터링
    url_clusters = cluster_failures(url_failures)
    
    # Step 4: 임계값 필터링
    total_sessions = len(sessions)
    filtered_clusters = filter_by_threshold(url_clusters, total_sessions)
    
    # Step 5: GPT-4o 병렬 호출
    issues = analyze_clusters(filtered_clusters, total_sessions)
    
    # Step 6: S3 저장
    save_issues(age, issue_keys, issues, total_sessions)
    
    return {'status': 'ok', 'age': age, 'issue_count': len(issues)}


def load_sessions(issue_keys: list) -> list:
    # S3에서 issue JSON 읽어서 리스트로 반환.
    sessions = []
    for key in issue_keys:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        session = json.loads(obj['Body'].read())
        sessions.append(session)
    return sessions

def collect_failures(sessions: list) -> dict:
    """
    모든 세션에서 집계 대상 declare_failure 추출
    found_tier: null → 집계 대상
    found_tier: 상/중/하 → 정상 탐색 흐름, 제외
    반환: {url: [failure_entry, ...]}
    """
    url_failures = {}
    
    for session in sessions:
        persona_age = session.get('persona_age')
        for page in session.get('pages', []):
            for step in page.get('steps', []):
                
                # declare_failure + found_tier null 만 집계
                if step.get('action_type') != 'declare_failure':
                    continue
                if not _is_null_tier(step.get('found_tier')):
                    continue
                
                url = page['url']
                if url not in url_failures:
                    url_failures[url] = []
                    
                url_failures[url].append({
                    'failure_context': step.get('failure_context'),
                    'reasoning': step.get('reasoning'),
                    'session_id': session['session_id'],
                    'persona_age': persona_age,
                    'goal': session['goal'],
                })
    
    return url_failures


def _is_null_tier(found_tier) -> bool:
    """found_tier가 null인지 판별 (문자열 'null'도 null 처리)"""
    return found_tier is None or str(found_tier).lower() == 'null'

def cluster_failures(url_failures: dict) -> dict:
    """
    URL별로 failure_context를 임베딩 후 코사인 유사도 0.9 기준 클러스터링
    반환: {url: [cluster, ...]}
    cluster = {
        'failures': [failure_entry, ...],
        'fail_count': int,
    }
    """
    from openai import OpenAI
    client = OpenAI()
    
    url_clusters = {}
    
    for url, failures in url_failures.items():
        # failure_context → 텍스트 변환
        texts = [_context_to_text(f['failure_context']) for f in failures]
        
        # 임베딩 일괄 요청 (비용 최소화)
        response = client.embeddings.create(
            model='text-embedding-3-small',
            input=texts
        )
        embeddings = [item.embedding for item in response.data]
        
        # 코사인 유사도 기반 클러스터링
        clusters = _cluster_by_similarity(failures, embeddings)
        url_clusters[url] = clusters
    
    return url_clusters


def _context_to_text(failure_context: Optional[dict]) -> str:
    """failure_context dict → 임베딩용 텍스트 변환"""
    if not failure_context:
        return ''
    parts = []
    for tier in ['상_tier', '중_tier', '하_tier']:
        items = failure_context.get(tier, [])
        if items:
            parts.append(f"{tier}: {', '.join(items)}")
    return ' | '.join(parts)


def _cluster_by_similarity(failures: list, embeddings: list) -> list:
    """
    코사인 유사도 0.9 이상이면 같은 클러스터로 묶기
    greedy 방식: 첫 번째 미배정 항목을 새 클러스터 대표로
    """
    import math
    
    def cosine_similarity(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
    
    assigned = [False] * len(failures)
    clusters = []
    
    for i in range(len(failures)):
        if assigned[i]:
            continue
        
        cluster = [failures[i]]
        assigned[i] = True
        
        for j in range(i + 1, len(failures)):
            if assigned[j]:
                continue
            similarity = cosine_similarity(embeddings[i], embeddings[j])
            if similarity >= SIMILARITY_THRESHOLD:
                cluster.append(failures[j])
                assigned[j] = True
        
        clusters.append({
            'failures': cluster,
            'fail_count': len(cluster),
            'representative_embedding': embeddings[i],
        })
    
    return clusters

def filter_by_threshold(url_clusters: dict, total_sessions: int) -> dict:
    """
    fail_count / total_sessions < THRESHOLD(5%) 패턴 제거
    노이즈성 단발 실패 걸러내기
    """
    filtered = {}
    
    for url, clusters in url_clusters.items():
        valid_clusters = []
        for cluster in clusters:
            fail_rate = cluster['fail_count'] / total_sessions
            if fail_rate >= THRESHOLD:
                cluster['fail_rate'] = fail_rate
                valid_clusters.append(cluster)
        
        if valid_clusters:
            filtered[url] = valid_clusters
    
    return filtered

def analyze_clusters(filtered_clusters: dict, total_sessions: int) -> list:
    """
    패턴별 GPT-4o 병렬 호출로 UX 이슈 분석
    반환: [issue, ...]
    """
    from openai import OpenAI
    import concurrent.futures
    client = OpenAI()
    
    # 분석 대상 패턴 목록 생성
    tasks = []
    for url, clusters in filtered_clusters.items():
        for cluster in clusters:
            tasks.append((url, cluster, total_sessions))
    
    # 병렬 호출
    issues = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(_analyze_single_cluster, client, url, cluster, total_sessions)
            for url, cluster, total_sessions in tasks
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                issues.append(result)
    
    return issues


def _analyze_single_cluster(client, url: str, cluster: dict, total_sessions: int) -> Optional[dict]:
    """
    클러스터 1개 → GPT-4o 호출 → 이슈 dict 반환
    """
    failures = cluster['failures']
    fail_count = cluster['fail_count']
    fail_rate = cluster['fail_rate']
    
    # failure_context 빈도 집계
    tier_freq = {'상_tier': {}, '중_tier': {}, '하_tier': {}}
    for f in failures:
        ctx = f.get('failure_context') or {}
        for tier in tier_freq:
            for item in ctx.get(tier, []):
                tier_freq[tier][item] = tier_freq[tier].get(item, 0) + 1
    
    # 샘플 추출
    samples = failures[:SAMPLE_SIZE]
    context_samples = [f.get('failure_context') for f in samples]
    reasoning_samples = [f.get('reasoning') for f in samples]
    goal_samples = list({f.get('goal') for f in samples})
    
    prompt = f"""당신은 UX 분석 전문가입니다. 아래 데이터를 분석하여 UX 이슈를 JSON으로 반환하세요.

URL: {url}
목표: {goal_samples}
실패 횟수: {fail_count} / {total_sessions} ({fail_rate:.1%})

failure_context 빈도 (상/중/하 tier별 요소 등장 횟수):
{json.dumps(tier_freq, ensure_ascii=False, indent=2)}

failure_context 샘플 ({SAMPLE_SIZE}개):
{json.dumps(context_samples, ensure_ascii=False, indent=2)}

AI reasoning 샘플 ({SAMPLE_SIZE}개):
{json.dumps(reasoning_samples, ensure_ascii=False, indent=2)}

반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "category": "사용성 | 접근성 | 시각요소",
  "subCategory": "시인성 부족 | 클릭 영역 불명확 | 포커스 이동 오류 | 기타",
  "severity": "high | medium | low",
  "title": "이슈 제목",
  "description": "상세 설명",
  "targetHtml": "문제 요소 자연어 1줄 요약",
  "tags": ["태그1", "태그2"]
}}"""

    try:
        response = client.chat.completions.create(
            model='gpt-4o',
            messages=[{'role': 'user', 'content': prompt}],
            response_format={'type': 'json_object'},
            temperature=0,
        )
        issue = json.loads(response.choices[0].message.content)
        issue['url'] = url
        issue['fail_count'] = fail_count
        issue['fail_rate'] = fail_rate
        issue['embedding'] = cluster.get('representative_embedding')
        issue['session_ids'] = [f['session_id'] for f in failures]
        issue['persona_ages'] = [f['persona_age'] for f in failures]
        return issue
    except Exception as e:
        print(f"[GPT4O_ERROR] {url}: {e}")
        return None

def save_issues(age: str, issue_keys: list, issues: list, total_sessions: int):
    """
    분석 결과 S3 저장
    경로: raw/logs/{날짜}/analyzed/{age}/issues.json
    """
    # 날짜 추출 (issue_keys[0] 기준)
    # raw/logs/2026-05-02_14-20-34/structured/20s/...
    parts = issue_keys[0].split('/')
    date_prefix = parts[2]  # 2026-05-02_14-20-34
    
    output_key = f"raw/logs/{date_prefix}/analyzed/{age}/issues.json"
    
    doc = {
        'age': age,
        'total_sessions': total_sessions,
        'issues': issues,
    }
    
    s3.put_object(
        Bucket=BUCKET,
        Key=output_key,
        Body=json.dumps(doc, ensure_ascii=False, indent=2),
        ContentType='application/json',
    )
    
    print(f"[SAVED] {output_key} ({len(issues)} issues)")