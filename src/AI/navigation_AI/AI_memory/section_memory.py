#src/AI/navigation_AI/utils/section_memory.py

"""
Section Memory Implementation
섹션별 탐색 결과 관리 + URL별 캐싱

책임:
1. 현재 페이지 섹션 탐색 결과 저장
2. URL별 섹션 캐싱 (재방문 시 스킵)
3. 이전 섹션들 요약 반환 (프롬프트용)
"""

from typing import Dict, List, Optional


class SectionMemory:
    """
    섹션별 탐색 결과 + URL별 캐싱
    
    isuue point
    * ai가 만약 틀려서 뒷페이지로 이동시 뒷페이지 내용들이 캐시에 url별로 저장이 되어있음
    지금은 섹션 별로 요약해서 hash에 넣었지만 만약 ai가 실수를 한 경우 이미 섹션을 확인한 페이지에선 같은 실수를 반복함 왜냐 이미 본 섹션은 지나칠테니
    두번째 문제는 우리는 섹션 안에 요소별로 또 티어를 나누어 루프를 돔 지금은 본 섹션은 넘어가게 설계 했지만 모든 요소를 본게 아니면 어차피 섹션 다시 돔
    
    특징:
    - URL별로 섹션 결과 저장 (재방문 대응)
    - 현재 페이지만 프롬프트에 포함
    - Confidence Score 없음 (v3에서 제거)
    
    사용 시점:
    - 페이지 전환 시 set_current_url() 호출
    - 섹션 탐색 완료 시 save_section_result() 호출
    - 프롬프트 생성 시 get_previous_summaries() 호출
    """
    
    def __init__(self):
        """
        초기화
        
        Example:
            section_memory = SectionMemory()
        """
        self.section_cache: Dict[str, Dict[str, Dict]] = {}
        # {
        #     "https://naver.com": {
        #         "header": {"summary": "...", "found_target": False, "ux_issues": [...]},
        #         "main": {...}
        #     },
        #     "https://naver.com/signup": {...}
        # }
        
        self.current_url: str = ""
    
    def set_current_url(self, url: str) -> None:
        """
        현재 페이지 URL 설정
        
        페이지 전환 시 호출:
        - Navigator가 새 페이지 들어갈 때
        - 캐시에 해당 URL 없으면 자동 생성
        
        Args:
            url: 현재 페이지 URL
        
        Example:
            # 페이지 전환 시
            section_memory.set_current_url("https://naver.com/signup")
        """
        self.current_url = url
        
        # 캐시에 없는 URL이면 빈 dict 생성
        if url not in self.section_cache:
            self.section_cache[url] = {}
    
    def save_section_result(
        self, 
        section: str, 
        summary: str, 
        found_target: bool, 
        ux_issues: List[str],
        explored_tiers: List[str],
        visited_elements: List[str]
    ) -> None:
        """
        섹션 탐색 결과 저장 (현재 URL에)
        
        Args:
            section: 섹션 이름 ("header", "main", "nav", "footer")
            summary: 섹션 한 줄 요약 (다음 섹션 참고용)
            found_target: 목표 요소를 찾았는지 여부
            ux_issues: UX 문제 리스트 (요약)
            explored_tiers: 탐색한 tier 목록 (["상"] or ["상", "중"] or ["상", "중", "하"])
            visited_elements: 본 요소 ID 목록 (["elem10", "elem11", "elem12"])
        
        Example:
            # 상 tier만 보고 피로도로 중단
            section_memory.save_section_result(
                section="header",
                summary="로고만 봄. 로그인 버튼 못 찾음",
                found_target=False,
                ux_issues=["elem30: 폰트 12px"],
                explored_tiers=["상"],
                visited_elements=["elem10", "elem11", "elem12"]
            )
            
            # 재방문 시 중 tier부터 탐색 재개 가능
        """
        if not self.current_url:
            return
        
        self.section_cache[self.current_url][section] = {
            "summary": summary,
            "found_target": found_target,
            "ux_issues": ux_issues,
            "explored_tiers": explored_tiers,
            "visited_elements": visited_elements
        }
        
    def has_visited(self, section: str) -> bool:
        """
        섹션 방문 여부 (부분 탐색 포함)
        
        Args:
            section: 섹션 이름
        
        Returns:
            True: 한 번이라도 방문함 (상 tier만 봐도 True)
            False: 아직 한 번도 안 봄
        
        Example:
            if section_memory.has_visited("header"):
                # 이전에 봤음 (어느 tier까지인지는 별도 확인)
                tiers = section_memory.get_explored_tiers("header")
        """
        if not self.current_url:
            return False
        
        return (self.current_url in self.section_cache and 
                section in self.section_cache[self.current_url])
        
    def is_fully_explored(self, section: str) -> bool:
        """
        섹션 완전 탐색 여부 (모든 tier 탐색 완료)
        
        Args:
            section: 섹션 이름
        
        Returns:
            True: 상, 중, 하 tier 모두 탐색 완료
            False: 아직 안 본 tier가 남음
        
        Example:
            if section_memory.is_fully_explored("header"):
                print("header 완전 탐색됨. 스킵")
            else:
                tiers = section_memory.get_explored_tiers("header")
                if "중" not in tiers:
                    # 중 tier부터 재개
        """
        if not self.has_visited(section):
            return False
        
        explored = self.get_explored_tiers(section)
        return "상" in explored and "중" in explored and "하" in explored
        
    def get_explored_tiers(self, section: str) -> List[str]:
        """
        이 섹션에서 이미 탐색한 tier 목록
        
        Args:
            section: 섹션 이름
        
        Returns:
            탐색한 tier 리스트 (빈 리스트 = 미방문)
        
        Example:
            >>> tiers = section_memory.get_explored_tiers("header")
            >>> print(tiers)
            ["상"]
            
            >>> if "중" not in tiers:
            ...     # 중 tier부터 탐색 재개
        """
        if not self.current_url:
            return []
        
        if (self.current_url not in self.section_cache or 
            section not in self.section_cache[self.current_url]):
            return []
        
        return self.section_cache[self.current_url][section]["explored_tiers"]
    
    def get_visited_elements(self, section: str) -> List[str]:
        """
        이 섹션에서 이미 본 요소 ID 목록
        
        Args:
            section: 섹션 이름
        
        Returns:
            본 요소 ID 리스트 (빈 리스트 = 미방문)
        
        Example:
            >>> elements = section_memory.get_visited_elements("header")
            >>> print(elements)
            ["elem10", "elem11", "elem12"]
            
            >>> if "elem15" not in elements:
            ...     # elem15는 안 봤으니 탐색
        """
        if not self.current_url:
            return []
        
        if (self.current_url not in self.section_cache or 
            section not in self.section_cache[self.current_url]):
            return []
        
        return self.section_cache[self.current_url][section]["visited_elements"]
    
    def get_previous_summaries(self) -> str:
        """
        이전 섹션들 요약 (현재 URL만, 프롬프트용)
        
        Returns:
            섹션 요약 문자열 (빈 문자열 = 아직 탐색 안 함)
        
        Example:
            >>> section_memory.get_previous_summaries()
            '''
            - header: 로고만 봄. 로그인 버튼 없음 (상 tier 탐색)
            ⚠️ UX: elem30: 폰트 12px
            - nav: 메뉴 3개. 관련 없음 (상, 중 tier 탐색)
            '''
        """
        if not self.current_url:
            return ""
        
        if self.current_url not in self.section_cache:
            return ""
        
        sections = self.section_cache[self.current_url]
        
        if not sections:
            return ""
        
        lines = []
        for section, data in sections.items():
            # 기본 요약
            tier_info = ", ".join(data["explored_tiers"])
            line = f"- {section}: {data['summary']} ({tier_info} tier 탐색)"
            lines.append(line)
            
            # UX 문제 (있으면)
            if data["ux_issues"]:
                for issue in data["ux_issues"]:
                    lines.append(f"  ⚠️ UX: {issue}")
        
        return "\n".join(lines)
    
    def get_section_count(self) -> int:
        """
        방문한 섹션 수 (현재 URL 기준)
        
        Returns:
            섹션 개수 (0 = 아직 탐색 안 함)
        
        Example:
            >>> section_memory.get_section_count()
            2  # header, main 탐색 완료
        """
        if not self.current_url:
            return 0
        
        if self.current_url not in self.section_cache:
            return 0
        
        return len(self.section_cache[self.current_url])
    
    #====================================================== 유틸함수 =========================================================
    
    def __len__(self) -> int:
        """
        len(section_memory) 지원
        
        Returns:
            현재 URL의 방문한 섹션 수
        
        Example:
            >>> len(section_memory)
            2
            >>> if len(section_memory) > 3:
            ...     print("섹션 많이 탐색함")
        """
        return self.get_section_count()
    
    def __repr__(self) -> str:
        """
        print(section_memory) 예쁘게 출력
        
        Returns:
            읽기 쉬운 문자열
        
        Example:
            >>> print(section_memory)
            SectionMemory(url='https://naver.com/signup', sections=2)
        """
        return (f"SectionMemory(url='{self.current_url}', "
                f"sections={self.get_section_count()})")