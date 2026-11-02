import sau_backend


def test_distribution_does_not_expose_new_agent_services():
    paths = {rule.rule for rule in sau_backend.app.url_map.iter_rules()}
    assert not any(path.startswith(("/api/agents", "/api/agent-runs", "/api/chat", "/api/ai")) for path in paths)


def test_script_generation_keeps_existing_structured_model_call(monkeypatch):
    calls = []

    def generate(task_name, prompt, schema):
        calls.append((task_name, prompt, schema))
        return {"script": "generated"}

    monkeypatch.setattr(sau_backend, "run_structured", generate)
    result = sau_backend.generate_identity_script({}, {})
    assert result == {"script": "generated"}
    assert calls[0][0] == "scriptGeneration"
