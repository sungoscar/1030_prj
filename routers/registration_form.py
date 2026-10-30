import psycopg
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from db import get_connection
from templating import templates


router = APIRouter(tags=["活動報名"])

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
def submit_registration(
    request: Request,
    activity_id: int,
    name: str = Form(""),
    phone: str = Form(""),
    connection: psycopg.Connection = Depends(get_connection),
):
    # 與其他 Router 一樣使用同步 psycopg，避免在事件迴圈直接執行同步 SQL。
    name = name.strip()
    phone = phone.strip()

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
        # 寫入時再次檢查截止時間，避免使用者開啟表單後才截止仍可送出。
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
            activity["is_open"] = False
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
        # 沿用 schema 的 UNIQUE(activity_id, name, phone)，避免重複或同時送出。
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
