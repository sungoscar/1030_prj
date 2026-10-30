from types import SimpleNamespace
from unittest.mock import Mock

import psycopg
import pytest
from fastapi.testclient import TestClient

import db
from main import app


@pytest.fixture
def client():
    connection = Mock()
    app.dependency_overrides[db.get_connection] = lambda: connection
    with TestClient(app) as test_client:
        yield test_client, connection
    app.dependency_overrides.clear()


def test_list_renders_count_phone_and_parameterized_query(client):
    test_client, connection = client
    connection.execute.return_value.fetchall.return_value = [
        {"activity_id": 7, "activity_title": "資料庫工作坊", "registration_id": 21, "name": "王小明", "phone": "0912345678"},
        {"activity_id": 7, "activity_title": "資料庫工作坊", "registration_id": 22, "name": "陳小華", "phone": "0223456789"},
    ]

    response = test_client.get("/activities/7/registrations")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "資料庫工作坊" in response.text
    assert "王小明" in response.text and "陳小華" in response.text
    assert "0912345678" in response.text and "0223456789" in response.text
    assert "目前報名人數：2 人" in response.text
    assert "<td>21</td>" in response.text and "<td>22</td>" in response.text
    query, parameters = connection.execute.call_args.args
    assert "WHERE a.id = %s" in query
    assert parameters == (7,)


def test_empty_activity(client):
    test_client, connection = client
    connection.execute.return_value.fetchall.return_value = [
        {"activity_id": 8, "activity_title": "尚未開放的活動", "registration_id": None, "name": None, "phone": None}
    ]
    response = test_client.get("/activities/8/registrations")
    assert response.status_code == 200
    assert "尚未開放的活動" in response.text
    assert "目前報名人數：0 人" in response.text
    assert "目前尚無報名資料" in response.text


def test_missing_activity_returns_404(client):
    test_client, connection = client
    connection.execute.return_value.fetchall.return_value = []
    response = test_client.get("/activities/999/registrations")
    assert response.status_code == 404
    assert response.json()["detail"] == "找不到此活動"


def test_template_escapes_database_content(client):
    test_client, connection = client
    connection.execute.return_value.fetchall.return_value = [
        {"activity_id": 1, "activity_title": "<script>alert(1)</script>", "registration_id": 1, "name": "<b>姓名</b>", "phone": "0900000000"}
    ]
    response = test_client.get("/activities/1/registrations")
    assert "<script>" not in response.text
    assert "&lt;script&gt;" in response.text
    assert "&lt;b&gt;姓名&lt;/b&gt;" in response.text


def test_invalid_activity_id_is_rejected(client):
    test_client, connection = client
    response = test_client.get("/activities/1%20OR%201=1/registrations")
    assert response.status_code == 422
    connection.execute.assert_not_called()


def test_template_path_does_not_depend_on_working_directory(client, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    test_client, connection = client
    connection.execute.return_value.fetchall.return_value = [
        {"activity_id": 1, "activity_title": "路徑測試", "registration_id": None, "name": None, "phone": None}
    ]
    assert test_client.get("/activities/1/registrations").status_code == 200


def test_missing_database_configuration_returns_503(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as test_client:
        response = test_client.get("/activities/1/registrations")
    assert response.status_code == 503
    assert "DATABASE_URL" in response.json()["detail"]


@pytest.mark.parametrize("error", [psycopg.OperationalError, psycopg.ProgrammingError, ValueError])
def test_database_connection_failure_does_not_leak_credentials(monkeypatch, error):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@example.invalid/db")
    monkeypatch.setattr(db.psycopg, "connect", Mock(side_effect=error("secret")))
    with TestClient(app) as test_client:
        response = test_client.get("/activities/1/registrations")
    assert response.status_code == 503
    assert "secret" not in response.text


def test_database_connection_is_closed(monkeypatch):
    connection = Mock()
    connect = Mock(return_value=connection)
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")
    monkeypatch.setattr(db, "psycopg", SimpleNamespace(connect=connect))
    dependency = db.get_connection()
    assert next(dependency) is connection
    dependency.close()
    connection.close.assert_called_once()
