from backend_app.modules.mcp_server.handlers import create_mcp_handlers


def test_review_uses_all_accounts_when_no_account_is_selected():
    requested_limits = []

    def list_all_videos(limit):
        requested_limits.append(limit)
        return [
            {"id": 1, "title": "A", "play_count": 10},
            {"id": 2, "title": "B", "play_count": 20},
        ]

    handlers = create_mcp_handlers(
        None, None, None, None, None, None, None, None,
        list_all_videos, None,
    )()

    result = handlers["review_published_content"]({"work_id": 2, "limit": 5})

    assert requested_limits == [5]
    assert result["summary"]["total"] == 1
    assert result["videos"][0]["id"] == 2
