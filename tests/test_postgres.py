import os
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from db import get_connection
from main import app


@pytest.fixture
def postgres_client():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("未設定 TEST_DATABASE_URL，未驗證真實 PostgreSQL 查詢")

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        # 只建立連線專屬的暫存表，結束時自動移除，不讀寫既有資料表。
        connection.execute("SET search_path TO pg_temp")
        schema = (Path(__file__).resolve().parents[1] / "database" / "schema.sql").read_text(encoding="utf-8-sig")
        connection.execute(schema.replace("CREATE TABLE ", "CREATE TEMP TABLE "))
        connection.execute(
            """
            INSERT INTO activities (title, event_date, registration_deadline)
            VALUES ('資料庫工作坊', '2026-11-10 10:00', '2026-11-09 18:00'),
                   ('Python 工作坊', '2026-11-11 10:00', '2026-11-10 18:00'),
                   ('尚無報名活動', '2026-11-12 10:00', '2026-11-11 18:00')
            """
        )
        connection.execute(
            """
            INSERT INTO registrations (activity_id, name, phone)
            VALUES (1, '王小明', '0912345678'), (1, '陳小華', '0223456789'),
                   (2, '林小美', '0987654321')
            """
        )
        app.dependency_overrides[get_connection] = lambda: connection
        try:
            with TestClient(app) as test_client:
                yield test_client
        finally:
            app.dependency_overrides.clear()
            connection.rollback()


@pytest.mark.parametrize(
    ("activity_id", "title", "names", "excluded_names", "count"),
    [
        (1, "資料庫工作坊", ["王小明", "陳小華"], ["林小美"], 2),
        (2, "Python 工作坊", ["林小美"], ["王小明", "陳小華"], 1),
        (3, "尚無報名活動", [], ["王小明", "陳小華", "林小美"], 0),
    ],
)
def test_real_postgres_list_and_activity_isolation(postgres_client, activity_id, title, names, excluded_names, count):
    response = postgres_client.get(f"/activities/{activity_id}/registrations")
    assert response.status_code == 200
    assert title in response.text
    assert f"目前報名人數：{count} 人" in response.text
    for name in names:
        assert name in response.text
    for name in excluded_names:
        assert name not in response.text
    if count == 0:
        assert "目前尚無報名資料" in response.text
    if activity_id == 1:
        assert "0912345678" in response.text and "0223456789" in response.text
        assert "<td>1</td>" in response.text and "<td>2</td>" in response.text


def test_real_postgres_missing_activity(postgres_client):
    response = postgres_client.get("/activities/999/registrations")
    assert response.status_code == 404
