"""Small, same-origin Mini App host; preview mode never starts a Telegram bot."""
from pathlib import Path

from aiohttp import web

WEB_ROOT = Path(__file__).with_name("web")
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self' https://telegram.org; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "connect-src 'self'; font-src 'self'; object-src 'none'; "
        "base-uri 'none'; form-action 'self'; "
        "frame-ancestors https://web.telegram.org https://*.telegram.org https://t.me"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-cache",
}


async def health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "turnikmen"},
                             headers={"Cache-Control": "no-store"})


async def app_index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(WEB_ROOT / "index.html", headers={
        **SECURITY_HEADERS, "Content-Type": "text/html; charset=utf-8",
    })


async def app_asset(request: web.Request) -> web.FileResponse:
    # An explicit allowlist keeps Python, configuration and databases unreachable.
    asset = request.match_info["asset"]
    content_type = {"app.js": "text/javascript; charset=utf-8",
                    "app.css": "text/css; charset=utf-8",
                    "icon.svg": "image/svg+xml"}[asset]
    return web.FileResponse(WEB_ROOT / asset, headers={
        **SECURITY_HEADERS, "Content-Type": content_type,
    })


def setup_static(app: web.Application) -> None:
    app.router.add_get("/", _redirect)
    app.router.add_get("/app", app_index)
    app.router.add_get("/app/", app_index)
    app.router.add_get("/app/{asset:app\\.css|app\\.js|icon\\.svg}", app_asset)
    app.router.add_get("/healthz", health)


async def _redirect(request: web.Request) -> web.Response:
    raise web.HTTPFound("/app")


def preview() -> None:
    """Serve the labelled frontend demo locally, without credentials or databases."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8088)
    args = parser.parse_args()
    app = web.Application(client_max_size=64 * 1024)
    setup_static(app)
    web.run_app(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    preview()
