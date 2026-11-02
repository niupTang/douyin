def own_report_schema():
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "summary",
            "traffic_conclusion",
            "diagnosis_layers",
            "key_metrics",
            "low_performing_videos",
            "improvement_actions",
            "confidence",
        ],
        "properties": {
            "summary": {"type": "string"},
            "traffic_conclusion": {"type": "string"},
            "diagnosis_layers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["layer", "judgment", "reason"],
                    "properties": {
                        "layer": {"type": "string"},
                        "judgment": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                },
            },
            "key_metrics": {"type": "array", "items": {"type": "string"}},
            "low_performing_videos": {"type": "array", "items": {"type": "string"}},
            "improvement_actions": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "string"},
        },
    }


def benchmark_report_schema():
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "summary",
            "viral_conclusion",
            "per_video_classification",
            "key_metrics",
            "takeaways",
            "confidence",
        ],
        "properties": {
            "summary": {"type": "string"},
            "viral_conclusion": {"type": "string"},
            "per_video_classification": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["title", "classification", "reason"],
                    "properties": {
                        "title": {"type": "string"},
                        "classification": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                },
            },
            "key_metrics": {"type": "array", "items": {"type": "string"}},
            "takeaways": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "string"},
        },
    }
