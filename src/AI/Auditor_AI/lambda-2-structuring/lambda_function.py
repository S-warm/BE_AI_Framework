import json
import re
import boto3
import os
from pathlib import Path

s3 = boto3.client('s3')
BUCKET = BUCKET = os.environ.get('S3_BUCKET')

def lambda_handler(event, context):
    """
    Step Functions Map에서 페르소나 그룹 1개 받음
    event = {"age": "20s", "sessions": ["raw/logs/.../AI-sess_xxx.json", ...]}
    """
    
    age = event['age']
    sessions = event['sessions']
    
    issue_keys = []
    for sess_key in sessions:
        issue_key = process_session(age, sess_key)
        issue_keys.append(issue_key)
    
    return {'status': 'ok', 'age': age, 'issue_keys': issue_keys}


def process_session(age: str, sess_key: str) -> str:
    # AI-sess 읽기
    sess_obj = s3.get_object(Bucket=BUCKET, Key=sess_key)
    sess = json.loads(sess_obj['Body'].read())
    
    session_id = sess['session_id']
    base_prefix = str(Path(sess_key).parent)  # raw/logs/날짜/20s/sim_xxx
    
    # 날짜 + sim uuid 추출 (structured 저장 경로용)
    parts = Path(sess_key).parts
    date_prefix = parts[2]   # 2026-05-02_14-20-34
    sim_uuid = parts[4]      # sim_c69a6a
    structured_base = f"raw/logs/{date_prefix}/structured/{age}/{sim_uuid}"
    
    # step 파일 목록
    step_files = list_step_files(base_prefix)
    
    # step_001 → goal/success_condition
    task = load_task(base_prefix)
    
    # is_failed=True 액션의 step 번호 수집
    failed_steps = collect_failed_steps(sess)
    
    # step_002~ 읽기 (step=0 제외)
    steps_data = load_steps(base_prefix, step_files)
    
    # 구조화
    issue_doc = build_issue_doc(sess, task, steps_data, failed_steps)
    heatmap_doc = build_heatmap_doc(sess)
    summary_doc = build_summary_doc(sess)
    
    # S3 저장
    save(f"{structured_base}/issue/{session_id}.json", issue_doc)
    save(f"{structured_base}/heatmap/{session_id}.json", heatmap_doc)
    save(f"{structured_base}/summary/{session_id}.json", summary_doc)
    
    return f"raw/logs/{date_prefix}/structured/{age}/{sim_uuid}/issue/{session_id}.json"

def list_step_files(prefix: str) -> list:
    """
    prefix 폴더 안의 step_xxx.json 파일 목록 반환 (정렬)
    step_001.json 포함
    
    step_001.json도 포함해서 반환 load_task에서 step_001 따로 읽고, load_steps에서 step_001 제외
    """

    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
    files = [
        obj['Key'] for obj in resp.get('Contents', [])
        if re.search(r'step_\d+\.json', obj['Key'])
    ]
    return sorted(files)

def load_task(prefix: str) -> dict:
    """
    step_001.json의 ai_response에서 goal, success_condition 추출
    """
    
    key = f"{prefix}/step_001.json"
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    data = json.loads(obj['Body'].read())
    ai = data.get('ai_response', {})
    return {
        'goal': ai.get('goal', ''),
        'success_condition': ai.get('success_condition', ''),
    }

def collect_failed_steps(sess: dict) -> set:
    """
    AI-sess의 actions 순회 → is_failed=True인 액션의 step 번호 수집
    Lambda 2에서 failed_tier_elements 파싱 대상 결정에 사용
    """
    failed = set()
    for page in sess.get('pages', []):
        for action in page.get('actions', []):
            if action.get('is_failed') and action.get('step_file'):
                failed.add(action['step_file'])
    return failed

