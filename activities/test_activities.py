"""UI 與共用 app 的整合測試；不在匯入時連線或寫入正式資料庫。"""
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path
import os
import re
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from activities.router import router as activities_router
from db import get_connection
from main import app
from routers.registrations import router as registrations_router


def activity_form(**changes):
    now = datetime.now().replace(second=0, microsecond=0)
    form = {
        "title": "測試-可報名<b>", "description": "說明A",
        "event_date": (now + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M"),
        "registration_deadline": (now + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M"),
    }
    form.update(changes)
    return form


@pytest.fixture
def ui_client():
    connection = Mock()
    connection.execute.return_value.fetchall.return_value = []
    app.dependency_overrides[get_connection] = lambda: connection
    try:
        with TestClient(app) as client:
            yield client, connection
    finally:
        app.dependency_overrides.clear()


def test_home_redirects_to_activity_list(ui_client):
    client, _ = ui_client
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert urlsplit(response.headers["location"]).path == "/activities"


def test_new_activity_form_and_shared_navigation(ui_client):
    client, connection = ui_client
    response = client.get("/activities/new")
    assert response.status_code == 200
    assert "活動名稱" in response.text and "主要導覽" in response.text
    assert 'action="http://testserver/activities"' in response.text
    connection.execute.assert_not_called()


def test_empty_activity_list(ui_client):
    client, _ = ui_client
    response = client.get("/activities")
    assert response.status_code == 200
    assert "目前還沒有任何活動" in response.text


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"title": "   "}, "請填寫活動名稱"),
        ({"title": "a" * 101}, "活動名稱不可超過 100 字"),
        ({"event_date": ""}, "請選擇活動日期"),
        ({"registration_deadline": ""}, "請選擇報名截止時間"),
        ({"event_date": "亂填"}, "活動日期格式不正確"),
        ({"registration_deadline": "亂填"}, "報名截止時間格式不正確"),
        ({"registration_deadline": "9999-12-31T23:59"}, "報名截止時間不可晚於活動日期"),
    ],
)
def test_invalid_form_preserves_input_without_insert(ui_client, changes, message):
    client, connection = ui_client
    response = client.post("/activities", data=activity_form(**changes))
    assert response.status_code == 400
    assert message in response.text
    if "title" not in changes:
        assert 'value="測試-可報名&lt;b&gt;"' in response.text
    connection.execute.assert_not_called()


def test_completely_empty_form_returns_400(ui_client):
    client, connection = ui_client
    assert client.post("/activities", data={}).status_code == 400
    connection.execute.assert_not_called()


def test_create_uses_parameters_and_redirects(ui_client):
    client, connection = ui_client
    connection.execute.return_value.fetchone.return_value = {"id": 42}
    response = client.post("/activities", data=activity_form(description="  "), follow_redirects=False)
    assert response.status_code == 303
    assert parse_qs(urlsplit(response.headers["location"]).query) == {"created": ["42"]}
    query, parameters = connection.execute.call_args.args
    assert "VALUES (%s, %s, %s, %s)" in query
    assert parameters[0] == "測試-可報名<b>" and parameters[1] is None
    assert isinstance(parameters[2], datetime)


