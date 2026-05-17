from app.api.contracts import EndpointInventory
from app.api.main import app
from app.web.ui_inventory import UIViewInventory


def test_pass14_required_api_endpoints_are_registered():
    registered = set()
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        for method in methods:
            if method in {"GET", "POST"} and path.startswith("/api"):
                registered.add((method, path))

    report = EndpointInventory().compare_to_registered(registered)

    assert report["status"] == "pass", report
    assert report["required_count"] >= 15


def test_pass14_required_ui_views_exist():
    report = UIViewInventory("app/web/pages").validate()

    assert report["status"] == "pass", report
    assert report["required_count"] >= 14
