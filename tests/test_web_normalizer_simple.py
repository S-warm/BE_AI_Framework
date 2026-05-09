# test_web_normalizer_simple.py

from playwright.sync_api import sync_playwright
from normalizer.mcp.web_normalizer.web_normalizer import WebNormalizer
from dotenv import load_dotenv
import os

# .env 로드
load_dotenv()  # 추가

def test_basic_normalize():
    """기본 동작 테스트"""
    
    # API Key 확인 (디버깅용)
    print(f"API Key 존재 여부: {bool(os.getenv('ANTHROPIC_API_KEY'))}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # 간단한 HTML 페이지
        page.set_content("""
        <!DOCTYPE html>
        <html>
        <body>
            <h1>Test Page</h1>
            <button id="submit-btn">Submit</button>
            <input type="text" placeholder="Enter name">
            <p>This is a paragraph.</p>
            <img src="test.png" alt="Test image">
        </body>
        </html>
        """)
        
        # WebNormalizer 실행
        normalizer = WebNormalizer()
        nodes = normalizer.normalize(page)
        
        # 기본 검증
        print(f"✅ 총 {len(nodes)}개 노드 추출")
        
        # 타입별 개수 확인
        types = [n.type for n in nodes]
        print(f"✅ 타입 분포: {set(types)}")
        
        # 버튼 찾기
        buttons = [n for n in nodes if n.type == 'button']
        print(f"✅ 버튼 {len(buttons)}개 발견")
        if buttons:
            print(f"   - 첫 버튼 내용: '{buttons[0].content}'")
        
        # input 찾기
        inputs = [n for n in nodes if n.type == 'input']
        print(f"✅ Input {len(inputs)}개 발견")
        if inputs:
            print(f"   - 첫 input placeholder: '{inputs[0].content}'")
        
        browser.close()
        
        # 최소 검증
        assert len(nodes) > 0, "노드가 하나도 추출되지 않음"
        assert len(buttons) > 0, "버튼이 발견되지 않음"
        print("\n✅ 모든 테스트 통과!")

if __name__ == "__main__":
    test_basic_normalize()