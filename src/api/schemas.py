"""
Request/Response 데이터 구조 정의하는 파일이야. Spring DTO랑 매핑되는 Python 버전

SimulationRequest = Spring DTO를 Python으로 그대로 옮긴 것. 미구현 필드는 Optional로 받되 무시.
SuccessCondition = 담당자한테 수정 요청한 구조화 형식.
SimulationStatusResponse = 폴링용. step, step_count로 프론트에 진행 상황 표시.
S3Results = 5개 파일 URL 묶음.
"""



from pydantic import BaseModel, Field
from typing import Optional


# ────────────────────────────────────────────
# Request 모델 (Spring → Python)
# ────────────────────────────────────────────
 
class SuccessCondition(BaseModel):
    """
    AI가 시뮬레이션 성공 여부를 판단하는 기준
    Spring DTO의 SuccessCondition inner class와 동일한 구조
    """
    path: str = Field(..., example="/journal/articleDetail")
    required_params: Optional[dict] = Field(default=None, example={"nodeId": "NODE12728926"})
 
 
class SimulationRequest(BaseModel):
    """
    Spring → Python 시뮬레이션 요청
    Spring의 SimulationCreateRequest DTO와 매핑됨
    """
 
    # 프로젝트 제목 (S3 경로에 slug 변환해서 사용)
    title: str = Field(..., example="Q1 2026 체크아웃 플로우 UX 테스트")
 
    # 테스트 대상 URL
    target_url: str = Field(..., example="https://shopping-mall.com/checkout")
    
    # AI에게 줄 자연어 지시
    task: str = Field(..., example="검색창에 파운데이션 모델 검색하고 게시글 클릭해줘")
 
    # 성공 조건 (Python 코드로 검증)
    success_condition: SuccessCondition
 
    # 연령대별 페르소나 수 (합산해서 Celery 작업 분배)
    age_count_10: int = Field(default=0, ge=0)
    age_count_20: int = Field(default=0, ge=0)
    age_count_30: int = Field(default=0, ge=0)
    age_count_40: int = Field(default=0, ge=0)
    age_count_50: int = Field(default=0, ge=0)
    age_count_60: int = Field(default=0, ge=0)
    age_count_70: int = Field(default=0, ge=0)
 
    # 아래 3개는 이번 캡스톤 미구현 → 받되 무시
    digital_literacy: Optional[str] = None
    persona_device: Optional[str] = None
    vision_impairment: Optional[int] = None
    attention_level: Optional[int] = None
 
 
# ────────────────────────────────────────────
# Response 모델 (Python → Spring)
# ────────────────────────────────────────────
 
class SimulationStartResponse(BaseModel):
    """
    /simulate POST 응답
    job_id만 즉시 반환 (비동기 처리 시작)
    """
    job_id: str = Field(..., example="abc-123-xyz")
 
 
class SimulationStatusResponse(BaseModel):
    """
    /status/{job_id} GET 응답
    Spring 프론트에서 폴링으로 진행 상황 표시
    페르소나 1개 완료마다 갱신됨
    """
    job_id: str
    status: str = Field(..., example="running")  # pending | running | completed | failed
    completed: int = Field(default=0, example=30)   # 완료된 페르소나 수
    total: int = Field(default=0, example=100)       # 전체 페르소나 수
    failed: int = Field(default=0, example=2)        # 실패한 페르소나 수
 
 
class S3Results(BaseModel):
    """
    시뮬레이션 완료 후 S3에 저장된 결과 파일 URL 모음
    """
    final_issues: str
    heatmap_aggregation: str
    summary_aggregation: str
    wcag: str
    fixes: str  # fixes/{encoded_url}/fix.json 경로
    screenshots: str
 
 
class SimulationResultResponse(BaseModel):
    """
    /result/{job_id} GET 응답
    완료된 시뮬레이션의 S3 결과 URL 반환
    """
    job_id: str
    status: str  # completed | failed
    results: Optional[S3Results] = None  # failed면 None