"""
DOMExtractor - 방문 URL별 HTML DOM 추출 및 S3 저장

역할:
    시뮬레이션 완료 후 Navigator AI가 방문한 모든 URL의 HTML을 추출하여 S3에 저장.
    Lambda 5(Fix 제안)에서 final_issues URL 기준으로 해당 DOM을 가져다 GPT-4o에 넘김.

사용:
    extractor = DOMExtractor(page=page, uploader=uploader)
    extractor.run(urls=["https://example.com/"], date_prefix="2026-05-03_23-10-12")

S3 저장 경로:
    raw/logs/{date_prefix}/dom/{url_encoded}.html
"""

import json
import traceback
from typing import List, Dict, Optional
from pathlib import Path
from urllib.parse import quote
from playwright.sync_api import Page

from AI.Auditor_AI.utils.s3_uploader import S3Uploader


class DOMExtractor:

    def __init__(
        self,
        page: Page,
        uploader: Optional[S3Uploader] = None,
    ):
        self.page = page
        self.uploader = uploader

    def run(self, urls: List[str], date_prefix: str) -> Dict:
        result = {}
        for url in urls:
            print(f"[DOM] 추출 중: {url}")
            try:
                html = self._extract_url(url)
                styles = self._extract_styles(url)
                s3_key = self._save(url, html, styles, date_prefix)
                result[url] = s3_key
            except Exception as e:
                print(f"[DOM] 실패: {url} → {e}")
                traceback.print_exc()
                result[url] = None
        return result

    def _extract_url(self, url: str) -> str:
        """
        단일 URL HTML 추출

        흐름:
        1. URL 로드
        2. networkidle 대기 (동적 콘텐츠 로드 완료 보장)
        3. page.content()로 전체 HTML 반환

        Args:
            url: 추출할 URL

        Returns:
            HTML 문자열
        """
        self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
        self._dismiss_overlays()
        self.page.wait_for_timeout(2000)
        return self.page.content()

    def _encode_url(self, url: str) -> str:
        """
        URL을 S3 키로 사용 가능한 문자열로 인코딩

        예: "https://example.com/search?q=test" → "https%3A%2F%2Fexample.com%2Fsearch%3Fq%3Dtest"

        Args:
            url: 원본 URL

        Returns:
            인코딩된 문자열
        """
        return quote(url, safe='')

    def _save(self, url: str, html: str, styles: List[Dict], date_prefix: str) -> str:
        """
        HTML + styles 로컬 저장 + S3 업로드

        Args:
            url: 원본 URL
            html: 페이지 HTML
            styles: computedStyle 리스트
            date_prefix: S3 경로용 날짜 prefix

        Returns:
            S3 key 문자열
        """
        encoded = self._encode_url(url)
        data = {
            "url": url,
            "html": html,
            "styles": styles
        }

        local_path = Path(f"/tmp/dom_{encoded}.json")
        with open(local_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        s3_key = f"raw/{date_prefix}/dom/{encoded}.json"
        if self.uploader:
            self.uploader.upload_file(str(local_path), s3_key)
            print(f"[DOM] S3 업로드: {s3_key}")
            
        print(f"[DOM] _save 호출됨: {url}")
        print(f"[DOM] uploader: {self.uploader}")

        return s3_key
    
    def _extract_styles(self, url: str) -> List[Dict]:
        """
        페이지 내 가시적 요소의 computedStyle 추출

        - display:none, visibility:hidden 요소 제외
        - Fix 제안에 필요한 스타일 속성만 추출
        (font-size, color, background-color, padding, margin,
        border, opacity, cursor, text-decoration)

        Args:
            url: 현재 페이지 URL (로드 확인용)

        Returns:
            [{"selector": "...", "styles": {...}}, ...] 리스트
        """
        return self.page.evaluate("""
            () => {
                const elements = Array.from(document.querySelectorAll('*'));
                const result = [];

                for (const el of elements) {
                    const style = window.getComputedStyle(el);

                    // 비가시 요소 제외
                    if (style.display === 'none' || style.visibility === 'hidden') continue;

                    // selector 생성
                    let selector = el.tagName.toLowerCase();
                    if (el.id) selector = `#${el.id}`;
                    else if (el.className && typeof el.className === 'string') {
                        const cls = el.className.trim().split(/\\s+/).join('.');
                        if (cls) selector = `${el.tagName.toLowerCase()}.${cls}`;
                    }

                    result.push({
                        selector: selector,
                        text: (el.textContent || '').trim().slice(0, 50),
                        styles: {
                            'font-size': style.fontSize,
                            'color': style.color,
                            'background-color': style.backgroundColor,
                            'padding': style.padding,
                            'margin': style.margin,
                            'border': style.border,
                            'opacity': style.opacity,
                            'cursor': style.cursor,
                            'text-decoration': style.textDecoration,
                            'font-weight': style.fontWeight,
                        }
                    });
                }

                return result;
            }
        """)
        
    def _dismiss_overlays(self):
        """광고, 모달, 쿠키 배너 자동 닫기. 실패해도 조용히 넘김."""
        try:
            self.page.evaluate("""
                () => {
                    if (window.location.hash === '#google_vignette') {
                        history.replaceState(null, '', window.location.pathname + window.location.search);
                    }
                    document.querySelectorAll('iframe[id*="google_ads"], iframe[id*="aswift"]').forEach(el => el.remove());
                    document.querySelectorAll('[id*="google_vignette"], .adsbygoogle').forEach(el => el.remove());
                    const closeSelectors = [
                        '[aria-label="Close ad" i]',
                        '[aria-label="Close" i]',
                        'button.dismiss-button',
                        '.modal-close',
                        '#dismiss-button',
                    ];
                    for (const sel of closeSelectors) {
                        const btn = document.querySelector(sel);
                        if (btn) btn.click();
                    }
                }
            """)
        except Exception as e:
            print(f"[DISMISS_OVERLAY] skip: {e}")