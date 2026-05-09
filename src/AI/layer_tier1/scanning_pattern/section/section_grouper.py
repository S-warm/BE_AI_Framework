"""
HTML semantic tag 기준 섹션 그룹핑
main 섹션은 viewport 높이 단위로 청킹
"""

from typing import List, Dict
from normalizer.standard_ui_node import StandardUINode


def group_by_html_tag(
    nodes: List[StandardUINode],
    viewport_height: int = 1080
) -> Dict[str, List[StandardUINode]]:
    """
    HTML semantic tag 기준 섹션 그룹핑
    main 섹션은 viewport 높이 단위로 청킹

    Args:
        nodes: StandardUINode 리스트
        viewport_height: 뷰포트 높이 (기본값 1080px)

    Returns:
        {
            'header': [...],
            'nav': [...],
            'main_0': [...],  # y 0~1080
            'main_1': [...],  # y 1080~2160
            ...
            'footer': [...]
        }

    Notes:
        - 'other' 섹션은 'main'으로 병합
        - 빈 섹션은 결과에서 제외
        - main은 viewport_height 단위로 청킹
    """
    sections = {
        'header': [],
        'nav': [],
        'main': [],
        'footer': [],
        'other': []
    }

    for node in nodes:
        if not node.metadata:
            sections['other'].append(node)
            continue

        xpath = node.metadata.get('xpath', '')
        ancestor_tags = node.metadata.get('ancestor_tags', [])

        if 'header' in ancestor_tags or 'header[' in xpath:
            sections['header'].append(node)
        elif 'footer' in ancestor_tags or 'footer[' in xpath:
            sections['footer'].append(node)
        elif 'nav' in ancestor_tags or 'nav[' in xpath:
            sections['nav'].append(node)
        elif 'main' in ancestor_tags or 'main[' in xpath:
            sections['main'].append(node)
        else:
            sections['other'].append(node)

    # other를 main으로 병합
    if sections['other']:
        sections['main'].extend(sections['other'])

    # ── main 청킹 ──────────────────────────────────────────
    # 1단계: y좌표 기준으로 청크 분류
    chunks: Dict[int, List[StandardUINode]] = {}
    for node in sections['main']:
        y = node.properties.get('y', 0)
        chunk_idx = int(y // viewport_height)
        if chunk_idx not in chunks:
            chunks[chunk_idx] = []
        chunks[chunk_idx].append(node)

    # 2단계: 청크 0에 노드가 너무 많으면 분산 (y=0 몰림 현상 방지)
    # visual_priority 상위 50개만 main_0에 유지, 나머지는 main_1으로 이동
    MAX_CHUNK_0 = 50
    if 0 in chunks and len(chunks[0]) > MAX_CHUNK_0:
        chunks[0].sort(
            key=lambda n: n.properties.get('visual_priority', 0),
            reverse=True
        )
        overflow = chunks[0][MAX_CHUNK_0:]
        chunks[0] = chunks[0][:MAX_CHUNK_0]

        if 1 not in chunks:
            chunks[1] = []
        chunks[1] = overflow + chunks[1]  # overflow를 앞에 붙임

    # ── 결과 조립 ──────────────────────────────────────────
    result: Dict[str, List[StandardUINode]] = {}

    if sections['header']:
        result['header'] = sections['header']
    if sections['nav']:
        result['nav'] = sections['nav']

    for idx in sorted(chunks.keys()):
        if chunks[idx]:
            result[f'main_{idx}'] = chunks[idx]

    if sections['footer']:
        result['footer'] = sections['footer']

    return result