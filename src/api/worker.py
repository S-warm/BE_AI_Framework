"""
Celery 태스크 정의 파일이야. 시뮬레이션 1개를 비동기로 실행하는 단위 작업

run_simulation = 페르소나 1개짜리 시뮬레이션 1회. routes.py에서 age_count만큼 이걸 반복 호출
update_status = Redis에 진행 상태 저장. Spring이 폴링할 때 이 값 읽음
_upload_to_s3 = 지금은 URL만 생성하는 플레이스홀더. S3 수정할 때 boto3로 교체
"""

import os
import uuid
import json
import redis as redis_lib
from celery import Celery
from pathlib import Path

celery_app = Celery(
    "ux_swarm",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)

DB_PATH = "/app/cache/test_cache.db"


def get_redis():
    return redis_lib.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


def update_status(job_id: str, completed: int, total: int, failed: int):
    r = get_redis()
    r.set(f"status:{job_id}", f"{completed}|{total}|{failed}", ex=3600)


def _trigger_step_functions(session_dir: str):
    """테스트 코드 trigger_step_functions_after_all fixture와 동일한 로직"""
    import boto3
    client = boto3.client('stepfunctions', region_name='ap-northeast-2')
    client.start_execution(
        stateMachineArn='arn:aws:states:ap-northeast-2:195765661361:stateMachine:swarm-auditor-pipeline',
        input=json.dumps({"prefix": f"raw/{session_dir}"})
    )
    print(f"[STEP_FUNCTIONS] 트리거: raw/{session_dir}")


@celery_app.task(bind=True)
def run_simulation(self, job_id: str, target_url: str, task: str,
                   age_group: str, success_condition: dict, title: str,
                   session_dir: str, total: int):

    from playwright.sync_api import sync_playwright
    from AI.navigation_AI.navigation_loop.navigation_loop import NavigationLoop
    from AI.layer_tier2.base_persona import BasePersona
    from AI.Auditor_AI.utils.s3_uploader import S3Uploader
    from normalizer.mcp.web_normalizer.web_normalizer_incremental.web_normalizer_incremental import WebNormalizerIncremental
    from engine.navigator_ai import NavigatorAI
    from AI.navigation_AI.navigation_loop.navigator_guide import NavigatorGuide

    # 경로 구성 (테스트 코드 test_real_navigation과 동일)
    persona_dir = Path(session_dir) / age_group
    sim_id = uuid.uuid4().hex[:6]
    log_dir = str(persona_dir / f"sim_{sim_id}")

    sim_status = "failed"

    try:
        # 의존성 생성 (테스트 코드 fixture들과 동일)
        navigator_ai = NavigatorAI(log_dir=log_dir)
        uploader = S3Uploader(bucket_name=os.getenv("S3_BUCKET"))
        persona = BasePersona(age_group)

        with sync_playwright() as p:
            # 브라우저 창
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                ]
            )
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            page.on("console", lambda msg: print(f"[JS] {msg.text}"))
            page.on("dialog", lambda d: (print(f"[DIALOG] {d.message}"), d.accept()))

            # 1. guide 먼저
            guide = NavigatorGuide(
                page=page,
                navigator_ai=navigator_ai,
                db_path=DB_PATH,
                uploader=uploader,
            )
            date_prefix = session_dir
            guide.run(goal=task, url=target_url, success_condition=success_condition, session_dir=session_dir, date_prefix=date_prefix)
            
            # guide 끝났으니 log_dir을 sim 폴더로 복구
            page.goto(target_url, wait_until='domcontentloaded', timeout=60000)
            navigator_ai.set_log_dir(log_dir)

            # 2. loop 그 다음 (page.goto 없이)
            loop = NavigationLoop(
                page=page,
                normalizer=guide.normalizer,  # ← 변경
                navigator_ai=navigator_ai,
                db_path=DB_PATH,
                log_dir=log_dir,
                session_dir=session_dir,
                uploader=uploader,
            )
            loop.max_steps = 100
            result = loop.run(task, persona, success_condition)

            page.close()
            context.close()
            browser.close()

        s3_urls = _upload_to_s3(result, log_dir)
        sim_status = "completed"

    except Exception as e:
        print(f"[ERROR] {age_group} {sim_id}: {e}")
        s3_urls = {}

    finally:
        # Redis atomic increment로 completed/failed 갱신
        r = get_redis()
        if sim_status == "completed":
            new_completed = r.hincrby(f"counter:{job_id}", "completed", 1)
            new_failed = int(r.hget(f"counter:{job_id}", "failed") or 0)
        else:
            new_failed = r.hincrby(f"counter:{job_id}", "failed", 1)
            new_completed = int(r.hget(f"counter:{job_id}", "completed") or 0)

        r.expire(f"counter:{job_id}", 3600)
        update_status(job_id, new_completed, total, new_failed)

        # 마지막 태스크면 Step Functions 트리거 (autouse fixture와 동일)
        if new_completed + new_failed >= total:
            _trigger_step_functions(session_dir)

    return {"status": sim_status, "age_group": age_group, "s3_urls": s3_urls}


def _upload_to_s3(result: dict, log_dir: str) -> dict:
    bucket = os.getenv("S3_BUCKET", "ux-swarm-bucket")
    s3_prefix = f"raw/{log_dir}"

    # TODO: boto3 실제 업로드로 교체
    return {
        "final_issues": f"s3://{bucket}/{s3_prefix}/final_issues.json",
        "heatmap_aggregation": f"s3://{bucket}/{s3_prefix}/heatmap_aggregation.json",
        "summary_aggregation": f"s3://{bucket}/{s3_prefix}/summary_aggregation.json",
        "wcag": f"s3://{bucket}/{s3_prefix}/wcag.json",
        "fixes": f"s3://{bucket}/{s3_prefix}/fixes/fix.json",
    }