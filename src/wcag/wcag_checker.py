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

    def __init__(self, page, uploader=None, navigator_ai=None):
        self.page = page
        self.uploader = uploader
        self.navigator_ai = navigator_ai

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

    def _parse_violations(self, raw: List[Dict]) -> List[Dict]:
        result = []
        for v in raw:
            severity = IMPACT_MAP.get(v.get("impact", "minor"), "Minor")
            print(f"[TAGS] {v.get('tags')}")

            html = ""
            if v.get("nodes"):
                html = v["nodes"][0].get("html", "")

            wcag_criteria = self._extract_wcag_criteria(v.get("tags", []))

            # title + description 한 번에 번역
            title_en = v.get("description", "")
            help_text = v.get("help", "")
            translated = self._translate_violation(title_en, help_text, severity)

            result.append({
                "wcagIssueId": str(uuid.uuid4()),
                "title": translated["title"],
                "severity": severity,
                "description": translated["description"],
                "html": html,
                "wcag_criteria": wcag_criteria,
            })

        order = {"Critical": 0, "Moderate": 1, "Minor": 2}
        result.sort(key=lambda x: order.get(x["severity"], 3))

        return result


    def _translate_violation(self, title, help_text, severity):
        """
        title + description을 한 번에 한국어로 번역
        """
        if not self.navigator_ai:
            return {"title": title, "description": help_text}

        prompt = f"""다음 WCAG 접근성 이슈를 한국어로 번역해줘.
    심각도: {severity}
    영문 title: {title}
    영문 description: {help_text}

    규칙:
    1. title: 간결한 명사형 (10자 이내, 예: "색상 대비 부족")
    2. description: 전문적이고 간결하게 (1-2문장, 어떤 사용자에게 영향을 주는지 포함)
    3. JSON으로 응답: {{"title": "...", "description": "..."}}"""

        try:
            response = self.navigator_ai.call(prompt)
            return {
                "title": response.get("title", title),
                "description": response.get("description", help_text)
            }
        except Exception as e:
            print(f"[WCAG] 번역 실패: {e}")
            return {"title": title, "description": help_text}

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