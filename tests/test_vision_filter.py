# tests/test_vision_filter.py

import pytest
from playwright.sync_api import sync_playwright
from normalizer.mcp.web_normalizer.web_normalizer_incremental.web_normalizer_incremental import WebNormalizerIncremental
from AI.layer_tier2.filters.vision_filter import VisionFilter


@pytest.fixture(scope="module")
def parsed_nodes():
    from dotenv import load_dotenv
    load_dotenv()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="chrome")
        page = browser.new_page()
        page.goto("https://www.dbpia.co.kr/", wait_until="networkidle")
        
        normalizer = WebNormalizerIncremental()
        nodes = normalizer.normalize(page)
        
        browser.close()
        return nodes


class TestVisionFilter:

    def test_70s_reduces_nodes(self, parsed_nodes):
        f = VisionFilter('70s')
        filtered = f.apply(parsed_nodes)
        
        removed = [n for n in parsed_nodes if n not in filtered]
        print(f"\n원본: {len(parsed_nodes)}개 → 필터링: {len(filtered)}개")
        print(f"\n제거된 노드 {len(removed)}개:")
        for n in removed:
            print(f"  [{n.type}] '{n.content[:30]}' | font={n.properties.get('font_size')} contrast={n.properties.get('contrast_ratio')} size={n.properties.get('size')}")
        
        assert len(filtered) < len(parsed_nodes)

    def test_20s_removes_less_than_70s(self, parsed_nodes):
        """20대가 70대보다 덜 제거되는지"""
        f20 = VisionFilter('20s')
        f70 = VisionFilter('70s')
        filtered_20 = f20.apply(parsed_nodes)
        filtered_70 = f70.apply(parsed_nodes)
        print(f"\n20대: {len(filtered_20)}개, 70대: {len(filtered_70)}개")
        assert len(filtered_20) >= len(filtered_70)

    def test_icon_filter(self, parsed_nodes):
        """아이콘 단독 노드 필터링 비율 확인"""
        from normalizer.standard_ui_node import StandardUINode
        icon_nodes = [
            n for n in parsed_nodes
            if not n.content.strip()
            and n.properties.get('image_analysis', {}).get('vision_type') == 'ICON'
        ]
        print(f"\n아이콘 단독 노드: {len(icon_nodes)}개")
        
        f = VisionFilter('70s')
        filtered = f.apply(parsed_nodes)
        remaining_icons = [
            n for n in filtered
            if not n.content.strip()
            and n.properties.get('image_analysis', {}).get('vision_type') == 'ICON'
        ]
        print(f"필터 후 아이콘: {len(remaining_icons)}개")