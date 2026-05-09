import json
import boto3
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone

s3 = boto3.client('s3')
BUCKET = os.environ.get('S3_BUCKET')
SPRING_BASE_URL = os.environ.get('SPRING_BASE_URL')  # ex) http://10.0.1.100:8080
PRESIGNED_EXPIRES = 3600  # 1시간


def lambda_handler(event, context):
    date_prefix = event['date_prefix']
    
    results = {}
    results['overview'] = post_overview(date_prefix)
    results['issues'] = post_issues(date_prefix)
    results['heatmap'] = post_heatmap(date_prefix)
    results['wcag'] = post_wcag(date_prefix)
    results['fixes'] = post_fixes(date_prefix)
    
    print(f"[Post] done: {results}")
    return {'status': 'ok', 'results': results}


def read_s3_json(key: str) -> dict:
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    return json.loads(obj['Body'].read())


def make_presigned_url(key: str) -> str | None:
    try:
        return s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET, 'Key': key},
            ExpiresIn=PRESIGNED_EXPIRES,
        )
    except Exception as e:
        print(f"[Lambda8] presigned url failed {key}: {e}")
        return None


def get_screenshot_url(date_prefix: str, url: str) -> str | None:
    url_encoded = urllib.parse.quote(url, safe='')
    key = f"raw/logs/{date_prefix}/screenshots/{url_encoded}.png"
    return make_presigned_url(key)


def post_json(endpoint: str, payload: dict) -> str:
    url = f"{SPRING_BASE_URL}{endpoint}"
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return f"{resp.status}"
    except Exception as e:
        print(f"[Lambda8] POST failed {url}: {e}")
        return f"error: {e}"


def post_overview(date_prefix: str) -> str:
    key = f"raw/logs/{date_prefix}/analyzed/summary_aggregation.json"
    payload = read_s3_json(key)
    return post_json(f"/api/simulations/{date_prefix}/overview", payload)


def post_issues(date_prefix: str) -> str:
    key = f"raw/logs/{date_prefix}/analyzed/final_issues.json"
    payload = read_s3_json(key)
    
    # 이슈별 스크린샷 presigned URL 추가
    for issue in payload.get('issues', []):
        issue['screenshotUrl'] = get_screenshot_url(date_prefix, issue['url'])
    
    return post_json(f"/api/simulations/{date_prefix}/issues", payload)


def post_heatmap(date_prefix: str) -> str:
    key = f"raw/logs/{date_prefix}/analyzed/heatmap_aggregation.json"
    payload = read_s3_json(key)
    
    # URL별 스크린샷 presigned URL 추가
    seen = {}
    for point in payload.get('errorPoints', []):
        url = point['url']
        if url not in seen:
            seen[url] = get_screenshot_url(date_prefix, url)
        point['screenshotUrl'] = seen[url]
    
    return post_json(f"/api/simulations/{date_prefix}/heatmap", payload)


def post_wcag(date_prefix: str) -> str:
    key = f"raw/logs/{date_prefix}/analyzed/wcag.json"
    payload = read_s3_json(key)
    
    # URL별 스크린샷 presigned URL 추가
    for url, result in payload.get('urls', {}).items():
        result['screenshotUrl'] = get_screenshot_url(date_prefix, url)
    
    return post_json(f"/api/simulations/{date_prefix}/wcag", payload)


def post_fixes(date_prefix: str) -> str:
    """fixes는 URL별로 파일이 분리되어 있어서 목록 먼저 탐색"""
    prefix = f"raw/logs/{date_prefix}/analyzed/fixes/"
    paginator = s3.get_paginator('list_objects_v2')
    
    all_fixes = []
    seen_urls = {}
    
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if not key.endswith('fix.json'):
                continue
            try:
                fix_data = read_s3_json(key)
                url = fix_data.get('url', '')
                
                if url not in seen_urls:
                    seen_urls[url] = get_screenshot_url(date_prefix, url)
                fix_data['screenshotUrl'] = seen_urls[url]
                
                all_fixes.append(fix_data)
            except Exception as e:
                print(f"[Lambda8] skip {key}: {e}")
    
    payload = {'fixes': all_fixes}
    return post_json(f"/api/simulations/{date_prefix}/fixes", payload)