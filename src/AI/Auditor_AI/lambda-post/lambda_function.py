import json
import os
import boto3
from datetime import datetime, timezone

s3 = boto3.client('s3')
BUCKET = os.environ.get('S3_BUCKET')


def lambda_handler(event, context):
    job_id = event.get('job_id')
    date_prefix = event.get('date_prefix')
    title_slug = event.get('title_slug')
    
    if not job_id:
        print(f"[Lambda8] job_id 없음 - event: {event}")
        return {'status': 'error', 'reason': 'no job_id'}
    
    base = f"raw/{title_slug}/logs/{date_prefix}/analyzed"
    
    done_payload = {
        "job_id": job_id,
        "date_prefix": date_prefix,
        "title_slug": title_slug,
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "results": {
            "overview":      f"s3://{BUCKET}/{base}/summary_aggregation.json",
            "issues":        f"s3://{BUCKET}/{base}/final_issues.json",
            "heatmap":       f"s3://{BUCKET}/{base}/heatmap_aggregation.json",
            "wcag":          f"s3://{BUCKET}/{base}/wcag.json",
            "fixes_prefix":  f"s3://{BUCKET}/{base}/fixes/"
        }
    }
    
    done_key = f"done/{job_id}.json"
    s3.put_object(
        Bucket=BUCKET,
        Key=done_key,
        Body=json.dumps(done_payload, ensure_ascii=False, indent=2),
        ContentType='application/json',
    )
    
    print(f"[Lambda8] done.json 업로드: s3://{BUCKET}/{done_key}")
    return {'status': 'ok', 'done_key': done_key}