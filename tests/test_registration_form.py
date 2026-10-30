"""報名功能測試；真實寫入只使用 TEST_DATABASE_URL 連線專屬的暫存表。"""
from datetime import datetime, timedelta
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from activities.router import router as activities_router
from db import get_connection
from main import app
from routers.registration_form import router as form_router
from routers.registrations import router as list_router


def activity(is_open=True):
    now = datetime.now()
    return {"id": 1, "title": "測試活動", "description": "活動說明",
            "event_date": now + timedelta(days=3),
            "registration_deadline": now + timedelta(days=2), "is_open": is_open}


def cursor(row):
    return SimpleNamespace(fetchone=lambda: row)


@pytest.fixture
def form_client():
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = activity()
    app.dependency_overrides[get_connection] = lambda: connection
    try:
        with TestClient(app) as client:
            yield client, connection
    finally:
        app.dependency_overrides.clear()


def test_open_form_has_shared_navigation_and_correct_fields(form_client):
    client, _ = form_client
    response = client.get("/activities/1/register")
    assert response.status_code == 200
    assert "測試活動" in response.text and "主要導覽" in response.text
    assert 'name="name" maxlength="50"' in response.text
    assert 'name="phone" maxlength="20"' in response.text
    assert 'action="http://testserver/activities/1/register"' in response.text


@pytest.mark.parametrize("method", ["get", "post"])
def test_missing_activity_is_404(form_client, method):
    client, connection = form_client
    connection.execute.return_value.fetchone.return_value = None
    response = getattr(client, method)("/activities/999/register")
    assert response.status_code == 404
    assert "找不到此活動" in response.text


@pytest.mark.parametrize(
    ("name", "phone", "message"),
    [
        ("", "0900000000", "不可空白"),
        ("王小明", "", "不可空白"),
        ("  ", "  ", "不可空白"),
        ("名" * 51, "0900000000", "姓名最多50字"),
        ("王小明", "0" * 21, "聯絡電話最多20字"),
    ],
)
def test_invalid_fields_do_not_insert(form_client, name, phone, message):
    client, connection = form_client
    response = client.post("/activities/1/register", data={"name": name, "phone": phone})
    assert response.status_code == 400
    assert message in response.text
    assert connection.execute.call_count == 1


def test_input_is_trimmed_and_insert_is_parameterized(form_client):
    client, connection = form_client
    connection.execute.side_effect = [cursor(activity()), cursor({"id": 7})]
    response = client.post("/activities/1/register", data={"name": "  王小明  ", "phone": "  0912345678  "})
    assert response.status_code == 200 and "報名成功！" in response.text
    query, parameters = connection.execute.call_args.args
    assert parameters == ("王小明", "0912345678", 1)
    assert "registration_deadline > CURRENT_TIMESTAMP" in query
    assert "查看報名清單" in response.text


def test_closed_activity_hides_form_and_rejects_direct_post(form_client):
    client, connection = form_client
    connection.execute.return_value.fetchone.return_value = activity(False)
    response = client.get("/activities/1/register")
    assert response.status_code == 200 and "已截止報名" in response.text
    assert "<form" not in response.text
    connection.reset_mock()
    response = client.post("/activities/1/register", data={"name": "王小明", "phone": "0912345678"})
    assert response.status_code == 400 and "已截止報名" in response.text
    assert connection.execute.call_count == 1


def test_deadline_rechecked_by_insert(form_client):
    client, connection = form_client
    connection.execute.side_effect = [cursor(activity()), cursor(None)]
    response = client.post("/activities/1/register", data={"name": "王小明", "phone": "0912345678"})
    assert response.status_code == 400 and "已截止報名" in response.text
    assert "<form" not in response.text


def test_reflected_input_and_activity_title_are_escaped(form_client):
    client, connection = form_client
    row = activity()
    row["title"] = "<script>alert(1)</script>"
    connection.execute.return_value.fetchone.return_value = row
    response = client.post("/activities/1/register", data={"name": '<b>測試</b>', "phone": ""})
    assert response.status_code == 400
    assert "<script>" not in response.text and "&lt;script&gt;" in response.text
    assert 'value="&lt;b&gt;測試&lt;/b&gt;"' in response.text


def test_invalid_id_is_rejected_before_query(form_client):
    client, connection = form_client
    assert client.get("/activities/1%20OR%201=1/register").status_code == 422
    connection.execute.assert_not_called()


