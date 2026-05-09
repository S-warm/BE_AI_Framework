#src/AI/navigation_AI/utils/page_history.py

"""
Page History Implementation
페이지 전환 히스토리 관리

여기도 working memory 개념 들어감 나중에 오버라이딩 해야함 tier2 페르소나 별로 다르게

책임:
1. 페이지 전환 기록 (섹션 요약 포함)
2. 최근 N개 페이지만 반환 (토큰 제한)
3. 키워드로 페이지 검색 (뒤로가기용)
"""

from typing import List, Dict, Optional
from datetime import datetime


class PageHistory:
    """
    페이지 전환 히스토리 관리
    
    특징:
    - Working/Long-term 구분 없음 (v3에서 제거됨)
    - 모든 페이지 동일하게 취급
    - 최근 N개만 프롬프트에 포함 (토큰 절약)
    
    사용 시점:
    - 페이지 전환 시 add_page() 호출
    - 프롬프트 생성 시 get_history_summary() 호출
    - 뒤로가기 필요 시 find_page_by_keyword() 호출
    """
    
    def __init__(self):
        """
        초기화
        
        Example:
            page_history = PageHistory()
        """
        self.pages: List[Dict] = []
    
    def add_page(self, url: str, summary: str, action: str) -> None:
        """
        페이지 추가
        
        Args:
            url: 페이지 URL
            summary: 페이지 요약 (섹션별 주요 내용 포함)
            action: 이 페이지로 온 방법 (예: "elem30 '회원가입' 클릭")
        
        Example:
            page_history.add_page(
                url="https://naver.com/signup",
                summary="네이버 회원가입\n- header: 로고만\n- main: 입력 폼 4개",
                action="elem30 '회원가입' 클릭"
            )
        """
        self.pages.append({
            "url": url,
            "summary": summary,
            "action": action,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_history_summary(self, max_pages: int = 7) -> str:
        """
        최근 N개 페이지 요약 (프롬프트용, 토큰 제한)
        
        Working Memory 개념:
        - 기본값 7 (Miller's Law: 7±2)
        - Persona별로 다르게 설정 가능:
        * 20대 high: 9개 (7+2)
        * 50대 medium: 7개 (기본)
        * 70대 low: 5개 (7-2)
        
        Args:
            max_pages: 최대 페이지 수 (기본 7개)
        
        Returns:
            페이지 히스토리 문자열 (빈 문자열 가능)
        
        Example:
            >>> page_history.get_history_summary()
            '''
            1. 네이버 메인 - header: 로고, 검색창 | main: 뉴스 5개
            (방법: 직접 접속)
            2. 회원가입 페이지 - main: 입력 폼 4개
            (방법: elem30 '회원가입' 클릭)
            '''
        """
        recent = self.pages[-max_pages:] if len(self.pages) > max_pages else self.pages
        
        if not recent:
            return ""
        
        lines = []
        for i, page in enumerate(recent, 1):
            lines.append(f"{i}. {page['summary']}")
            lines.append(f"   (방법: {page['action']})")
        
        return "\n".join(lines)
    
    def find_page_by_keyword(self, keyword: str) -> Optional[Dict]:
        """
        키워드로 페이지 검색 (뒤로가기용)
        
        Args:
            keyword: 검색 키워드 (예: "로그인", "메인")
        
        Returns:
            매칭되는 페이지 (가장 최근) 또는 None
        
        Example:
            # "로그인"이 summary에 포함된 페이지 찾기
            page = page_history.find_page_by_keyword("로그인")
            if page:
                browser.navigate(page["url"])  # 뒤로가기
        """
        for page in reversed(self.pages):
            if keyword.lower() in page["summary"].lower():
                return page
        return None
    
    def get_current_page(self) -> Optional[Dict]:
        """
        현재 페이지 (가장 최근 추가된 페이지)
        
        Returns:
            현재 페이지 dict 또는 None (페이지 없으면)
        
        Example:
            >>> current = page_history.get_current_page()
            >>> print(current["url"])
            "https://naver.com/signup"
        """
        return self.pages[-1] if self.pages else None
    
    def get_page_count(self) -> int:
        """
        전체 페이지 수
        
        Returns:
            방문한 페이지 개수
        
        Example:
            >>> page_history.get_page_count()
            5
        """
        return len(self.pages)
    
    def get_all_urls(self) -> List[str]:
        """방문한 모든 URL 반환"""
        return [page['url'] for page in self.pages]
    
    #====================================================== 유틸함수 =========================================================
    
    def __len__(self) -> int:
        """
        len(page_history) 지원
        
        Returns:
            전체 페이지 수
        
        Example:
            >>> len(page_history)
            5
            >>> if len(page_history) > 10:
            ...     print("페이지 많이 방문함")
        """
        return len(self.pages)
    
    def __repr__(self) -> str:
        """
        print(page_history) 예쁘게 출력
        
        Returns:
            읽기 쉬운 문자열
        
        Example:
            >>> print(page_history)
            PageHistory(pages=5, current='https://naver.com/signup')
        """
        current_url = self.pages[-1]["url"] if self.pages else "None"
        return f"PageHistory(pages={len(self.pages)}, current='{current_url}')"