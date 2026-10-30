from pathlib import Path

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from db import get_connection


router = APIRouter(tags=["活動報名清單"])
# 使用絕對路徑，避免從不同目錄啟動時找不到模板。
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


@router.get("/activities/{activity_id}/registrations", response_class=HTMLResponse)
def registration_list(
    request: Request,
    activity_id: int,
    connection: psycopg.Connection = Depends(get_connection),
):
    # LEFT JOIN 保留尚無報名者的活動；單次查詢確保清單與人數一致。
    rows = connection.execute(
        """
        SELECT a.id AS activity_id, a.title AS activity_title,
               r.id AS registration_id, r.name, r.phone
        FROM activities AS a
        LEFT JOIN registrations AS r ON r.activity_id = a.id
        WHERE a.id = %s
        ORDER BY r.id
        """,
        (activity_id,),
    ).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="找不到此活動")

    registrations = [
        {"id": row["registration_id"], "name": row["name"], "phone": row["phone"]}
        for row in rows
        if row["registration_id"] is not None
    ]
    return templates.TemplateResponse(
        request=request,
        name="registrations/list.html",
        context={
            "activity": {"id": rows[0]["activity_id"], "title": rows[0]["activity_title"]},
            "registrations": registrations,
            "registration_count": len(registrations),
        },
    )
