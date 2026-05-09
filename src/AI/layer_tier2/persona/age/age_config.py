# src/AI/layer_tier2/persona/age/age_config.py
"""
연령별 인지 제약 수치 설정

앵커값 (논문 직접 근거):
- 20s, 50s, 70s 수치는 PDF 가중치 자료 기반 (Hou et al., 2022 등)

보간값 (선형 보간):
- 10s, 30s, 40s, 60s는 앵커값 간 선형 보간
- 근거: Nielsen Norman Group (2024), "Usability for Older Adults"
  "between the ages of 25 and 60, ability to use websites declines by 0.8% per year"
- 논문 명시: "interpolated linearly based on Nielsen Norman Group (2024) annual decline rate"
- 한계: 연령별 인지 변화는 영역마다 균일하지 않으며 개인차가 큼
  (Glisky, 2019; Craik, 2011 - The Handbook of Aging and Cognition)
"""

from typing import Dict, Any

# ==================== 앵커값 (논문 직접 근거) ====================

_ANCHORS: Dict[str, Dict[str, Any]] = {
    "20s": {
        "vision": {
            "min_font_size": 10,
            "min_contrast_ratio": 3.0,
            "min_line_height": 1.2,
            "min_letter_spacing": 0.0,
            "min_font_weight": 300,
            "icon_only_recognition_rate": 0.95,
            "color_only_recognition_rate": 0.90,
        },
        "visual_field": {
            "effective_field_ratio": 1.0,
            "below_fold_recognition_rate": 0.9,
            "edge_recognition_rate": 0.85,
            "fixed_header_interference": 0.0,
        },
        "attention": {
            "simultaneous_elements": 8,
            "visual_noise_tolerance": 5,
            "animation_tolerance": 3,
            "banner_hijack_probability": 0.2,
        },
        "working_memory": {
            "memory_slots": 7,
            "retention_duration": 20,
            "prev_screen_retention_rate": 0.85,
            "input_retention_rate": 0.9,
        },
        "decision": {
            "max_options": 12,
            "selection_delay_probability": 0.1,
            "selection_avoidance_probability": 0.05,
            "similar_option_confusion_probability": 0.1,
        },
        "navigation": {
            "max_depth": 4,
            "max_menu_nesting": 3,
            "breadcrumb_comprehension_rate": 0.8,
            "path_recovery_rate": 0.9,
        },
        "action_accuracy": {
            "click_accuracy": 0.95,
            "min_button_size": 32,
            "adjacent_misclick_probability": 0.05,
            "retry_accuracy_gain": 0.1,
        },
        "temporal": {
            "avg_reaction_time": 1.2,
            "max_wait_time": 10,
            "loading_failure_recognition_rate": 0.1,
            "auto_transition_failure_rate": 0.1,
        },
        "error_recovery": {
            "error_recognition_rate": 0.9,
            "error_message_comprehension_rate": 0.85,
            "avg_recovery_attempts": 8,
            "repeated_error_probability": 0.1,
        },
        "abandonment": {
            "frustration_threshold": 6,
            "abandonment_threshold": 8,
            "avg_time_before_abandon": 120,
            "system_blame_probability": 0.2,
        },
        "digital_familiarity": {
            "icon_recognition_rate": 0.9,
            "hidden_menu_recognition_rate": 0.85,
            "new_pattern_learning_rate": 0.8,
            "gesture_misunderstanding_probability": 0.1,
            "familiar_ui_dependency": 0.2,
        },
        "risk_aversion": {
            "click_hesitation_probability": 0.1,
            "warning_stop_rate": 0.2,
            "mistake_avoidance_rate": 0.05,
            "new_feature_trial_rate": 0.85,
            "verified_only_rate": 0.2,
        },
        "self_efficacy": {
            "retry_after_failure_probability": 0.9,
            "self_solve_rate": 0.85,
            "self_blame_rate": 0.7,
            "guidance_utilization_rate": 0.8,
            "quick_abandon_probability": 0.1,
        },
        "distraction": {
            "notification_interrupt_probability": 0.15,
            "task_recovery_rate": 0.85,
            "modal_confusion_rate": 0.2,
            "multitask_success_rate": 0.8,
            "post_interrupt_abandon_probability": 0.05,
        },
    },
    "50s": {
        "vision": {
            "min_font_size": 13,
            "min_contrast_ratio": 4.5,
            "min_line_height": 1.4,
            "min_letter_spacing": 0.02,
            "min_font_weight": 400,
            "icon_only_recognition_rate": 0.6,
            "color_only_recognition_rate": 0.5,
        },
        "visual_field": {
            "effective_field_ratio": 0.75,
            "below_fold_recognition_rate": 0.6,
            "edge_recognition_rate": 0.5,
            "fixed_header_interference": 0.2,
        },
        "attention": {
            "simultaneous_elements": 5,
            "visual_noise_tolerance": 3,
            "animation_tolerance": 1,
            "banner_hijack_probability": 0.5,
        },
        "working_memory": {
            "memory_slots": 5,
            "retention_duration": 12,
            "prev_screen_retention_rate": 0.6,
            "input_retention_rate": 0.7,
        },
        "decision": {
            "max_options": 8,
            "selection_delay_probability": 0.4,
            "selection_avoidance_probability": 0.3,
            "similar_option_confusion_probability": 0.4,
        },
        "navigation": {
            "max_depth": 3,
            "max_menu_nesting": 2,
            "breadcrumb_comprehension_rate": 0.5,
            "path_recovery_rate": 0.6,
        },
        "action_accuracy": {
            "click_accuracy": 0.8,
            "min_button_size": 40,
            "adjacent_misclick_probability": 0.2,
            "retry_accuracy_gain": 0.05,
        },
        "temporal": {
            "avg_reaction_time": 2.0,
            "max_wait_time": 6,
            "loading_failure_recognition_rate": 0.4,
            "auto_transition_failure_rate": 0.4,
        },
        "error_recovery": {
            "error_recognition_rate": 0.6,
            "error_message_comprehension_rate": 0.5,
            "avg_recovery_attempts": 5,
            "repeated_error_probability": 0.4,
        },
        "abandonment": {
            "frustration_threshold": 4,
            "abandonment_threshold": 5,
            "avg_time_before_abandon": 80,
            "system_blame_probability": 0.5,
        },
        "digital_familiarity": {
            "icon_recognition_rate": 0.6,
            "hidden_menu_recognition_rate": 0.55,
            "new_pattern_learning_rate": 0.5,
            "gesture_misunderstanding_probability": 0.4,
            "familiar_ui_dependency": 0.6,
        },
        "risk_aversion": {
            "click_hesitation_probability": 0.4,
            "warning_stop_rate": 0.5,
            "mistake_avoidance_rate": 0.3,
            "new_feature_trial_rate": 0.45,
            "verified_only_rate": 0.6,
        },
        "self_efficacy": {
            "retry_after_failure_probability": 0.6,
            "self_solve_rate": 0.5,
            "self_blame_rate": 0.4,
            "guidance_utilization_rate": 0.55,
            "quick_abandon_probability": 0.4,
        },
        "distraction": {
            "notification_interrupt_probability": 0.45,
            "task_recovery_rate": 0.5,
            "modal_confusion_rate": 0.5,
            "multitask_success_rate": 0.45,
            "post_interrupt_abandon_probability": 0.3,
        },
    },
    "70s": {
        "vision": {
            "min_font_size": 16,
            "min_contrast_ratio": 7.0,
            "min_line_height": 1.6,
            "min_letter_spacing": 0.05,
            "min_font_weight": 500,
            "icon_only_recognition_rate": 0.2,
            "color_only_recognition_rate": 0.1,
        },
        "visual_field": {
            "effective_field_ratio": 0.5,
            "below_fold_recognition_rate": 0.2,
            "edge_recognition_rate": 0.2,
            "fixed_header_interference": 0.4,
        },
        "attention": {
            "simultaneous_elements": 3,
            "visual_noise_tolerance": 1,
            "animation_tolerance": 0,
            "banner_hijack_probability": 0.8,
        },
        "working_memory": {
            "memory_slots": 3,
            "retention_duration": 6,
            "prev_screen_retention_rate": 0.3,
            "input_retention_rate": 0.4,
        },
        "decision": {
            "max_options": 4,
            "selection_delay_probability": 0.7,
            "selection_avoidance_probability": 0.6,
            "similar_option_confusion_probability": 0.7,
        },
        "navigation": {
            "max_depth": 2,
            "max_menu_nesting": 1,
            "breadcrumb_comprehension_rate": 0.2,
            "path_recovery_rate": 0.3,
        },
        "action_accuracy": {
            "click_accuracy": 0.6,
            "min_button_size": 48,
            "adjacent_misclick_probability": 0.4,
            "retry_accuracy_gain": 0.0,
        },
        "temporal": {
            "avg_reaction_time": 3.5,
            "max_wait_time": 4,
            "loading_failure_recognition_rate": 0.7,
            "auto_transition_failure_rate": 0.8,
        },
        "error_recovery": {
            "error_recognition_rate": 0.3,
            "error_message_comprehension_rate": 0.2,
            "avg_recovery_attempts": 3,
            "repeated_error_probability": 0.7,
        },
        "abandonment": {
            "frustration_threshold": 2,
            "abandonment_threshold": 3,
            "avg_time_before_abandon": 40,
            "system_blame_probability": 0.8,
        },
        "digital_familiarity": {
            "icon_recognition_rate": 0.3,
            "hidden_menu_recognition_rate": 0.25,
            "new_pattern_learning_rate": 0.2,
            "gesture_misunderstanding_probability": 0.7,
            "familiar_ui_dependency": 0.9,
        },
        "risk_aversion": {
            "click_hesitation_probability": 0.75,
            "warning_stop_rate": 0.8,
            "mistake_avoidance_rate": 0.6,
            "new_feature_trial_rate": 0.15,
            "verified_only_rate": 0.9,
        },
        "self_efficacy": {
            "retry_after_failure_probability": 0.3,
            "self_solve_rate": 0.2,
            "self_blame_rate": 0.15,
            "guidance_utilization_rate": 0.25,
            "quick_abandon_probability": 0.75,
        },
        "distraction": {
            "notification_interrupt_probability": 0.8,
            "task_recovery_rate": 0.2,
            "modal_confusion_rate": 0.8,
            "multitask_success_rate": 0.15,
            "post_interrupt_abandon_probability": 0.65,
        },
    },
}


