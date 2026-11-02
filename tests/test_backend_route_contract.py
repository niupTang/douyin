from sau_backend import app


def test_migrated_routes_keep_their_urls_and_methods():
    methods_by_path = {}
    for rule in app.url_map.iter_rules():
        methods_by_path.setdefault(rule.rule, set()).update(rule.methods)

    expected = {
        "/login": {"GET"},
        "/uploadSave": {"POST"},
        "/postVideo": {"POST"},
        "/benchmark/douyin/accounts": {"GET", "POST"},
        "/own/douyin/import": {"POST"},
        "/own/douyin/export/run": {"POST"},
        "/idea-radar/douyin/videos/<int:video_id>/analyze": {"POST"},
        "/account-diagnosis/reports": {"GET"},
        "/mcp/invoke": {"POST"},
        "/runtime/license/install": {"POST"},
        "/settings/agent-models": {"GET", "POST"},
    }
    for path, methods in expected.items():
        assert methods <= methods_by_path.get(path, set()), path
