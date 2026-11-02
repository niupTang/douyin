import sau_backend


def test_admin_user_routes_are_not_registered():
    routes = {rule.rule for rule in sau_backend.app.url_map.iter_rules()}

    assert "/admin/users" not in routes
    assert "/admin/users/<int:user_id>" not in routes
