# s3_uploader.py

import boto3 # WS 공식 Python SDK야. S3, Lambda, EC2 등 AWS 서비스를 Python 코드로 제어할 수 있게 해줌
import os
from pathlib import Path


class S3Uploader:
    def __init__(self, bucket_name: str, region: str = "ap-northeast-2"):
        self.bucket_name = bucket_name
        self.client = boto3.client("s3", region_name=region)

    def upload_session_logs(self, s3_prefix, logs_dir: Path) -> bool:
        # logs/ 폴더 자체가 없으면 조기 종료
        if not logs_dir.exists():
            print(f"[S3] logs 폴더 없음: {logs_dir}")
            return False

        # logs/ 하위 모든 파일 수집 (폴더 제외)
        files = list(logs_dir.glob("**/*"))
        files = [f for f in files if f.is_file()]

        success = True
        for local_path in files:
            # logs_dir 기준 상대경로 유지
            relative_path = local_path.relative_to(logs_dir)
            s3_key = f"{s3_prefix}/{relative_path}"
            if not self._upload_file_with_retry(local_path, s3_key):
                print(f"[S3] 최종 업로드 실패: {local_path.name}")
                success = False

        return s3_prefix if success else None  # 전체 성공 여부 반환

    def _upload_file_with_retry(self, local_path: Path, s3_key: str, max_retry: int = 3) -> bool:
        for attempt in range(max_retry):  # 0, 1, 2 — 최대 3번 시도
            try:
                self.client.upload_file(str(local_path), self.bucket_name, s3_key)
                # 로컬 파일 경로, 버킷 이름, S3 저장 경로 순서로 전달
                return True  # 성공하면 즉시 True 반환
            except Exception as e:
                print(f"[S3 업로드 실패] {s3_key} ({attempt+1}/{max_retry}): {e}")
                # 실패하면 로그 남기고 다음 시도로 넘어감
        return False  # 3번 다 실패하면 False 반환
    
    def upload_file(self, local_path: str, s3_key: str) -> bool:
        return self._upload_file_with_retry(Path(local_path), s3_key)