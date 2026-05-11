#src/AI/layer_tier1/scanning_pattern/utils/prompt_builder.py

"""
Navigator AI 프롬프트 생성
"""

from typing import List, Dict
from normalizer.standard_ui_node import StandardUINode
from AI.layer_tier1.scanning_pattern.element.element_summary import summarize_tier, count_tier


def format_element(node: StandardUINode) -> str:
    """
    요소 포맷 (상/중/하 공통)
    
    Args:
        node: 포맷할 노드
        
    Returns:
        "button '로그인' at (x:100, y:200, w:80, h:30) tier:상"
        "image 'icon' at (x:50, y:50, w:24, h:24) tier:중"
    """
    element_type = node.type
    tier = node.properties.get('tier', '?')
    x = node.properties.get('x', 0)
    y = node.properties.get('y', 0)
    width = node.properties.get('width', 0)
    height = node.properties.get('height', 0)
    
    # 요소 내용 처리
    if node.type == 'image':
        content = node.metadata.get('image_class', 'image')
    else:
        content = node.content or '[no text]'
    
    return f"{element_type} '{content}' at (x:{x}, y:{y}, w:{width}, h:{height}) tier:{tier}"


def build_prompt(
    visible_elements: List[StandardUINode],
    context_elements: List[StandardUINode],
    current_tier: str,
    goal: str,
    explored_tiers: List[str] = None,
    success_condition: str = None,
    verify_fail_reason: str = None
) -> str:
    """
    Navigator AI 프롬프트 생성 (섹션 탐색용)
    """
    visible_lines = []
    for i, elem in enumerate(visible_elements):
        visible_lines.append(f"[{i}] {format_element(elem)}")
    visible_text = "\n".join(visible_lines) if visible_lines else "(없음)"
    
    tier_map = {'상': '중/하', '중': '상/하', '하': '상/중'}
    excluded = tier_map.get(current_tier, '다른')
    
    explored = explored_tiers or []

    if '중' in explored:
        중_text = summarize_tier(context_elements, '중')
        중_label = "**중 tier (탐색 완료)**"
    else:
        중_text = count_tier(context_elements, '중')
        중_label = "**중 tier 구조** (미탐색, 액션 불가)"

    if '하' in explored:
        하_text = summarize_tier(context_elements, '하')
        하_label = "**하 tier (탐색 완료)**"
    else:
        하_text = count_tier(context_elements, '하')
        하_label = "**하 tier 구조** (미탐색, 액션 불가)"
    
    # success_condition 섹션
    # 변경
    if success_condition:
        if verify_fail_reason:
            success_text = f"""
        **성공 조건**: {success_condition}
        """
        else:
            success_text = f"""
        **성공 조건**: {success_condition}

        **중요**: 최근_행동에서 목표를 달성했다면 즉시 declare_success 호출
        """
    else:
        success_text = ""
        
    verify_text = ""
    if verify_fail_reason:
        verify_text = f"\n<주의>\n목표 미달성: {verify_fail_reason}\n아직 탐색을 계속하세요. 성공 선언하지 마세요.\n</주의>"
    
    prompt = f"""
당신은 현재 {current_tier} tier 요소만 탐색 중입니다.

**목표**: {goal}
{success_text}
{verify_text}

**규칙**:
1. {current_tier} tier 요소만 found=True 가능
2. {excluded} tier 요소는 선택 불가
3. element_id는 [인덱스] 번호 사용
4. 현재 tier 요소 중 목표와 직접 관련된 요소가 없으면 반드시 declare_failure
    ※ 목표 텍스트와 유사한 내용이 있는 경우, 해당 텍스트 근처의 클릭 가능한 요소(link, button, cursor:pointer인 container/text)도 목표와 관련된 요소로 간주
    ※ declare_failure 선택 시 reasoning에 반드시 포함:
       1. 찾으려 했던 요소가 무엇인지 (목표 기준)
       2. 상 tier에 있던 요소들이 왜 목표와 무관한지
    ※ 링크/버튼 텍스트가 목표에서 언급된 항목과 의미적으로 일치하면 클릭 가능 (대소문자 무시)
    ※ 현재 페이지가 목표와 관련 없다고 판단되면 go_back 선택 가능
    ※ 목표에 순서가 있는 경우, 반드시 순서대로 수행. 이전 단계가 최근_행동에 없으면 먼저 수행할 것
5. 목표와 무관한 요소는 절대 클릭 금지

**{current_tier} tier 요소** (탐색 대상):
{visible_text}

{중_label}:
{중_text}

{하_label}:
{하_text}

**응답 형식**:
{{
    "found": true/false,
    "found_tier": "상"/"중"/"하"/null,
    "element_id": 0,
    "action_type": "click" / "fill" / "declare_success" / "declare_failure",
    "text": "입력할 텍스트 (fill일 때만, 나머지는 생략)",
    "reasoning": "..."
}}

**action_type**:
- "click": 목표 요소 클릭
- "fill": input 요소에 텍스트 입력
- "declare_success": 성공 조건 충족 시
- "declare_failure": {current_tier} tier에서 목표 없음

**경고**: 요소가 없거나 클릭만 했다고 declare_success 하지 말 것. 반드시 성공 조건이 실제로 충족된 경우만

**주의**: found=true는 반드시 {current_tier} tier에서만 가능
"""
    return prompt


