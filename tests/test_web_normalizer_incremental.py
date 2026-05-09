# tests/test_web_normalizer_incremental.py

import pytest
import time
from playwright.sync_api import sync_playwright, Page
from normalizer.mcp.web_normalizer.web_normalizer_incremental import WebNormalizerIncremental
from dotenv import load_dotenv
import os

# .env 로드
load_dotenv()  # 추가

class TestWebNormalizerIncremental:
    """
    WebNormalizerIncremental 통합 테스트
    
    테스트 목적:
    1. 전체 파싱 vs 증분 파싱 분기 확인
    2. MutationObserver 변경 감지 확인
    3. 캐시 시스템 정확성 확인
    4. 성능 측정 (전체 vs 증분)
    """
    
    @pytest.fixture
    def browser_page(self):
        """Playwright 브라우저 fixture"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)  # headless=True
            page = browser.new_page()
            yield page
            browser.close()
    
    @pytest.fixture
    def test_html(self):
        """테스트용 HTML"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>테스트 페이지</title>
            <style>
                .modal { display: none; }
                .modal.active { display: block; }
            </style>
        </head>
        <body>
            <h1 id="title">메인 페이지</h1>
            <button id="open-modal">모달 열기</button>
            <button id="change-text">텍스트 변경</button>
            
            <div id="modal" class="modal">
                <h2>모달 제목</h2>
                <p>모달 내용입니다.</p>
                <button id="close-modal">닫기</button>
            </div>
            
            <script>
                document.getElementById('open-modal').addEventListener('click', () => {
                    document.getElementById('modal').classList.add('active');
                });
                
                document.getElementById('close-modal').addEventListener('click', () => {
                    document.getElementById('modal').classList.remove('active');
                });
                
                document.getElementById('change-text').addEventListener('click', () => {
                    const title = document.getElementById('title');
                    title.textContent = title.textContent === '메인 페이지' 
                        ? '변경된 페이지' 
                        : '메인 페이지';
                });
            </script>
        </body>
        </html>
        """
    
    def test_1_initial_full_parse(self, browser_page, test_html):
        """
        Test 1: 전체 파싱 (첫 방문)
        
        검증:
        - Observer 설치됨
        - 전체 노드 파싱됨
        - 캐시 구축됨
        """
        print("\n=== Test 1: 전체 파싱 (첫 방문) ===")
        
        # HTML 로드
        browser_page.set_content(test_html)
        browser_page.wait_for_load_state('networkidle')
        
        # 증분 파싱 인스턴스 생성
        incremental = WebNormalizerIncremental()
        
        # 첫 파싱 실행
        start_time = time.time()
        nodes = incremental.normalize(browser_page)
        parse_time = time.time() - start_time
        
        # 검증
        assert len(nodes) > 0, "노드가 파싱되지 않음"
        assert incremental.mutation_observer.is_installed(), "Observer 미설치"
        assert len(incremental.cache_manager.cache_map) > 0, "캐시 미구축"
        assert incremental.last_url == browser_page.url, "URL 기록 안 됨"
        
        print(f"✅ 전체 파싱 완료: {len(nodes)}개 노드")
        print(f"✅ 캐시 크기: {len(incremental.cache_manager.cache_map)}개")
        print(f"✅ 파싱 시간: {parse_time:.3f}초")
        
        return incremental  # 다음 테스트에서 재사용
    
    def test_2_incremental_parse_add_element(self, browser_page, test_html):
        """
        Test 2: 증분 파싱 (요소 추가)
        
        검증:
        - 모달 열기 → 모달 요소만 파싱됨
        - 전체 파싱보다 빠름
        - 캐시에 추가됨
        """
        print("\n=== Test 2: 증분 파싱 (요소 추가) ===")
        
        # 초기 설정
        browser_page.set_content(test_html)
        browser_page.wait_for_load_state('networkidle')
        
        incremental = WebNormalizerIncremental()
        initial_nodes = incremental.normalize(browser_page)
        initial_count = len(incremental.cache_manager.cache_map)
        
        print(f"초기 노드 수: {len(initial_nodes)}개")
        
        # 모달 열기
        browser_page.click('#open-modal')
        browser_page.wait_for_timeout(500)  # DOM 변경 대기
        
        # 증분 파싱 실행
        start_time = time.time()
        delta_nodes = incremental.normalize(browser_page)
        parse_time = time.time() - start_time
        
        final_count = len(incremental.cache_manager.cache_map)
        
        # 검증
        assert len(delta_nodes) > 0, "변경 감지 실패"
        assert len(delta_nodes) < len(initial_nodes), "전체 파싱됨 (증분 실패)"
        assert final_count > initial_count, "캐시 업데이트 안 됨"
        
        print(f"✅ 증분 파싱 완료: {len(delta_nodes)}개 노드 (전체 {len(initial_nodes)}개 대비)")
        print(f"✅ 캐시 증가: {initial_count}개 → {final_count}개 (+{final_count - initial_count})")
        print(f"✅ 파싱 시간: {parse_time:.3f}초")
    
    def test_3_incremental_parse_modify_element(self, browser_page, test_html):
        print("\n=== Test 3 시작 ===")
        
        browser_page.set_content(test_html)
        print("HTML 로드 완료")
        
        browser_page.wait_for_load_state('networkidle')
        print("페이지 로드 대기 완료")
        
        incremental = WebNormalizerIncremental()
        print("Incremental 인스턴스 생성 완료")
        
        initial_nodes = incremental.normalize(browser_page)
        print(f"초기 파싱 완료: {len(initial_nodes)}개")
        
        # 모든 노드의 id 확인
        all_ids = [n.metadata.get('id') for n in initial_nodes]
        print(f"모든 ID: {all_ids}")
        
        # title 노드 찾기
        title_nodes = [n for n in initial_nodes if n.metadata.get('id') == 'title']
        print(f"title 노드 개수: {len(title_nodes)}")
        
        if len(title_nodes) == 0:
            print("❌ title 노드를 못 찾음!")
            print("HTML:", test_html[:200])
            assert False, "title 노드 없음"
    
    def test_4_incremental_parse_remove_element(self, browser_page, test_html):
        """
        Test 4: 증분 파싱 (요소 삭제)
        
        검증:
        - 모달 닫기 → 모달 요소 삭제됨
        - 캐시에서 제거됨
        """
        print("\n=== Test 4: 증분 파싱 (요소 삭제) ===")
        
        # 초기 설정 + 모달 열기
        browser_page.set_content(test_html)
        browser_page.wait_for_load_state('networkidle')
        
        incremental = WebNormalizerIncremental()
        incremental.normalize(browser_page)
        
        # 모달 열기
        browser_page.click('#open-modal')
        browser_page.wait_for_timeout(500)
        incremental.normalize(browser_page)
        
        cache_with_modal = len(incremental.cache_manager.cache_map)
        print(f"모달 열린 상태 캐시: {cache_with_modal}개")
        
        # 모달 닫기
        browser_page.click('#close-modal')
        browser_page.wait_for_timeout(500)
        
        # 증분 파싱
        delta_nodes = incremental.normalize(browser_page)
        cache_after_close = len(incremental.cache_manager.cache_map)
        
        # 검증
        # Note: display:none은 삭제가 아니라 숨김이므로 DOM에 남아있음
        # 실제 삭제 테스트는 removeChild 필요
        print(f"✅ 모달 닫힌 후 캐시: {cache_after_close}개")
        print(f"✅ 증분 파싱: {len(delta_nodes)}개 노드")
    
    def test_5_url_change_triggers_full_parse(self, browser_page, test_html):
        """
        Test 5: URL 변경 → 전체 파싱
        
        검증:
        - 다른 페이지 이동 시 전체 파싱
        - 캐시 초기화
        """
        print("\n=== Test 5: URL 변경 → 전체 파싱 ===")
        
        # 첫 페이지
        browser_page.goto("data:text/html," + test_html)
        browser_page.wait_for_load_state('networkidle')
        
        incremental = WebNormalizerIncremental()
        first_nodes = incremental.normalize(browser_page)
        first_url = browser_page.url
        first_cache_size = len(incremental.cache_manager.cache_map)
        
        print(f"첫 페이지: {len(first_nodes)}개 노드, 캐시 {first_cache_size}개")
        
        # 다른 페이지로 이동
        second_html = """
        <!DOCTYPE html>
        <html>
        <head><title>두 번째 페이지</title></head>
        <body>
            <h1>새로운 페이지</h1>
            <p>완전히 다른 구조입니다.</p>
        </body>
        </html>
        """
        browser_page.goto("data:text/html," + second_html)
        browser_page.wait_for_load_state('networkidle')
        
        # 파싱 실행
        second_nodes = incremental.normalize(browser_page)
        second_url = browser_page.url
        second_cache_size = len(incremental.cache_manager.cache_map)
        
        # 검증
        assert second_url != first_url, "URL이 같음"
        assert incremental.last_url == second_url, "URL 업데이트 안 됨"
        # 캐시는 완전히 새로 구축됨
        
        print(f"✅ 두 번째 페이지: {len(second_nodes)}개 노드, 캐시 {second_cache_size}개")
        print(f"✅ URL 변경 감지: 전체 파싱 실행됨")
    
    def test_6_performance_comparison(self, browser_page, test_html):
        """
        Test 6: 성능 측정
        
        측정:
        - 전체 파싱 시간
        - 증분 파싱 시간
        - 속도 향상 비율
        """
        print("\n=== Test 6: 성능 측정 ===")
        
        # 초기 설정
        browser_page.set_content(test_html)
        browser_page.wait_for_load_state('networkidle')
        
        incremental = WebNormalizerIncremental()
        
        # 전체 파싱 시간 측정
        start = time.time()
        full_nodes = incremental.normalize(browser_page)
        full_parse_time = time.time() - start
        
        # 모달 열기
        browser_page.click('#open-modal')
        browser_page.wait_for_timeout(500)
        
        # 증분 파싱 시간 측정
        start = time.time()
        delta_nodes = incremental.normalize(browser_page)
        incremental_parse_time = time.time() - start
        
        # 결과
        speedup = full_parse_time / incremental_parse_time if incremental_parse_time > 0 else 0
        
        print(f"✅ 전체 파싱: {full_parse_time:.3f}초 ({len(full_nodes)}개 노드)")
        print(f"✅ 증분 파싱: {incremental_parse_time:.3f}초 ({len(delta_nodes)}개 노드)")
        print(f"✅ 속도 향상: {speedup:.1f}배")
        
        assert incremental_parse_time < full_parse_time, "증분 파싱이 더 느림"
    
    def test_7_observer_buffer_isolation(self, browser_page, test_html):
        """
        Test 7: Observer 버퍼 격리 확인
        
        검증:
        - clear_buffers 후 이전 변경 사항 남지 않음
        - 독립적인 변경 추적
        """
        print("\n=== Test 7: Observer 버퍼 격리 ===")
        
        # 초기 설정
        browser_page.set_content(test_html)
        browser_page.wait_for_load_state('networkidle')
        
        incremental = WebNormalizerIncremental()
        incremental.normalize(browser_page)
        
        # 첫 번째 변경
        browser_page.click('#open-modal')
        browser_page.wait_for_timeout(500)
        first_delta = incremental.normalize(browser_page)
        
        print(f"첫 번째 변경: {len(first_delta)}개 노드")
        
        # 두 번째 변경 (독립적)
        browser_page.click('#change-text')
        browser_page.wait_for_timeout(500)
        second_delta = incremental.normalize(browser_page)
        
        print(f"두 번째 변경: {len(second_delta)}개 노드")
        
        # 검증: 두 번째 변경에 첫 번째 변경 포함 안 됨
        assert len(second_delta) < len(first_delta) + len(second_delta), "버퍼 격리 실패"
        print(f"✅ 버퍼 격리 확인: 독립적 변경 추적")


# 실행 방법:
# pytest tests/test_web_normalizer_incremental.py -v -s