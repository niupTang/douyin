def identity_script_schema():
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "title", "cover_text", "script", "tags", "shooting_notes", "risk_notes",
        ],
        "properties": {
            "title": {"type": "string"},
            "cover_text": {"type": "string"},
            "script": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8},
            "shooting_notes": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 6},
            "risk_notes": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 6},
        },
    }
