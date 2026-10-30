
from pathlib import Path

import psycopg
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from db import get_connection


router = APIRouter(tags=["活動報名"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)


@router.get(
    "/activities/{activity_id}/register",
    response_class=HTMLResponse
)
def show_registration_form(
    request: Request,
    activity_id: int,
    connection: psycopg.Connection = Depends(get_connection),
):
    activity = connection.execute(
        """
        SELECT id, title, description, event_date,
               registration_deadline,
               registration_deadline > CURRENT_TIMESTAMP AS is_open
        FROM activities
        WHERE id = %s
        """,
        (activity_id,),
    ).fetchone()

    if activity is None:
        return templates.TemplateResponse(
            request=request,
            name="registrations/form.html",
            context={
                "activity": None,
                "error": "找不到此活動。",
            },
            status_code=404,
        )

    return templates.TemplateResponse(
        request=request,
        name="registrations/form.html",
        context={
            "activity": activity,
            "error": None if activity["is_open"] else "此活動已截止報名。",
            "success": None,
        },
    )


@router.post(
    "/activities/{activity_id}/register",
    response_class=HTMLResponse
)
async def submit_registration(
    request: Request,
    activity_id: int,
    connection: psycopg.Connection = Depends(get_connection),
):
    form = await request.form()

    name = str(form.get("name", "")).strip()
    phone = str(form.get("phone", "")).strip()

    activity = connection.execute(
        """
        SELECT id, title, description, event_date,
               registration_deadline,
               registration_deadline > CURRENT_TIMESTAMP AS is_open
        FROM activities
        WHERE id = %s
        """,
        (activity_id,),
    ).fetchone()

    if activity is None:
        return templates.TemplateResponse(
            request=request,
            name="registrations/form.html",
            context={
                "activity": None,
                "error": "找不到此活動。",
            },
            status_code=404,
        )

    if not name or not phone:
        return templates.TemplateResponse(
            request=request,
            name="registrations/form.html",
            context={
                "activity": activity,
                "error": "姓名及聯絡電話不可空白。",
                "name": name,
                "phone": phone,
            },
            status_code=400,
        )

    if len(name) > 50 or len(phone) > 20:
        return templates.TemplateResponse(
            request=request,
            name="registrations/form.html",
            context={
                "activity": activity,
                "error": "姓名最多50字，聯絡電話最多20字。",
                "name": name,
                "phone": phone,
            },
            status_code=400,
        )

    if not activity["is_open"]:
        return templates.TemplateResponse(
            request=request,
            name="registrations/form.html",
            context={
                "activity": activity,
                "error": "此活動已截止報名，無法送出。",
                "name": name,
                "phone": phone,
            },
            status_code=400,
        )

    try:
        result = connection.execute(
            """
            INSERT INTO registrations (activity_id, name, phone)
            SELECT id, %s, %s
            FROM activities
            WHERE id = %s
              AND registration_deadline > CURRENT_TIMESTAMP
            RETURNING id
            """,
            (name, phone, activity_id),
        ).fetchone()

        if result is None:
            return templates.TemplateResponse(
                request=request,
                name="registrations/form.html",
                context={
                    "activity": activity,
                    "error": "此活動已截止報名，無法送出。",
                    "name": name,
                    "phone": phone,
                },
                status_code=400,
            )

    except psycopg.errors.UniqueViolation:
        return templates.TemplateResponse(
            request=request,
            name="registrations/form.html",
            context={
                "activity": activity,
                "error": "您已經報名過此活動。",
                "name": name,
                "phone": phone,
            },
            status_code=409,
        )

    return templates.TemplateResponse(
        request=request,
        name="registrations/form.html",
        context={
            "activity": activity,
            "success": "報名成功！",
            "error": None,
        },
    )