def test_ui_template_path_is_independent_of_working_directory(ui_client, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    client, _ = ui_client
    assert client.get("/activities").status_code == 200
    assert client.get("/activities/new").status_code == 200


def test_routers_support_mount_prefix():
    host = FastAPI()
    host.include_router(activities_router, prefix="/team")
    host.include_router(registrations_router, prefix="/team")
    with TestClient(host) as client:
        response = client.get("/team/activities/new")
    assert response.status_code == 200
    assert 'action="http://testserver/team/activities"' in response.text
    assert 'href="http://testserver/team/activities"' in response.text


def test_registration_router_still_works_without_ui_router():
    host = FastAPI()
    host.include_router(registrations_router)
    connection = Mock()
    connection.execute.return_value.fetchall.return_value = [
        {"activity_id": 1, "activity_title": "獨立掛載", "registration_id": None, "name": None, "phone": None}
    ]
    host.dependency_overrides[get_connection] = lambda: connection
    with TestClient(host) as client:
        response = client.get("/activities/1/registrations")
    assert response.status_code == 200
    assert "目前尚無報名資料" in response.text


def test_old_dev_app_uses_shared_app():
    from activities.dev_app import app as dev_app
    assert dev_app is app


@pytest.fixture
def postgres_ui_client():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("未設定 TEST_DATABASE_URL，未驗證 UI 的真實 PostgreSQL 整合")
    with psycopg.connect(database_url, row_factory=dict_row, autocommit=True) as connection:
        # 所有新增活動、報名者都只寫入此連線的 TEMP 表，關閉後自動移除。
        connection.execute("SET search_path TO pg_temp")
        schema = (Path(__file__).resolve().parents[1] / "database/schema.sql").read_text(encoding="utf-8-sig")
        connection.execute(schema.replace("CREATE TABLE ", "CREATE TEMP TABLE "))
        app.dependency_overrides[get_connection] = lambda: connection
        try:
            with TestClient(app) as client:
                yield client, connection
        finally:
            app.dependency_overrides.clear()


def create_activity(client, **changes):
    response = client.post("/activities", data=activity_form(**changes), follow_redirects=False)
    assert response.status_code == 303
    return int(parse_qs(urlsplit(response.headers["location"]).query)["created"][0])


def test_postgres_create_preserves_dates_description_and_success_message(postgres_ui_client):
    client, connection = postgres_ui_client
    form = activity_form()
    activity_id = create_activity(client)
    row = connection.execute("SELECT * FROM activities WHERE id = %s", (activity_id,)).fetchone()
    assert row["title"] == form["title"] and row["description"] == "說明A"
    assert row["event_date"] == datetime.strptime(form["event_date"], "%Y-%m-%dT%H:%M")
    assert row["registration_deadline"] == datetime.strptime(form["registration_deadline"], "%Y-%m-%dT%H:%M")
    response = client.get(f"/activities?created={activity_id}")
    assert response.status_code == 200 and "已新增活動" in response.text
    assert "測試-可報名&lt;b&gt;" in response.text and "測試-可報名<b>" not in response.text


def test_postgres_blank_description_and_empty_registration_list(postgres_ui_client):
    client, connection = postgres_ui_client
    activity_id = create_activity(client, description="  ")
    assert connection.execute("SELECT description FROM activities WHERE id = %s", (activity_id,)).fetchone()["description"] is None
    response = client.get(f"/activities/{activity_id}/registrations")
    assert response.status_code == 200
    assert "目前報名人數：0 人" in response.text and "目前尚無報名資料" in response.text


def test_postgres_open_closed_status_and_all_page_links(postgres_ui_client):
    client, _ = postgres_ui_client
    open_id = create_activity(client)
    closed_id = create_activity(client, title="測試-已截止", registration_deadline="2000-01-01T00:00")
    response = client.get("/activities")
    assert "可報名" in response.text and "已截止" in response.text
    assert "報名功能尚未接入" not in response.text
    assert f"/activities/{open_id}/register" in response.text
    assert f"/activities/{closed_id}/register" not in response.text
    assert f"/activities/{open_id}/registrations" in response.text
    assert f"/activities/{closed_id}/registrations" in response.text
    for link in set(re.findall(r'href="([^"]+)"', response.text)):
        assert client.get(unescape(link)).status_code == 200


def test_postgres_ui_to_registration_list_keeps_activity_data_separate(postgres_ui_client):
    client, connection = postgres_ui_client
    first_id = create_activity(client, title="第一場活動")
    second_id = create_activity(client, title="第二場活動")
    connection.execute(
        "INSERT INTO registrations (activity_id, name, phone) VALUES (%s, %s, %s), (%s, %s, %s)",
        (first_id, "第一場報名者", "0911111111", second_id, "第二場報名者", "0922222222"),
    )
    first = client.get(f"/activities/{first_id}/registrations")
    second = client.get(f"/activities/{second_id}/registrations")
    assert "第一場報名者" in first.text and "0911111111" in first.text
    assert "第二場報名者" not in first.text and "0922222222" not in first.text
    assert "第二場報名者" in second.text and "第一場報名者" not in second.text
    assert "目前報名人數：1 人" in first.text and "目前報名人數：1 人" in second.text
    assert client.get("/activities/999/registrations").status_code == 404


def test_postgres_invalid_form_does_not_write(postgres_ui_client):
    client, connection = postgres_ui_client
    before = connection.execute("SELECT count(*) AS n FROM activities").fetchone()["n"]
    assert client.post("/activities", data=activity_form(title=" ")).status_code == 400
    assert connection.execute("SELECT count(*) AS n FROM activities").fetchone()["n"] == before
