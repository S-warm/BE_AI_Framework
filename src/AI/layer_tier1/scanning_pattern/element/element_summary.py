"""
탐색 완료된 tier 요소 요약 포맷
Navigator AI에게 이미 돈 tier를 최소 토큰으로 전달
"""

from typing import List
from normalizer.standard_ui_node import StandardUINode


def _get_element_id(node: StandardUINode, index: int) -> str:
    """
    요소 식별자 반환
    HTML id 있으면 사용, 없으면 인덱스 번호 fallback
    """
    html_id = node.metadata.get('id', '') if node.metadata else ''
    return html_id if html_id else str(index)


def format_element_summary(node: StandardUINode, index: int) -> str:
    """
    탐색 완료 tier용 최소 요약 포맷
    element_id + type + content만 포함 (좌표/크기/tier 제거)

    Returns:
        "[elem12] link '새소식'"
        "[3] button '로그인'"
    """
    if node.type == 'image':
        content = node.metadata.get('image_class', 'image') if node.metadata else 'image'
    else:
        content = node.content or '[no text]'

    elem_id = _get_element_id(node, index)
    return f"[{elem_id}] {node.type} '{content}'"


def summarize_tier(nodes: List[StandardUINode], tier: str) -> str:
    """
    탐색 완료된 tier 전체 요약
    element_id 포함 → 돌아가서 클릭 가능

    Args:
        nodes: context_elements 전체
        tier: '상', '중', '하'

    Returns:
        "[elem12] link '새소식'\n[elem13] link '대학소개'\n..."
        없으면 "(없음)"
    """
    tier_nodes = [n for n in nodes if n.properties.get('tier') == tier]
    if not tier_nodes:
        return "(없음)"

    lines = [format_element_summary(node, i) for i, node in enumerate(tier_nodes)]
    return "\n".join(lines)


def count_tier(nodes: List[StandardUINode], tier: str) -> str:
    """
    미탐색 tier 구조 카운트
    구조 파악용이므로 element_id 없음

    Args:
        nodes: context_elements 전체
        tier: '상', '중', '하'

    Returns:
        "link 32개, button 8개, text 7개"
        없으면 "(없음)"
    """
    tier_nodes = [n for n in nodes if n.properties.get('tier') == tier]
    if not tier_nodes:
        return "(없음)"

    counts: dict = {}
    for node in tier_nodes:
        counts[node.type] = counts.get(node.type, 0) + 1

    return ", ".join(f"{t} {n}개" for t, n in counts.items())