"""活動管理模組（新增活動、活動清單）。

整合方式（在共用 main.py 加兩行即可）：
    from activities.router import router as activities_router
    app.include_router(activities_router)

資料庫連線設定一律從環境變數讀取，程式內不寫密碼：
    DB_HOST（預設空白=本機 socket）、DB_PORT、DB_NAME（預設 activity_signup）、
    DB_USER、DB_PASSWORD
若組員之後提供共用的連線模組，只需替換下方 get_conn()。
"""
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/activities", tags=["activities"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

DT_FORMAT = "%Y-%m-%dT%H:%M"  # <input type="datetime-local"> 的格式


@contextmanager
def get_conn():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST") or None,
        port=os.getenv("DB_PORT") or None,
        dbname=os.getenv("DB_NAME", "activity_signup"),
        user=os.getenv("DB_USER") or None,
        password=os.getenv("DB_PASSWORD") or None,
    )
    try:
        with conn:  # 成功 commit、例外 rollback
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur
    finally:
        conn.close()


def parse_dt(value: str):
    try:
        return datetime.strptime(value.strip(), DT_FORMAT)
    except (ValueError, AttributeError):
        return None


@router.get("", response_class=HTMLResponse)
def list_activities(request: Request, created: int | None = None):
    with get_conn() as cur:
        cur.execute(
            "SELECT id, title, description, event_date, registration_deadline "
            "FROM activities ORDER BY event_date ASC, id ASC"
        )
        rows = cur.fetchall()
        created_title = None
        if created is not None:
            cur.execute("SELECT title FROM activities WHERE id = %s", (created,))
            hit = cur.fetchone()
            created_title = hit["title"] if hit else None

    now = datetime.now()
    for r in rows:
        r["is_open"] = r["registration_deadline"] > now
    return templates.TemplateResponse(
        request, "activity_list.html",
        {"activities": rows, "created_title": created_title},
    )


@router.get("/new", response_class=HTMLResponse)
def new_activity_form(request: Request):
    return templates.TemplateResponse(
        request, "activity_new.html", {"errors": [], "form": {}}
    )


@router.post("", response_class=HTMLResponse)
def create_activity(
    request: Request,
    title: str = Form(""),
    description: str = Form(""),
    event_date: str = Form(""),
    registration_deadline: str = Form(""),
):
    form = {
        "title": title, "description": description,
        "event_date": event_date, "registration_deadline": registration_deadline,
    }
    errors = []
    title = title.strip()
    description = description.strip()

    if not title:
        errors.append("請填寫活動名稱")
    elif len(title) > 100:
        errors.append("活動名稱不可超過 100 字")

    ev = parse_dt(event_date) if event_date.strip() else None
    dl = parse_dt(registration_deadline) if registration_deadline.strip() else None
    if not event_date.strip():
        errors.append("請選擇活動日期")
    elif ev is None:
        errors.append("活動日期格式不正確")
    if not registration_deadline.strip():
        errors.append("請選擇報名截止時間")
    elif dl is None:
        errors.append("報名截止時間格式不正確")
    if ev and dl and dl > ev:
        errors.append("報名截止時間不可晚於活動日期")

    if errors:
        return templates.TemplateResponse(
            request, "activity_new.html",
            {"errors": errors, "form": form}, status_code=400,
        )

    with get_conn() as cur:
        cur.execute(
            "INSERT INTO activities (title, description, event_date, registration_deadline) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (title, description or None, ev, dl),
        )
        new_id = cur.fetchone()["id"]
    return RedirectResponse(url=f"/activities?created={new_id}", status_code=303)
