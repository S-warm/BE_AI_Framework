import json
import boto3
import os
from typing import Dict, List, Optional
from botocore.exceptions import ClientError

s3 = boto3.client("s3")
BUCKET = os.environ.get("S3_BUCKET")

VIEWPORT_W = 1920
VIEWPORT_H = 1080


def lambda_handler(event: Dict, context) -> Dict:
    date_prefix = event["date_prefix"]
    issues = load_final_issues(date_prefix)
    session_key_cache = build_session_key_cache(date_prefix)

    error_points = []
    for idx, issue in enumerate(issues):
        points = process_issue(idx, issue, session_key_cache)
        error_points.extend(points)

    result = {"errorPoints": error_points}
    save_result(date_prefix, result)
    return {"status": "ok", "point_count": len(error_points)}


def load_final_issues(date_prefix: str) -> List[Dict]:
    """
    S3에서 final_issues.json 읽기
    
    Returns:
        issues 리스트
    """
    s3_key = f"raw/logs/{date_prefix}/analyzed/final_issues.json"
    response = s3.get_object(Bucket=BUCKET, Key=s3_key)
    data = json.loads(response["Body"].read().decode("utf-8"))
    return data.get("issues", [])

def build_session_key_cache(date_prefix: str) -> Dict[str, str]:
    """
    S3 structured/ 아래 전체를 한 번만 탐색하여
    session_id → S3 key 매핑 dict 생성.
    
    이슈마다 S3를 탐색하면 API 호출이 많아지므로
    미리 전체 목록을 캐싱해두고 재사용.

    Returns:
        {"AI-sess_xxx": "raw/logs/.../structured/.../heatmap/AI-sess_xxx.json"}
    """
    prefix = f"raw/logs/{date_prefix}/structured/"
    cache = {}

    # S3 목록이 1000개 넘을 수 있으므로 paginator 사용
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            # heatmap 폴더 파일만 필터
            if "/heatmap/" not in key:
                continue
            # "AI-sess_xxx.json" → "AI-sess_xxx"
            session_id = key.split("/")[-1].replace(".json", "")
            cache[session_id] = key

    print(f"[Lambda6] heatmap 캐시 구축 완료: {len(cache)}개")
    return cache

def load_heatmap(session_id: str, cache: Dict[str, str]) -> Optional[Dict]:
    """
    캐시에서 S3 key 찾아 heatmap 파일 읽기.
    캐시에 없으면 S3 탐색 없이 바로 None 반환.

    Returns:
        heatmap dict. 없으면 None
    """
    s3_key = cache.get(session_id)
    if not s3_key:
        print(f"[Lambda6] 캐시에 없음: {session_id}")
        return None

    try:
        response = s3.get_object(Bucket=BUCKET, Key=s3_key)
        return json.loads(response["Body"].read().decode("utf-8"))
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print(f"[Lambda6] S3에 없음: {s3_key}")
            return None
        raise

def process_issue(idx: int, issue: Dict, cache: Dict[str, str]) -> List[Dict]:
    """
    이슈 하나에 대해 affected_personas 순회하며
    heatmap에서 실패 좌표 수집 후 집계까지 처리.

    Returns:
        집계된 error_points 리스트
    """
    issue_id = f"issue_{idx}"
    url = issue.get("url", "")
    error_type = f"{issue.get('category', '')}/{issue.get('subCategory', '')}"

    # ageBand별로 raw 좌표 모으기
    # {"20대": [(x, y), ...], "70대": [(x, y), ...]}
    raw_by_age: Dict[str, List[tuple]] = {}

    session_ids = issue.get("session_ids", [])
    persona_ages = issue.get("persona_ages", [])

    for session_id, persona_age in zip(session_ids, persona_ages):
        age_band = to_age_band(persona_age)

        heatmap_data = load_heatmap(session_id, cache)
        if not heatmap_data:
            continue
        
        for point in heatmap_data.get("points", []):
            print(f"[Lambda6] 포인트: {point}")

        # 같은 URL + is_failed: true 좌표만 수집
        for point in heatmap_data.get("points", []):
            if point.get("url") != url:
                continue
            if not point.get("is_failed", False):
                continue

            # 정규화
            x = round(point["coord_x"] / VIEWPORT_W, 3)
            y = round(point["coord_y"] / VIEWPORT_H, 3)

            if age_band not in raw_by_age:
                raw_by_age[age_band] = []
            raw_by_age[age_band].append((x, y))

    # ageBand별로 근처 좌표 묶어서 집계
    result = []
    for age_band, coords in raw_by_age.items():
        aggregated = aggregate_points(coords)
        for point in aggregated:
            result.append({
                "issueId": issue_id,
                "url": url,
                "x": point["x"],
                "y": point["y"],
                "ageBand": age_band,
                "count": point["count"],
                "severity": calc_severity(point["count"]),
                "errorType": error_type
            })

    return result

def aggregate_points(coords: List[tuple], radius: float = 0.02) -> List[Dict]:
    """
    근처 좌표를 묶어서 count 집계.
    
    방식: 첫 번째 점을 기준으로 반경 radius 안에 있는 점들을 하나로 묶고,
    묶인 점들의 평균 좌표를 대표 좌표로 사용.
    이미 묶인 점은 건너뜀.

    Args:
        coords: [(x, y), ...] 정규화된 좌표 리스트
        radius: 묶을 반경 (기본 0.02 = 약 38px)

    Returns:
        [{"x": x, "y": y, "count": n}, ...]
    """
    used = [False] * len(coords)
    result = []

    for i, (x1, y1) in enumerate(coords):
        if used[i]:
            continue

        # 반경 안에 있는 점 수집
        cluster = [(x1, y1)]
        used[i] = True

        for j, (x2, y2) in enumerate(coords):
            if used[j]:
                continue
            # 유클리드 거리
            dist = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
            if dist <= radius:
                cluster.append((x2, y2))
                used[j] = True

        # 클러스터 평균 좌표
        avg_x = round(sum(p[0] for p in cluster) / len(cluster), 3)
        avg_y = round(sum(p[1] for p in cluster) / len(cluster), 3)

        result.append({
            "x": avg_x,
            "y": avg_y,
            "count": len(cluster)
        })

    return result

def calc_severity(fail_count: int) -> str:
    """
    fail_count 기반 severity 재계산.
    final_issues의 severity는 무시하고 여기서 재계산.

    1~3  → LOW
    4~7  → MEDIUM
    8~14 → HIGH
    15+  → CRITICAL
    """
    if fail_count >= 15:
        return "CRITICAL"
    elif fail_count >= 8:
        return "HIGH"
    elif fail_count >= 4:
        return "MEDIUM"
    else:
        return "LOW"


def to_age_band(persona_age: int) -> str:
    """
    persona_age 숫자 → ageBand 문자열 변환.
    예: 20 → "20s"
    """
    return f"{persona_age}s"

def save_result(date_prefix: str, result: Dict) -> str:
    """
    heatmap_aggregation.json S3 저장.

    Returns:
        저장된 S3 key
    """
    s3_key = f"raw/logs/{date_prefix}/analyzed/heatmap_aggregation.json"
    body = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")

    s3.put_object(
        Bucket=BUCKET,
        Key=s3_key,
        Body=body,
        ContentType="application/json"
    )
    print(f"[Lambda6] S3 저장: {s3_key}")
    return s3_key