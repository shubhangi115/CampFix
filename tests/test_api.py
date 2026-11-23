"""Integration test against a running CampFix API and a disposable MySQL database."""

import os
from uuid import uuid4

import pytest
import requests


def test_campus_complaint_workflow():
    base = os.getenv("CAMPFIX_TEST_URL")
    admin_email = os.getenv("CAMPFIX_TEST_ADMIN_EMAIL")
    admin_password = os.getenv("CAMPFIX_TEST_ADMIN_PASSWORD")
    if not all([base, admin_email, admin_password]):
        pytest.skip("Set CAMPFIX_TEST_URL and the test admin credentials to run against a test database.")

    def api(method, path, expected, token=None, **kwargs):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = requests.request(method, f"{base.rstrip('/')}{path}", headers=headers, timeout=10, **kwargs)
        assert response.status_code == expected, (method, path, response.status_code, response.text)
        return response.json() if response.content else None

    def register():
        suffix = uuid4().hex[:12]
        credentials = {"email": f"student-{suffix}@example.com", "password": "Campus-passphrase-813"}
        profile = dict(credentials, full_name=f"Student {suffix}", roll_number=f"TEST-{suffix}",
                       department="Computer Science", confirm_password=credentials["password"])
        api("POST", "/auth/student/register", 201, json=profile)
        api("POST", "/auth/student/register", 409, json=profile)
        token = api("POST", "/auth/student/login", 200, json=credentials)["access_token"]
        return token, credentials, profile

    assert api("GET", "/openapi.json", 200)["info"]["title"] == "CampFix API"
    first, credentials, profile = register()
    second, _, _ = register()
    administrator = api(
        "POST", "/auth/admin/login", 200, json={"email": admin_email, "password": admin_password},
    )["access_token"]

    api("POST", "/auth/student/login", 401, json=dict(credentials, password="incorrect"))
    api("GET", "/complaints", 401)
    api("GET", "/admin/students", 403, first)
    api("GET", "/complaints", 403, administrator)
    assert api("GET", "/auth/me", 200, first)["roll_number"] == profile["roll_number"]

    payload = {"title": profile["roll_number"], "category": "Cleanliness",
               "description": "Needs cleaning.", "location": "IT Building"}
    api("POST", "/complaints", 422, first, json=dict(payload, category="Invalid category"))
    item = api("POST", "/complaints", 201, first, json=payload)
    assert item["status"] == "Pending"
    assert item["reference"] == f'CMP-{item["complaint_id"]:04d}'
    path = f'/complaints/{item["complaint_id"]}'
    admin_path = f"/admin{path}"
    assert api("GET", path, 200, first)["title"] == payload["title"]
    api("GET", path, 404, second)
    api("PUT", path, 404, second, json=payload)
    api("DELETE", path, 404, second)
    updated = api("PUT", path, 200, first, json=dict(payload, location="Library"))
    assert updated["location"] == "Library"
    matches = api("GET", "/complaints", 200, first, params={
        "search": item["reference"], "category": "Cleanliness", "status": "Pending",
    })
    assert [row["complaint_id"] for row in matches] == [item["complaint_id"]]
    assert api("GET", "/complaints", 200, second, params={"search": payload["title"]}) == []

    api("PATCH", f"{admin_path}/status", 403, first, json={"status": "In Progress"})
    api("PATCH", f"{admin_path}/status", 409, administrator, json={"status": "Resolved"})
    api("PATCH", f"{admin_path}/status", 200, administrator, json={"status": "In Progress"})
    api("PUT", path, 409, first, json=payload)
    api("DELETE", path, 409, first)
    api("PATCH", f"{admin_path}/status", 200, administrator,
        json={"status": "Resolved", "resolution_note": "Floor cleaned."})
    record = api("GET", path, 200, first)
    assert record["status"] == "Resolved" and record["resolution_note"] == "Floor cleaned."
    assert [row["new_status"] for row in api("GET", admin_path, 200, administrator)["history"]] == [
        "In Progress", "Resolved",
    ]
    stats = api("GET", "/dashboard/stats", 200, first)
    assert stats["total"] == stats["by_status"]["Resolved"] == 1
    assert api("GET", "/dashboard/recent-complaints", 200, first)[0]["complaint_id"] == item["complaint_id"]
    assert "Cleanliness" in api("GET", "/admin/dashboard", 200, administrator)["by_category"]
    matches = api("GET", "/admin/complaints", 200, administrator, params={
        "roll_number": profile["roll_number"], "department": "Computer", "search": payload["title"],
    })
    assert len(matches) == 1 and matches[0]["roll_number"] == profile["roll_number"]
    students = api("GET", "/admin/students", 200, administrator,
                   params={"roll_number": profile["roll_number"]})
    assert len(students) == 1 and students[0]["complaint_count"] == 1
    assert "password_hash" not in students[0]

    removable = api("POST", "/complaints", 201, first, json=payload)
    delete_path = f'/complaints/{removable["complaint_id"]}'
    api("DELETE", delete_path, 204, first)
    api("GET", delete_path, 404, first)
    api("GET", f"/admin{delete_path}", 404, administrator)

    replacement = api("POST", "/auth/student/login", 200, json=credentials)["access_token"]
    api("GET", "/auth/me", 401, first)
    api("POST", "/auth/logout", 204, replacement)
    api("GET", "/auth/me", 401, replacement)
    api("POST", "/auth/logout", 204, administrator)
    api("GET", "/admin/students", 401, administrator)