def test_form_template_works_from_other_directory(form_client, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    client, _ = form_client
    assert client.get("/activities/1/register").status_code == 200


def test_registration_form_supports_mount_prefix():
    host = FastAPI()
    for router in (activities_router, form_router, list_router):
        host.include_router(router, prefix="/team")
    connection = Mock()
    connection.execute.side_effect = [cursor(activity()), cursor(activity()), cursor({"id": 1})]
    host.dependency_overrides[get_connection] = lambda: connection
    with TestClient(host) as client:
        form = client.get("/team/activities/1/register")
        assert 'action="http://testserver/team/activities/1/register"' in form.text
        response = client.post("/team/activities/1/register", data={"name": "測試", "phone": "0900000000"})
    assert response.status_code == 200
    assert 'href="http://testserver/team/activities/1/registrations"' in response.text


@pytest.fixture
def postgres_form_client():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("未設定 TEST_DATABASE_URL，未驗證報名功能的真實 PostgreSQL 查詢")
    with psycopg.connect(url, row_factory=dict_row, autocommit=True) as connection:
        connection.execute("SET search_path TO pg_temp")
        schema = (Path(__file__).resolve().parents[1] / "database/schema.sql").read_text(encoding="utf-8-sig")
        connection.execute(schema.replace("CREATE TABLE ", "CREATE TEMP TABLE "))
        connection.execute("""
            INSERT INTO activities (title, event_date, registration_deadline)
            VALUES ('第一場活動', CURRENT_TIMESTAMP + INTERVAL '3 days', CURRENT_TIMESTAMP + INTERVAL '2 days'),
                   ('第二場活動', CURRENT_TIMESTAMP + INTERVAL '3 days', CURRENT_TIMESTAMP + INTERVAL '2 days'),
                   ('已截止活動', CURRENT_TIMESTAMP + INTERVAL '3 days', CURRENT_TIMESTAMP - INTERVAL '1 second')
        """)
        app.dependency_overrides[get_connection] = lambda: connection
        try:
            with TestClient(app) as client:
                yield client, connection
        finally:
            app.dependency_overrides.clear()


def signup(client, activity_id=1, name="王小明", phone="0912345678"):
    return client.post(f"/activities/{activity_id}/register", data={"name": name, "phone": phone})


def test_postgres_signup_is_visible_in_existing_registration_list(postgres_form_client):
    client, connection = postgres_form_client
    page = client.get("/activities")
    assert "/activities/1/register" in page.text and "/activities/3/register" not in page.text
    assert signup(client).status_code == 200
    row = connection.execute("SELECT activity_id, name, phone FROM registrations").fetchone()
    assert row == {"activity_id": 1, "name": "王小明", "phone": "0912345678"}
    response = client.get("/activities/1/registrations")
    assert response.status_code == 200 and "目前報名人數：1 人" in response.text
    assert "王小明" in response.text and "0912345678" in response.text


def test_postgres_duplicate_is_409_and_connection_remains_usable(postgres_form_client):
    client, connection = postgres_form_client
    assert signup(client).status_code == 200
    duplicate = signup(client, name="  王小明 ", phone=" 0912345678 ")
    assert duplicate.status_code == 409 and "已經報名過" in duplicate.text
    assert connection.execute("SELECT count(*) AS n FROM registrations").fetchone()["n"] == 1
    assert client.get("/activities/1/registrations").status_code == 200


def test_postgres_same_participant_can_join_other_activity_without_mixing_lists(postgres_form_client):
    client, _ = postgres_form_client
    assert signup(client, 1).status_code == 200
    assert signup(client, 2).status_code == 200
    assert signup(client, 2, name="第二位", phone="0922222222").status_code == 200
    first = client.get("/activities/1/registrations").text
    second = client.get("/activities/2/registrations").text
    assert "目前報名人數：1 人" in first and "第二位" not in first
    assert "目前報名人數：2 人" in second and "第二位" in second


@pytest.mark.parametrize(("name", "phone"), [("王小明", "0922222222"), ("另一位", "0912345678")])
def test_postgres_unique_key_uses_both_name_and_phone(postgres_form_client, name, phone):
    client, _ = postgres_form_client
    assert signup(client).status_code == 200
    assert signup(client, name=name, phone=phone).status_code == 200
    assert "目前報名人數：2 人" in client.get("/activities/1/registrations").text


def test_postgres_closed_activity_cannot_be_submitted(postgres_form_client):
    client, connection = postgres_form_client
    page = client.get("/activities/3/register")
    assert page.status_code == 200 and "<form" not in page.text
    assert signup(client, 3).status_code == 400
    assert connection.execute("SELECT count(*) AS n FROM registrations").fetchone()["n"] == 0


def test_postgres_deadline_can_expire_after_opening_form(postgres_form_client):
    client, connection = postgres_form_client
    assert "<form" in client.get("/activities/1/register").text
    connection.execute("UPDATE activities SET registration_deadline = CURRENT_TIMESTAMP WHERE id = 1")
    assert signup(client).status_code == 400
    assert connection.execute("SELECT count(*) AS n FROM registrations").fetchone()["n"] == 0


def test_postgres_missing_activity_never_inserts(postgres_form_client):
    client, connection = postgres_form_client
    assert client.get("/activities/999/register").status_code == 404
    assert signup(client, 999).status_code == 404
    assert connection.execute("SELECT count(*) AS n FROM registrations").fetchone()["n"] == 0


def test_postgres_schema_length_limits_and_literal_sql_input(postgres_form_client):
    client, connection = postgres_form_client
    assert signup(client, name="名" * 50, phone="0" * 20).status_code == 200
    assert signup(client, name="名" * 51).status_code == 400
    assert signup(client, phone="0" * 21).status_code == 400
    value = "x'); DROP TABLE registrations; --"
    assert signup(client, name=value).status_code == 200
    row = connection.execute("SELECT name FROM registrations WHERE name = %s", (value,)).fetchone()
    assert row["name"] == value
    assert connection.execute("SELECT count(*) AS n FROM registrations").fetchone()["n"] == 2
