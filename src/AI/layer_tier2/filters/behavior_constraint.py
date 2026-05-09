# src/AI/layer_tier2/persona/age/age_config.py

AGE_CONFIGS = {
    "20s": {
        "vision": {},
        "visual_field": {},
        "attention": {},
        "working_memory": {},
        "decision": {},
        "navigation": {},
        "action_accuracy": {},
        "temporal": {},
        "error_recovery": {},
        "abandonment": {},
        "digital_familiarity": {},
        "risk_aversion": {},
        "self_efficacy": {},
        "distraction": {},
    },
    "50s": {},
    "70s": {},
}

def get_age_config(age_group: str) -> dict:
    if age_group not in AGE_CONFIGS:
        raise ValueError(f"Unknown age group: {age_group}. Use '20s', '50s', '70s'")
    return AGE_CONFIGS[age_group]