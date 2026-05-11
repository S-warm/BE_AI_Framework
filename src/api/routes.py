"""
/simulate = age_count 합산해서 총 N개 Celery 태스크 큐에 넣고 job_id 즉시 반환
/status/{job_id} = Redis에서 completed|total|failed 읽어서 반환. completed+failed >= total이면 완료.
/result/{job_id} = 완료된 S3 URL 반환. 아직 진행 중이면 202 반환.
TODO 하나 있음 — task 문자열 생성 로직 나중에 개선 필요.
"""

import uuid
import json
import redis
import os
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

def get_redis():
    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


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
    status = "completed" if completed + failed >= total else "running"

    return SimulationStatusResponse(
        job_id=job_id, status=status,
        completed=completed, total=total, failed=failed,
    )


@router.get("/result/{job_id}", response_model=SimulationResultResponse)
async def get_result(job_id: str):
    r = get_redis()
    raw = r.get(f"status:{job_id}")

    if raw is None:
        raise HTTPException(status_code=404, detail="job_id를 찾을 수 없습니다.")

    completed, total, failed = map(int, raw.decode().split("|"))

    if completed + failed < total:
        raise HTTPException(status_code=202, detail="아직 진행 중입니다.")

    result_raw = r.get(f"result:{job_id}")
    if result_raw is None:
        raise HTTPException(status_code=404, detail="결과를 찾을 수 없습니다.")

    result = json.loads(result_raw.decode())
    return SimulationResultResponse(
        job_id=job_id, status="completed",
        results=S3Results(**result),
    )