def load_steps(prefix: str, step_files: list) -> dict:
    """
    step 번호 → step 데이터 dict 반환
    {1: {step데이터}, 2: {step데이터}, ...}
    step_001은 포함하지 않음 (task parser 전용)
    """
    
    steps = {}
    for key in step_files:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        data = json.loads(obj['Body'].read())
        step_num = data.get('step')
        file_name = Path(key).name  # "step_006.json"
        if step_num is not None and step_num != 0:
            steps[file_name] = data  # 파일명을 키로
    return steps

def parse_failed_tier_elements(prompt: str) -> list:
    """
    is_failed=True 스텝의 prompt에서 상 tier 요소 목록 파싱
    정규식으로 [인덱스] text '...' at (x:, y:) 패턴 추출
    """

    pattern = r'\[(\d+)\]\s+\S+\s+\'([^\']+)\'\s+at\s+\(x:([\d.]+),\s*y:([\d.]+)'
    matches = re.findall(pattern, prompt)
    return [
        {
            'index': int(m[0]),
            'text': m[1],
            'x': float(m[2]),
            'y': float(m[3])
        }
        for m in matches
    ]

def build_issue_doc(sess: dict, task: dict, steps_data: dict, failed_steps: set) -> dict:
    # URL 기준 청킹은 AI-sess pages 구조가 이미 페이지별로 나뉘어 있어서 그대로 활용
    pages = []
    for page in sess.get('pages', []):
        steps = []
        for action in page.get('actions', []):
            # 해당 step의 ai_response에서 reasoning 추출
            step_file = action.get('step_file')
            step = steps_data.get(step_file, {})
            ai = step.get('ai_response', {})

            entry = {
                'action_type': action['action_type'],
                'target_html': action.get('target_html'),
                'is_failed': action.get('is_failed', False),
                'coord_x': action.get('coord_x'),
                'coord_y': action.get('coord_y'),
                'reasoning': ai.get('reasoning', ''),
                'found_tier': ai.get('found_tier'),
                'failure_context': action.get('failure_context'),
            }

            # is_failed=True인 스텝만 prompt 파싱해서 failed_tier_elements 추가
            if step_file in failed_steps:
                prompt = step.get('prompt', '')
                entry['failed_tier_elements'] = parse_failed_tier_elements(prompt)

            steps.append(entry)

        pages.append({
            'url': page['url'],
            'page_duration_ms': page.get('page_duration_ms'),
            'steps': steps,
        })

    return {
        'session_id': sess['session_id'],
        'persona_age': sess['persona_age'],
        'is_success': sess['is_success'],
        'goal': task['goal'],
        'success_condition': task['success_condition'],
        'pages': pages,
    }

def build_heatmap_doc(sess: dict) -> dict:
    # coord_x, coord_y, is_failed, url만 추출
    # AI 없이 순수 좌표 데이터만 모음
    points = []
    for page in sess.get('pages', []):
        for action in page.get('actions', []):
            if action.get('coord_x') is not None:
                points.append({
                    'url': page['url'],
                    'coord_x': action['coord_x'],
                    'coord_y': action['coord_y'],
                    'is_failed': action.get('is_failed', False),
                })
    return {
        'session_id': sess['session_id'],
        'persona_age': sess['persona_age'],
        'points': points,
    }

def build_summary_doc(sess: dict) -> dict:
    total_actions = 0
    declare_failure_count = 0

    for page in sess.get('pages', []):
        for action in page.get('actions', []):
            total_actions += 1
            if action.get('action_type') == 'declare_failure':
                declare_failure_count += 1

    return {
        'session_id': sess['session_id'],
        'persona_age': sess['persona_age'],
        'is_success': sess['is_success'],
        'total_duration_ms': sess['total_duration_ms'],
        'total_actions': total_actions,
        'declare_failure_count': declare_failure_count,
    }

def save(key: str, doc: dict):
    # S3에 JSON 저장
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(doc, ensure_ascii=False, indent=2),
        ContentType='application/json',
    )