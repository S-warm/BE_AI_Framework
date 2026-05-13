"""
/simulate = age_count 합산해서 총 N개 Celery 태스크 큐에 넣고 job_id 즉시 반환
/status/{job_id} = Redis 카운터 + S3 done.json 둘 다 봐서 running/analyzing/completed 판정
/result/{job_id} = S3 done.json 읽어서 결과 URL 반환. 없으면 202.
"""

import uuid
import json
import redis
import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from fastapi import APIRouter, HTTPException
from slugify import slugify

from api.schemas import (
    SimulationRequest, SimulationStartResponse,
    SimulationStatusResponse, SimulationResultResponse, S3Results,
)
from api.worker import run_simulation

router = APIRouter()

AGE_MAP = {
    "age_count_10": "10s",
    "age_count_20": "20s",
    "age_count_30": "30s",
    "age_count_40": "40s",
    "age_count_50": "50s",
    "age_count_60": "60s",
    "age_count_70": "70s",
}

S3_BUCKET = os.getenv("S3_BUCKET")
s3_client = boto3.client('s3', region_name='ap-northeast-2')


def get_redis():
    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


def check_done_exists(job_id: str) -> bool:
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=f"done/{job_id}.json")
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        raise


@router.post("/simulate", response_model=SimulationStartResponse)
async def start_simulation(request: SimulationRequest):
    job_id = str(uuid.uuid4())

    title_slug = slugify(request.title) or "untitled"
    session_dir = f"{title_slug}/logs/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"

    age_counts = {
        "age_count_10": request.age_count_10,
        "age_count_20": request.age_count_20,
        "age_count_30": request.age_count_30,
        "age_count_40": request.age_count_40,
        "age_count_50": request.age_count_50,
        "age_count_60": request.age_count_60,
        "age_count_70": request.age_count_70,
    }
    total = sum(age_counts.values())

    if total == 0:
        raise HTTPException(status_code=400, detail="페르소나 수가 0입니다.")

    r = get_redis()
    r.set(f"status:{job_id}", f"0|{total}|0", ex=3600)

    for field, age_group in AGE_MAP.items():
        count = age_counts[field]
        for _ in range(count):
            run_simulation.delay(
                job_id=job_id,
                target_url=request.target_url,
                task=request.task,
                age_group=age_group,
                success_condition=request.success_condition.dict(),
                title=title_slug,
                session_dir=session_dir,
                total=total,
            )

    return SimulationStartResponse(job_id=job_id)


@router.get("/status/{job_id}", response_model=SimulationStatusResponse)
async def get_status(job_id: str):
    r = get_redis()
    raw = r.get(f"status:{job_id}")

    if raw is None:
        raise HTTPException(status_code=404, detail="job_id를 찾을 수 없습니다.")

    completed, total, failed = map(int, raw.decode().split("|"))

    if completed + failed < total:
        status = "running"
    elif check_done_exists(job_id):
        status = "completed"
    else:
        status = "analyzing"

    return SimulationStatusResponse(
        job_id=job_id, status=status,
        completed=completed, total=total, failed=failed,
    )


@router.get("/result/{job_id}", response_model=SimulationResultResponse)
async def get_result(job_id: str):
    try:
        obj = s3_client.get_object(Bucket=S3_BUCKET, Key=f"done/{job_id}.json")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            raise HTTPException(status_code=202, detail="아직 진행 중입니다.")
        raise

    done = json.loads(obj['Body'].read())
    return SimulationResultResponse(
        job_id=job_id,
        status="completed",
        results=S3Results(**done['results']),
    )
    
@router.get("/health")
async def health():
    return {"status": "ok"}