def build_incremental_prompt(
    visible_elements: List[StandardUINode],
    all_layers: List[Dict],
    frozen_section_state: Dict,
    current_tier: str,
    goal: str,
    recent_actions: List[Dict],
    explored_tiers: List[str] = None,
    success_condition: str = None,
    verify_fail_reason: str = None
) -> str:
    """
    증분 레이어 탐색용 프롬프트 생성
    """
    # 1. 최근 행동
    action_lines = []
    for action in recent_actions:
        step = action.get('step', '?')
        action_type = action.get('action', '?')
        elem_id = action.get('element_id', '?')
        elem_text = action.get('element_text', '?')
        action_lines.append(f"Step {step}: {action_type} {elem_id} '{elem_text}'")
    actions_text = "\n".join(action_lines) if action_lines else "(없음)"
    
    # 2. 기존 섹션 코드
    section_name = frozen_section_state['section_name']
    section_tier = frozen_section_state['tier']
    section_visible = frozen_section_state['visible_elements']
    
    section_lines = []
    for elem in section_visible:
        section_lines.append(f"  - {format_element(elem)}")
    section_text = "\n".join(section_lines) if section_lines else "  (없음)"
    
    base_section_code = f"""<기존_{section_name}_섹션> (탐색 중단된 위치: {section_tier} tier)
{section_text}
</기존_{section_name}_섹션>"""
    
    # 3. 이전 증분 맥락 (trigger 체인만)
    if len(all_layers) > 1:
        previous_triggers = []
        for i, layer in enumerate(all_layers[:-1]):
            order = i + 1
            trigger = layer['trigger']
            parts = trigger.split('|')
            if len(parts) >= 3:
                action = parts[0]
                elem_id = parts[1]
                elem_text = parts[2]
                previous_triggers.append(f"  {order}. {elem_id} '{elem_text}' {action}")
            else:
                previous_triggers.append(f"  {order}. {trigger}")
        
        context_chain = "\n".join(previous_triggers)
        previous_context = f"""<이전_증분_맥락>
{context_chain}
</이전_증분_맥락>"""
    else:
        previous_context = ""
    
    # 4. 현재 증분 레이어 (최상위만)
    if all_layers:
        top_layer = all_layers[-1]
        trigger = top_layer['trigger']
        nodes = top_layer['nodes']
        
        parts = trigger.split('|')
        if len(parts) >= 3:
            action = parts[0]
            elem_id = parts[1]
            elem_text = parts[2]
            trigger_text = f"{elem_id} '{elem_text}' {action}으로 열림"
        else:
            trigger_text = trigger
        
        tier_상 = [n for n in nodes if n.properties.get('tier') == '상']
        tier_중 = [n for n in nodes if n.properties.get('tier') == '중']
        tier_하 = [n for n in nodes if n.properties.get('tier') == '하']
        
        explored = explored_tiers or []
        layer_lines = []
        
        if tier_상:
            layer_lines.append("  [상 tier]")
            for node in tier_상:
                layer_lines.append(f"    - {format_element(node)}")

        중_label = "  [중 tier (탐색 완료)]" if '중' in explored else "  [중 tier 구조] (미탐색)"
        하_label = "  [하 tier (탐색 완료)]" if '하' in explored else "  [하 tier 구조] (미탐색)"
        중_content = summarize_tier(nodes, '중') if '중' in explored else count_tier(nodes, '중')
        하_content = summarize_tier(nodes, '하') if '하' in explored else count_tier(nodes, '하')

        layer_lines.append(중_label)
        layer_lines.append(f"    {중_content}")
        layer_lines.append(하_label)
        layer_lines.append(f"    {하_content}")
        
        layer_text = "\n".join(layer_lines) if layer_lines else "  (없음)"
        
        current_layer_code = f"""<현재_증분> ({trigger_text})
{layer_text}
</현재_증분>"""
    else:
        current_layer_code = ""
        
    # 5. 현재 tier 요소 바로 위에 추가
    tier_map = {'상': '중/하', '중': '상/하', '하': '상/중'}
    excluded = tier_map.get(current_tier, '다른')
    
    # 5. 현재 tier 요소
    tier_lines = []
    for i, elem in enumerate(visible_elements):
        tier_lines.append(f"[{i}] {format_element(elem)}")
    tier_text = "\n".join(tier_lines) if tier_lines else "(없음)"
    
    # success_condition 섹션
    if success_condition:
        if verify_fail_reason:
            success_text = f"""
        **성공 조건**: {success_condition}
        """
        else:
            success_text = f"""
        **성공 조건**: {success_condition}

        **중요**: 최근_행동에서 목표를 달성했다면 즉시 declare_success 호출
        """
        
    else:
        success_text = ""
    
    verify_text = ""
    if verify_fail_reason:
        verify_text = f"\n<주의>\n목표 미달성: {verify_fail_reason}\n아직 탐색을 계속하세요. 성공 선언하지 마세요.\n</주의>"
    
    # 6. 프롬프트 조립
    prompt = f"""
당신은 증분 레이어(모달/드롭다운)를 탐색 중입니다.

**목표**: {goal}
{success_text}
{verify_text}
**최근 행동**:
{actions_text}

{base_section_code}

{previous_context}

{current_layer_code}

**현재 선택 가능** ({current_tier} tier):
{tier_text}

**규칙**:
1. {current_tier} tier 요소만 선택 가능
2. {excluded} tier 요소는 선택 불가
3. element_id는 [인덱스] 번호 사용
4. action_type:
   - "click": 목표와 직접 관련된 요소 클릭
   - "fill": input 요소에 텍스트 입력
   - "close": 증분 레이어 닫기
   - "declare_success": 성공 조건 충족 시
   - "declare_failure": 목표와 관련된 요소 없을 때
   ※ 목표에 순서가 있는 경우, 반드시 순서대로 수행. 이전 단계가 최근_행동에 없으면 먼저 수행할 것
5. 현재 tier 요소 중 목표와 직접 관련된 요소가 없으면 반드시 declare_failure
    ※ 목표 텍스트와 유사한 내용이 있는 경우, 해당 텍스트 근처의 클릭 가능한 요소(link, button, cursor:pointer인 container/text)도 목표와 관련된 요소로 간주
    ※ declare_failure 선택 시 reasoning에 반드시 포함:
       1. 찾으려 했던 요소가 무엇인지 (목표 기준)
       2. 상 tier에 있던 요소들이 왜 목표와 무관한지
    ※ 링크/버튼 텍스트가 목표에서 언급된 항목과 의미적으로 일치하면 클릭 가능 (대소문자 무시)
    ※ 현재 페이지가 목표와 관련 없다고 판단되면 go_back 선택 가능
6. 목표와 무관한 요소는 절대 클릭 금지

**경고**: 요소가 없거나 클릭만 했다고 declare_success 하지 말 것. 반드시 성공 조건이 실제로 충족된 경우만

**응답 형식**:
{{
    "found": true/false,
    "found_tier": "상"/"중"/"하"/null,
    "element_id": 0,
    "action_type": "click" / "fill" / "close" / "declare_success" / "declare_failure",
    "text": "입력할 텍스트 (fill일 때만, 나머지는 생략)",
    "reasoning": "..."
}}

**주의**: found=true는 반드시 {current_tier} tier에서만 가능
"""
    print(f"[PROMPT] tier={current_tier}, explored={explored_tiers}, prompt_len={len(prompt)}")
    
    return prompt