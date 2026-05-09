import json
import boto3
import os
from collections import defaultdict

s3 = boto3.client('s3')
BUCKET = os.environ.get('S3_BUCKET')

def lambda_handler(event, context):
    date_prefix = event['date_prefix']
    
    summary_files = collect_summary_files(date_prefix)
    aggregated = aggregate(summary_files)
    result = build_result(aggregated)
    save(date_prefix, result)
    
    return {'status': 'ok', 'total_files': len(summary_files)}


def collect_summary_files(date_prefix: str) -> list:
    """structured/ 하위 summary/ 폴더의 .json 파일 키 목록 반환"""
    prefix = f"raw/logs/{date_prefix}/structured/"
    paginator = s3.get_paginator('list_objects_v2')
    keys = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if '/summary/' in key and key.endswith('.json'):
                keys.append(key)
    return keys


def aggregate(summary_files: list) -> dict:
    """summary 파일 읽어서 age_group별 누적합 계산, 파싱 실패 파일은 skip"""
    data = defaultdict(lambda: {
        'total_sessions': 0,
        'success_count': 0,
        'duration_sum': 0,
        'actions_sum': 0,
        'declare_failure_sum': 0,
    })
    
    for key in summary_files:
        try:
            obj = s3.get_object(Bucket=BUCKET, Key=key)
            sess = json.loads(obj['Body'].read())
            
            age_group = f"{sess['persona_age']}s"
            d = data[age_group]
            d['total_sessions'] += 1
            d['success_count'] += 1 if sess['is_success'] else 0
            d['duration_sum'] += sess.get('total_duration_ms', 0)
            d['actions_sum'] += sess.get('total_actions', 0)
            d['declare_failure_sum'] += sess.get('declare_failure_count', 0)
        except Exception as e:
            print(f"[Lambda7] skip {key}: {e}")
            continue
    
    return data


def build_result(aggregated: dict) -> dict:
    """누적합 → summary 카드 + overview 차트 포맷 반환"""
    
    # 전체 합산
    total_sessions = sum(d['total_sessions'] for d in aggregated.values())
    total_success = sum(d['success_count'] for d in aggregated.values())
    total_duration = sum(d['duration_sum'] for d in aggregated.values())
    
    summary = {
        'success_rate': round(total_success / total_sessions, 4) if total_sessions else 0,
        'total_sessions': total_sessions,
        'avg_duration_ms': round(total_duration / total_sessions) if total_sessions else 0,
        'success_count': total_success,
    }
    
    # 연령대별
    overview = []
    for age_group in sorted(aggregated.keys()):
        d = aggregated[age_group]
        n = d['total_sessions']
        overview.append({
            'age_group': age_group,
            'total_sessions': n,
            'success_count': d['success_count'],
            'success_rate': round(d['success_count'] / n, 4) if n else 0,
            'fail_rate': round((n - d['success_count']) / n, 4) if n else 0,
            'avg_duration_ms': round(d['duration_sum'] / n) if n else 0,
            'avg_actions': round(d['actions_sum'] / n, 2) if n else 0,
            'avg_declare_failure': round(d['declare_failure_sum'] / n, 2) if n else 0,
        })
    
    return {'summary': summary, 'overview': overview}


def save(date_prefix: str, result: dict):
    """summary_aggregation.json S3 저장"""
    key = f"raw/logs/{date_prefix}/analyzed/summary_aggregation.json"
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(result, ensure_ascii=False, indent=2),
        ContentType='application/json',
    )
    print(f"[Lambda7] saved: {key}")