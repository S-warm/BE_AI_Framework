# tests/test_vision_filter_unit.py

import pytest
from normalizer.standard_ui_node import StandardUINode
from AI.layer_tier2.filters.vision_filter import VisionFilter


def make_node(id, type, content, properties, image_analysis=None):
    return StandardUINode(
        id=id,
        type=type,
        content=content,
        properties=properties,
        image_analysis=image_analysis
    )


class TestFontSizeFilter:

    def test_removes_small_font(self):
        """70대 기준 16px 미달 텍스트 제거"""
        nodes = [
            make_node("1", "text", "작은글씨", {"font_size": 10, "contrast_ratio": 7.0}),
            make_node("2", "text", "큰글씨", {"font_size": 18, "contrast_ratio": 7.0}),
        ]
        filtered = VisionFilter('70s').apply(nodes)
        ids = [n.id for n in filtered]
        assert "1" not in ids
        assert "2" in ids

    def test_image_button_passes(self):
        """font_size 없는 이미지 버튼은 통과"""
        nodes = [
            make_node("1", "button", "", {"contrast_ratio": 7.0, "size": {"width": 48, "height": 48}}),
        ]
        filtered = VisionFilter('70s').apply(nodes)
        assert len(filtered) == 1


class TestContrastFilter:

    def test_removes_low_contrast(self):
        """70대 기준 7.0 미달 노드 제거"""
        nodes = [
            make_node("1", "text", "저대비", {"font_size": 18, "contrast_ratio": 4.5}),
            make_node("2", "text", "고대비", {"font_size": 18, "contrast_ratio": 7.0}),
        ]
        filtered = VisionFilter('70s').apply(nodes)
        ids = [n.id for n in filtered]
        assert "1" not in ids
        assert "2" in ids


class TestButtonSizeFilter:

    def test_removes_small_button(self):
        """70대 기준 48px 미달 버튼 제거"""
        nodes = [
            make_node("1", "button", "작은버튼", {"font_size": 18, "contrast_ratio": 7.0, "size": {"width": 32, "height": 32}}),
            make_node("2", "button", "큰버튼", {"font_size": 18, "contrast_ratio": 7.0, "size": {"width": 48, "height": 48}}),
        ]
        filtered = VisionFilter('70s').apply(nodes)
        ids = [n.id for n in filtered]
        assert "1" not in ids
        assert "2" in ids

    def test_non_button_passes(self):
        """버튼/링크 아닌 노드는 크기 무관 통과"""
        nodes = [
            make_node("1", "text", "텍스트", {"font_size": 18, "contrast_ratio": 7.0, "size": {"width": 10, "height": 10}}),
        ]
        filtered = VisionFilter('70s').apply(nodes)
        assert len(filtered) == 1


class TestIconFilter:

    def test_removes_icons_by_tier_order(self):
        """하 tier부터 제거, 논문 수치(70대 80%) 유지"""
        nodes = [
            make_node("1", "image", "", {"tier": "상", "contrast_ratio": 7.0, "image_analysis": {"vision_type": "ICON"}}),
            make_node("2", "image", "", {"tier": "중", "contrast_ratio": 7.0, "image_analysis": {"vision_type": "ICON"}}),
            make_node("3", "image", "", {"tier": "중", "contrast_ratio": 7.0, "image_analysis": {"vision_type": "ICON"}}),
            make_node("4", "image", "", {"tier": "하", "contrast_ratio": 7.0, "image_analysis": {"vision_type": "ICON"}}),
            make_node("5", "image", "", {"tier": "하", "contrast_ratio": 7.0, "image_analysis": {"vision_type": "ICON"}}),
        ]
        filtered = VisionFilter('70s').apply(nodes)
        remaining_ids = [n.id for n in filtered]

        # 70대 80% 제거 = 5개 중 4개 제거, 1개 남음
        assert len(filtered) == 1
        # 상 tier가 마지막에 제거되므로 상 tier 남아있어야 함
        assert "1" in remaining_ids

    def test_non_icon_not_affected(self):
        """ICON 아닌 이미지 노드는 영향 없음"""
        nodes = [
            make_node("1", "image", "", {"tier": "하", "contrast_ratio": 7.0, "image_analysis": {"vision_type": "LOGO"}}),
        ]
        filtered = VisionFilter('70s').apply(nodes)
        assert len(filtered) == 1