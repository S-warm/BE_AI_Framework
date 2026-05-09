import json
import boto3
import os
import re

s3 = boto3.client('s3')
BUCKET = BUCKET = os.environ.get('S3_BUCKET')

# 지원 페르소나 연령대
AGE_MAP = {10: '10s', 20: '20s', 30: '30s', 40: '40s', 50: '50s', 60: '60s', 70: '70s'}

def lambda_handler(event, context):
    # Step Functions에서 넘어온 S3 prefix (기본값: 'raw/logs/')
    prefix = event.get('prefix', 'raw/logs/')
    
    # S3에서 AI-sess_ 파일 목록 조회
    response = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
    files = [obj['Key'] for obj in response.get('Contents', []) 
    if 'AI-sess_' in obj['Key'] 
    and '/guide/' not in obj['Key']
    and '/structured/' not in obj['Key']]
    
    # persona_age별 그룹 초기화
    groups = {age: [] for age in AGE_MAP.values()}
    
    for key in files:
        # 각 세션 파일 읽기
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        data = json.loads(obj['Body'].read())
        
        # persona_age 숫자 → 문자열 변환 후 그루핑
        age = AGE_MAP.get(data.get('persona_age'))
        if age:
            groups[age].append(key)
            
    date_prefix = re.search(r'raw/logs/([^/]+)/', files[0]).group(1)
    
    # Step Functions Map으로 전달할 그룹 반환
    return {
        "date_prefix": date_prefix,
        "age_list": [age for age, sessions in groups.items() if sessions],
        "persona_groups": [
            {"age": age, "sessions": sessions}
            for age, sessions in groups.items()
            if sessions
        ]
    }