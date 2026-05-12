"""
WCAGChecker - axe-core 기반 WCAG 2.1 AA 접근성 검사

사용:
    checker = WCAGChecker(page=page, uploader=uploader, navigator_ai=navigator_ai)
    checker.run(urls=["https://example.com/"], date_prefix="2026-05-03_23-10-12")
"""

import json
import uuid
from typing import List, Dict, Optional
from pathlib import Path
from playwright.sync_api import Page

from AI.Auditor_AI.utils.s3_uploader import S3Uploader

AXE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.0/axe.min.js"

# axe-core impact → 우리 severity 매핑
# axe-core는 "serious"도 있는데 우리는 critical로 통일
IMPACT_MAP = {
    "critical": "Critical",
    "serious": "Critical",
    "moderate": "Moderate",
    "minor": "Minor",
}


def _calc_wcag_label(score: int) -> str:
    """
    점수 기반 WCAG 레벨 분류
    - AAA: 95% 이상 (거의 완벽)
    - AA:  70% 이상 (일반 기준)
    - A:   50% 이상 (기본 수준)
    - 미달: 50% 미만
    """
    if score >= 95:
        return "AAA"
    elif score >= 70:
        return "AA"
    elif score >= 50:
        return "A"
    else:
        return "미달"


class WCAGChecker:

    def __init__(
        self,
        page: Page,
        uploader: Optional[S3Uploader] = None,
        navigator_ai=None,  # OpenAI 클라이언트 (GPT-4o 번역용)
    ):
        self.page = page
        self.uploader = uploader
        self.navigator_ai = navigator_ai  # description 한국어 번역에 사용

    def run(self, urls: List[str], date_prefix: str) -> Dict:
        """
        URL 목록 순회 → axe-core 검사 → S3 저장

        Args:
            urls: 검사할 URL 목록 (가이드 AI pages[*].url)
            date_prefix: S3 경로용 날짜 prefix

        Returns:
            wcag 결과 dict (URL별 구조)
        """
        result = {"urls": {}}

        for url in urls:
            print(f"[WCAG] 검사 중: {url}")
            try:
                url_result = self._check_url(url)
                result["urls"][url] = url_result
            except Exception as e:
                print(f"[WCAG] 실패: {url} → {e}")
                result["urls"][url] = {
                    "score": 0,
                    "wcagLabel": "미달",
                    "distribution": {"Critical": 0, "Moderate": 0, "Minor": 0},
                    "violations": [],
                    "error": str(e)
                }

        self._save(result, date_prefix)
        return result

    def _check_url(self, url: str) -> Dict:
        """
        단일 URL axe-core 검사

        흐름:
        1. URL 로드
        2. axe-core CDN 스크립트 주입
        3. axe.run() 실행 → violations, passes 반환
        4. violations 파싱 (GPT-4o 번역 포함)
        5. score, wcagLabel, distribution 계산
        """
        self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
        self.page.wait_for_timeout(2000)  # 동적 콘텐츠 렌더 대기

        # CSP가 엄격한 사이트는 여기서 막힐 수 있음
        # axe-core 스크립트 주입 (CDN)
        self.page.add_script_tag(url=AXE_CDN)
        self.page.wait_for_timeout(1000)

        # axe.run() 실행 - WCAG 2.1 A/AA 기준으로만 검사
        axe_result = self.page.evaluate("""
            async () => {
                return await axe.run(document, {
                    runOnly: {
                        type: 'tag',
                        values: ['wcag2a', 'wcag2aa']
                    }
                });
            }
        """)

        # violations 파싱 (GPT-4o 번역 포함)
        violations = self._parse_violations(axe_result.get("violations", []))

        # score 계산: 통과 규칙 / 전체 규칙 * 100
        passes = len(axe_result.get("passes", []))
        total = passes + len(violations)
        score = round((passes / total) * 100) if total > 0 else 100

        # distribution 집계
        distribution = {"Critical": 0, "Moderate": 0, "Minor": 0}
        for v in violations:
            severity = v.get("severity", "Minor")
            if severity in distribution:
                distribution[severity] += 1

        return {
            "score": score,
            "wcagLabel": _calc_wcag_label(score),
            "distribution": distribution,
            "violations": violations,
        }

    def _parse_violations(self, raw: List[Dict]) -> List[Dict]:
        """
        axe-core violations → 우리 포맷으로 변환

        각 violation에서:
        - impact: severity로 변환 (IMPACT_MAP)
        - nodes[0].html: 실제 위반된 DOM 요소
        - help: GPT-4o로 한국어 번역 → description
        - tags: wcag 기준 번호 추출
        - uuid: 동적 생성
        """
        result = []
        for v in raw:
            severity = IMPACT_MAP.get(v.get("impact", "minor"), "Minor")
            print(f"[TAGS] {v.get('tags')}")

            # 위반된 DOM 요소 (첫 번째 노드만)
            html = ""
            if v.get("nodes"):
                html = v["nodes"][0].get("html", "")

            # wcag 기준 번호 추출
            wcag_criteria = self._extract_wcag_criteria(v.get("tags", []))

            # GPT-4o로 한국어 description 생성
            help_text = v.get("help", "")
            description = self._translate_description(help_text, severity)

            result.append({
                "wcagIssueId": str(uuid.uuid4()),   # 동적 uuid 생성
                "title": v.get("description", ""),   # axe-core description을 title로
                "severity": severity,
                "description": description,           # GPT-4o 한국어 번역
                "html": html,
                "wcag_criteria": wcag_criteria,
            })

        # severity 순 정렬: Critical → Moderate → Minor
        order = {"Critical": 0, "Moderate": 1, "Minor": 2}
        result.sort(key=lambda x: order.get(x["severity"], 3))

        return result

    def _extract_wcag_criteria(self, tags: List[str]) -> str:
        """
        axe-core tags에서 wcag 기준 번호 추출
        예: ["wcag2aa", "wcag143", "cat.color"] → "1.4.3"
        숫자가 포함된 wcag 태그만 추출, 나머지 무시
        """
        for tag in tags:
            if tag.startswith("wcag") and any(c.isdigit() for c in tag):
                digits = tag.replace("wcag", "")
                # "2aa", "2a" 같은 레벨 태그 제외, 숫자 3자리 이상만
                if len(digits) >= 3 and digits.isdigit():
                    return ".".join(digits)  # "143" → "1.4.3"
        return ""

    def _translate_description(self, help_text: str, severity: str) -> str:
        """
        GPT-4o로 axe-core help 텍스트를 한국어 description으로 번역

        navigator_ai가 없으면 원문 그대로 반환
        """
        if not self.navigator_ai or not help_text:
            return help_text

        prompt = f"""다음 WCAG 접근성 이슈 설명을 한국어로 번역해줘.
심각도: {severity}
원문: {help_text}

규칙:
1. 전문적이고 간결하게 (1-2문장)
2. 어떤 사용자에게 영향을 주는지 포함
3. JSON으로 응답: {{"description": "..."}}"""

        try:
            response = self.navigator_ai.call(prompt)
            return response.get("description", help_text)
        except Exception as e:
            print(f"[WCAG] 번역 실패: {e}")
            return help_text

    def _save(self, result: Dict, date_prefix: str):
        """로컬 저장 + S3 업로드"""
        local_path = Path(f"/tmp/wcag_{date_prefix.replace('/', '_')}.json")
        with open(local_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[WCAG] 로컬 저장: {local_path}")

        if self.uploader:
            s3_key = f"raw/{date_prefix}/analyzed/wcag.json"
            self.uploader.upload_file(str(local_path), s3_key)
            print(f"[WCAG] S3 업로드: {s3_key}")