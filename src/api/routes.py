"""
/simulate = age_count 합산해서 총 N개 Celery 태스크 큐에 넣고 job_id 즉시 반환
/status/{job_id} = Redis에서 completed|total|failed 읽어서 반환. completed+failed >= total이면 완료.
/result/{job_id} = 완료된 S3 URL 반환. 아직 진행 중이면 202 반환.
TODO 하나 있음 — task 문자열 생성 로직 나중에 개선 필요.
"""



import uuid
import json
from fastapi import APIRouter, HTTPException
from slugify import slugify

from api.schemas import (
    SimulationRequest,
    SimulationStartResponse,
    SimulationStatusResponse,
    SimulationResultResponse,
    S3Results,
)
from api.worker import celery_app, run_simulation, update_status

router = APIRouter()


# ────────────────────────────────────────────
# 연령대 → age_group 문자열 매핑
# Spring DTO의 ageCount10~70 → BasePersona 인자
# ────────────────────────────────────────────
AGE_MAP = {
    "age_count_10": "10s",
    "age_count_20": "20s",
    "age_count_30": "30s",
    "age_count_40": "40s",
    "age_count_50": "50s",
    "age_count_60": "60s",
    "age_count_70": "70s",
}


# ────────────────────────────────────────────
# POST /simulate
# Spring이 시뮬레이션 요청을 보내는 엔드포인트
# 연령대별 count만큼 Celery 태스크 생성 후 job_id 즉시 반환
# ────────────────────────────────────────────
@router.post("/simulate", response_model=SimulationStartResponse)
async def start_simulation(request: SimulationRequest):

    # job_id 발급 (이번 배치 전체 식별자)
    job_id = str(uuid.uuid4())

    # 전체 페르소나 수 계산
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

    # 초기 상태 Redis에 저장
    update_status(job_id, completed=0, total=total, failed=0)

    # title slug 변환 (S3 경로용)
    title_slug = slugify(request.title) or "untitled"

    # 연령대별 Celery 태스크 생성
    # 예: age_count_20=50 이면 run_simulation을 50번 큐에 넣음
    for field, age_group in AGE_MAP.items():
        count = age_counts[field]
        for _ in range(count):
            run_simulation.delay(
                job_id=job_id,
                target_url=request.target_url,
                task=f"{request.target_url} 에서 목표를 달성해줘",  # TODO: task 생성 로직 개선
                age_group=age_group,
                success_condition=request.success_condition.dict(),
                title=title_slug,
            )

    return SimulationStartResponse(job_id=job_id)


# ────────────────────────────────────────────
# GET /status/{job_id}
# Spring이 폴링으로 진행 상황 확인하는 엔드포인트
# 페르소나 1개 완료마다 Redis 값이 갱신됨
# ────────────────────────────────────────────
@router.get("/status/{job_id}", response_model=SimulationStatusResponse)
async def get_status(job_id: str):

    # Redis에서 상태 조회
    raw = celery_app.backend.get(f"status:{job_id}")

    if raw is None:
        raise HTTPException(status_code=404, detail="job_id를 찾을 수 없습니다.")

    # "completed|total|failed" 파싱
    completed, total, failed = map(int, raw.decode().split("|"))

    # 완료 여부 판단
    if completed + failed >= total:
        status = "completed"
    else:
        status = "running"

    return SimulationStatusResponse(
        job_id=job_id,
        status=status,
        completed=completed,
        total=total,
        failed=failed,
    )


# ────────────────────────────────────────────
# GET /result/{job_id}
# 시뮬레이션 완료 후 S3 결과 URL 반환
# Spring이 이 URL로 S3에서 JSON 읽어서 DTO 파싱
# ────────────────────────────────────────────
@router.get("/result/{job_id}", response_model=SimulationResultResponse)
async def get_result(job_id: str):

    # Redis에서 상태 확인
    raw = celery_app.backend.get(f"status:{job_id}")

    if raw is None:
        raise HTTPException(status_code=404, detail="job_id를 찾을 수 없습니다.")

    completed, total, failed = map(int, raw.decode().split("|"))

    if completed + failed < total:
        raise HTTPException(status_code=202, detail="아직 진행 중입니다.")

    # Redis에서 S3 결과 URL 조회
    result_raw = celery_app.backend.get(f"result:{job_id}")

    if result_raw is None:
        raise HTTPException(status_code=404, detail="결과를 찾을 수 없습니다.")

    result = json.loads(result_raw.decode())

    return SimulationResultResponse(
        job_id=job_id,
        status="completed",
        results=S3Results(**result),
    )