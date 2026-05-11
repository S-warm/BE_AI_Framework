#src/AI/navigation_AI/utils/navigation_memory.py

"""
Action Log Implementation
행동 기록 관리 시스템
navigation AI가 내가 지금까지 뭐했지? 기억하게 해서 다음 행동을 판단할수 있세 도와줌
ex) 재시도 판단, 목표 진행 상황 파악, 무한루프 방지

working memory 요소도 포함되어 있음

책임:
1. 전체 사용자 목표 저장
2. 모든 행동 기록 (click, fill, hover 등)
3. 최근 N개 반환 (프롬프트용, 토큰 제한)
"""

from typing import List, Dict
from datetime import datetime


class NavigationMemory:
    """
    행동 기록 및 진행 상황 관리
    
    사용 시점:
    - Navigator가 행동 실행할 때마다 add_action() 호출
    - 프롬프트 생성 시 get_recent(10) 호출
    - 시뮬레이션 완료 후 get_all_actions() 로깅
    """
    
    def __init__(self, user_goal: str):
        """
        초기화
        
        Args:
            user_goal: 전체 목표 (예: "회원가입하고 로그인")
        
        Example:
            action_log = ActionLog("회원가입하고 로그인")
        """
        self.user_goal = user_goal
        self.actions: List[Dict] = []
    
    def add_action(self, action: str, element_id: str, 
            element_text: str, result: str, error: str = None) -> None:
        """
        행동 추가
        
        Args:
            action: 행동 타입 ("click", "fill", "hover")
            element_id: 요소 ID ("elem30")
            element_text: 요소 텍스트 ("회원가입")
            result: 결과 ("success", "page_changed", "modal_opened", "failed")
        
        Example:
            action_log.add_action("click", "elem30", "회원가입", "page_changed")
        """
        self.actions.append({
            "step": len(self.actions) + 1,
            "action": action,
            "element_id": element_id,
            "element_text": element_text,
            "result": result,
            "error": error,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_recent(self, n: int = 7) -> List[Dict]:
        """
        최근 N개 행동 반환 (프롬프트용, 토큰 제한)
        
        Working Memory 개념:
        - 기본값 7 (Miller's Law: 7±2)
        - Persona별로 다르게 설정 가능:
        * 20대 high: 9개 (7+2)
        * 50대 medium: 7개 (기본)
        * 70대 low: 5개 (7-2)
        
        Args:
            n: 최근 몇 개 (기본 7개)
        
        Returns:
            최근 N개 행동 리스트 (빈 리스트 가능)
        
        Example:
            # 기본값 사용
            recent = action_log.get_recent()  # 최근 7개
            
            # Persona별 오버라이딩 (Tier 2에서)
            if persona.age_group == "20s":
                recent = action_log.get_recent(9)
            elif persona.age_group == "70s":
                recent = action_log.get_recent(5)
        """
        return self.actions[-n:] if self.actions else []
    
    def get_summary(self) -> str:
        """
        전체 진행 요약
        
        Returns:
            진행 상황 문자열
        
        Example:
            >>> action_log.get_summary()
            "총 45개 행동, 마지막: 회원가입 click"
            
            >>> # 행동 없으면
            >>> action_log.get_summary()
            "아직 아무 행동 안 함"
        """
        if not self.actions:
            return "아직 아무 행동 안 함"
        
        last = self.actions[-1]
        return f"총 {len(self.actions)}개 행동, 마지막: {last['element_text']} {last['action']}"
    
    def get_all_actions(self) -> List[Dict]:
        """
        전체 행동 기록 (로깅/분석용)
        
        Returns:
            전체 행동 리스트
        
        Example:
            # 시뮬레이션 완료 후
            all_actions = action_log.get_all_actions()
            simulation_logger.save(all_actions)  # 로깅 시스템으로
        """
        return self.actions
    
    #====================================================== 유틸함수 =========================================================
    
    def __len__(self) -> int:
        """
        len(navigation_memory) 지원
        
        Returns:
            전체 행동 개수
        
        Example:
            >>> len(navigation_memory)
            45
            >>> if len(navigation_memory) > 100:
            ...     print("행동 많음")
        """
        return len(self.actions)
    
    def __repr__(self) -> str:
        """
        print(navigation_memory) 예쁘게 출력
        
        Returns:
            읽기 쉬운 문자열
        
        Example:
            >>> print(navigation_memory)
            NavigationMemory(goal='회원가입하고 로그인', actions=45)
        """
        return (f"NavigationMemory(goal='{self.user_goal}', "
                f"actions={len(self.actions)})")