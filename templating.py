from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from starlette.routing import NoMatchFound


def navigation_context(request: Request) -> dict:
    # 個別 Router 單獨掛載時，不顯示尚未提供的導覽入口。
    links = {}
    for key, route_name in (
        ("activities_url", "list_activities"),
        ("new_activity_url", "new_activity_form"),
    ):
        try:
            links[key] = request.url_for(route_name)
        except NoMatchFound:
            links[key] = None
    return links


templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent / "templates"),
    context_processors=[navigation_context],
)