# ==================== 보간 함수 ====================

def _interpolate(v_low: float, v_high: float, ratio: float) -> float:
    """
    두 앵커값 사이 선형 보간
    ratio: 0.0 = low, 1.0 = high
    """
    result = v_low + (v_high - v_low) * ratio
    # int 계열 수치 처리 (font_size, slots 등)
    if isinstance(v_low, int) and isinstance(v_high, int):
        return round(result)
    return round(result, 3)


def _interpolate_config(low: dict, high: dict, ratio: float) -> dict:
    """카테고리별 dict 재귀 보간"""
    result = {}
    for category, values in low.items():
        result[category] = {}
        for key, v_low in values.items():
            v_high = high[category][key]
            result[category][key] = _interpolate(v_low, v_high, ratio)
    return result


# ==================== 보간값 생성 ====================
# 근거: Nielsen Norman Group (2024), "Usability for Older Adults"
# "between the ages of 25 and 60, ability to use websites declines by 0.8% per year"
# 한계: Glisky (2019) - 인지 변화는 영역마다 균일하지 않으며 개인차가 큼
# 논문 명시: "interpolated linearly based on Nielsen Norman Group (2024) annual decline rate"

_INTERPOLATED: Dict[str, dict] = {
    # 10대: 20대와 동일 (논문상 차이 미미)
    "10s": _ANCHORS["20s"],

    # 30대: 20s~50s 구간에서 (30-20)/(50-20) = 1/3 지점
    "30s": _interpolate_config(_ANCHORS["20s"], _ANCHORS["50s"], 1/3),

    # 40대: 20s~50s 구간에서 (40-20)/(50-20) = 2/3 지점
    "40s": _interpolate_config(_ANCHORS["20s"], _ANCHORS["50s"], 2/3),

    # 60대: 50s~70s 구간에서 (60-50)/(70-50) = 1/2 지점
    "60s": _interpolate_config(_ANCHORS["50s"], _ANCHORS["70s"], 1/2),
}

# 전체 통합
AGE_CONFIGS: Dict[str, dict] = {**_ANCHORS, **_INTERPOLATED}


# ==================== 공개 API ====================

def get_age_config(age_group: str) -> dict:
    """
    연령대별 인지 제약 수치 반환

    Args:
        age_group: "10s" | "20s" | "30s" | "40s" | "50s" | "60s" | "70s"

    Returns:
        카테고리별 수치 dict

    Example:
        config = get_age_config("70s")
        config["vision"]["min_font_size"]  # 16
    """
    if age_group not in AGE_CONFIGS:
        raise ValueError(f"Unknown age group: {age_group}. Use: {list(AGE_CONFIGS.keys())}")
    return AGE_CONFIGS[age_group]