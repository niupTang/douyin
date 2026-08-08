def video_analysis_schema():
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "summary",
            "hook",
            "core_viewpoint",
            "pain_points",
            "viral_points",
            "reusable_points",
            "script_suggestions",
            "keywords",
            "structure",
        ],
        "properties": {
            "summary": {"type": "string"},
            "hook": {"type": "string"},
            "core_viewpoint": {"type": "string"},
            "pain_points": {"type": "array", "items": {"type": "string"}},
            "viral_points": {"type": "array", "items": {"type": "string"}},
            "reusable_points": {"type": "array", "items": {"type": "string"}},
            "script_suggestions": {"type": "array", "items": {"type": "string"}},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "structure": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["label", "content"],
                    "properties": {
                        "label": {"type": "string"},
                        "content": {"type": "string"},
                    },
                },
            },
        },
    }
