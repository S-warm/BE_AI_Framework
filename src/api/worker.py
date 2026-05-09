"""
Celery 태스크 정의 파일이야. 시뮬레이션 1개를 비동기로 실행하는 단위 작업

run_simulation = 페르소나 1개짜리 시뮬레이션 1회. routes.py에서 age_count만큼 이걸 반복 호출
update_status = Redis에 진행 상태 저장. Spring이 폴링할 때 이 값 읽음
_upload_to_s3 = 지금은 URL만 생성하는 플레이스홀더. S3 수정할 때 boto3로 교체
"""



import os
import uuid
from celery import Celery
from datetime import datetime
from slugify import slugify  # pip install python-slugify

from src.AI.layer_tier2.base_persona import BasePersona
from src.AI.navigation_AI.navigation_loop import NavigationLoop

# ────────────────────────────────────────────
# Celery 앱 초기화
# Redis를 브로커(작업 큐)이자 백엔드(결과 저장소)로 사용
# ────────────────────────────────────────────
celery_app = Celery(
    "ux_swarm",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),   # 작업 받는 곳
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),  # 결과 저장하는 곳
)


# ────────────────────────────────────────────
# 상태 업데이트 헬퍼
# NavigationLoop에서 페르소나 완료 마다 호출해서 폴링 응답에 반영
# ────────────────────────────────────────────
def update_status(job_id: str, completed: int, total: int, failed: int):
    """
    Redis에 현재 진행 상태 저장
    페르소나 1개 완료마다 호출됨
    Spring이 /status/{job_id} 폴링할 때 이 값을 반환함

    Args:
        job_id: 작업 고유 ID
        completed: 완료된 페르소나 수
        total: 전체 페르소나 수
        failed: 실패한 페르소나 수
    """
    celery_app.backend.set(
        f"status:{job_id}",
        f"{completed}|{total}|{failed}",
        ex=3600  # 1시간 후 자동 만료
    )


# ────────────────────────────────────────────
# 핵심 Celery 태스크: 시뮬레이션 1개 실행
# age_group 1개 + 시뮬레이션 1회에 해당
# routes.py에서 age_count만큼 반복 호출됨
# ────────────────────────────────────────────
@celery_app.task(bind=True)
def run_simulation(self, job_id: str, target_url: str, task: str,
                    age_group: str, success_condition: dict, title: str):
    """
    시뮬레이션 단일 실행 태스크

    Args:
        job_id: 전체 배치 작업 ID (같은 요청의 모든 태스크가 공유)
        target_url: 테스트할 URL
        task: AI에게 줄 자연어 지시 (현재는 target_url 기반으로 생성)
        age_group: 페르소나 연령대 ("10s", "20s", ... "70s")
        success_condition: {"path": "/...", "required_params": {...}}
        title: 프로젝트 제목 (S3 경로용)
    """

    # S3 저장 경로 생성
    # title을 slug로 변환 (한글/특수문자 → 영문 소문자)
    # 예: "Q1 2026 체크아웃 테스트" → "q1-2026"
    title_slug = slugify(title) or "untitled"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sim_id = str(uuid.uuid4())[:8]  # 충돌 방지용 짧은 ID

    s3_prefix = f"raw/logs/{title_slug}/{timestamp}/{age_group}/{sim_id}"

    try:
        # ── Step 1: 상태 업데이트 ──
        update_status(job_id, "initializing", 0, 10)

        # ── Step 2: 페르소나 생성 ──
        persona = BasePersona(age_group)

        update_status(job_id, "navigating", 1, 10)

        # ── Step 3: NavigationLoop 실행 ──
        loop = NavigationLoop(
            url=target_url,
            task=task,
            persona=persona,
            success_condition=success_condition,
            status_callback=lambda step, count, max_: update_status(job_id, step, count, max_)
        )
        result = loop.run()

        update_status(job_id, "uploading", 9, 10)

        # ── Step 4: S3 업로드 ──
        # TODO: 실제 S3 업로드 로직 연결 (boto3)
        s3_urls = _upload_to_s3(result, s3_prefix)

        update_status(job_id, "completed", 10, 10)

        return {
            "status": "completed",
            "age_group": age_group,
            "s3_urls": s3_urls
        }

    except Exception as e:
        update_status(job_id, "failed", 0, 0)
        return {
            "status": "failed",
            "age_group": age_group,
            "error": str(e)
        }


# ────────────────────────────────────────────
# S3 업로드 헬퍼 (플레이스홀더)
# 알고리즘 수정 완료 후 실제 구현 예정
# ────────────────────────────────────────────
def _upload_to_s3(result: dict, s3_prefix: str) -> dict:
    """
    시뮬레이션 결과를 S3에 업로드하고 URL 반환

    Args:
        result: NavigationLoop 실행 결과
        s3_prefix: S3 저장 경로 prefix

    Returns:
        5개 파일의 S3 URL dict
    """
    bucket = os.getenv("S3_BUCKET", "ux-swarm-bucket")

    # TODO: 실제 boto3 업로드 로직으로 교체
    return {
        "final_issues": f"s3://{bucket}/{s3_prefix}/final_issues.json",
        "heatmap_aggregation": f"s3://{bucket}/{s3_prefix}/heatmap_aggregation.json",
        "summary_aggregation": f"s3://{bucket}/{s3_prefix}/summary_aggregation.json",
        "wcag": f"s3://{bucket}/{s3_prefix}/wcag.json",
        "fixes": f"s3://{bucket}/{s3_prefix}/fixes/{{encoded_url}}/fix.json",
    }