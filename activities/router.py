"""活動管理模組（新增活動、活動清單）。

整合方式（在共用 main.py 加兩行即可）：
    from activities.router import router as activities_router
    app.include_router(activities_router)

資料庫沿用 db.get_connection 與 DATABASE_URL，不另外維護帳密或連線設定。
"""
from datetime import datetime

import psycopg
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from db import get_connection
from templating import templates

router = APIRouter(prefix="/activities", tags=["activities"])

DT_FORMAT = "%Y-%m-%dT%H:%M"  # <input type="datetime-local"> 的格式


def parse_dt(value: str):
    try:
        return datetime.strptime(value.strip(), DT_FORMAT)
    except (ValueError, AttributeError):
        return None


@router.get("", response_class=HTMLResponse)
def list_activities(
    request: Request,
    created: int | None = None,
    connection: psycopg.Connection = Depends(get_connection),
):
    rows = connection.execute(
        "SELECT id, title, description, event_date, registration_deadline "
        "FROM activities ORDER BY event_date ASC, id ASC"
    ).fetchall()
    created_title = None
    if created is not None:
        hit = connection.execute("SELECT title FROM activities WHERE id = %s", (created,)).fetchone()
        created_title = hit["title"] if hit else None

    now = datetime.now()
    for r in rows:
        r["is_open"] = r["registration_deadline"] > now
    return templates.TemplateResponse(
        request, "activities/list.html",
        {"activities": rows, "created_title": created_title},
    )


@router.get("/new", response_class=HTMLResponse)
def new_activity_form(request: Request):
    return templates.TemplateResponse(
        request, "activities/new.html", {"errors": [], "form": {}}
    )


@router.post("", response_class=HTMLResponse)
def create_activity(
    request: Request,
    title: str = Form(""),
    description: str = Form(""),
    event_date: str = Form(""),
    registration_deadline: str = Form(""),
    connection: psycopg.Connection = Depends(get_connection),
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
            request, "activities/new.html",
            {"errors": errors, "form": form}, status_code=400,
        )

    # 共用連線採 autocommit，單筆 INSERT 成功後即可由下一次請求讀取。
    new_id = connection.execute(
        "INSERT INTO activities (title, description, event_date, registration_deadline) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (title, description or None, ev, dl),
    ).fetchone()["id"]
    return RedirectResponse(
        url=request.url_for("list_activities").include_query_params(created=new_id),
        status_code=303,
    )
