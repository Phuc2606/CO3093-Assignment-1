from .dictionary import CaseInsensitiveDict   

RESPONSE_TEMPLATES = CaseInsensitiveDict({
    # ---- Success ----
    "api_ok": {
        "status": "200 OK",
        "content_type": "application/json; charset=utf-8",
        "headers": {},
        "body": b'{"status":"success"}',
    },
    "ok_html": {
        "status": "200 OK",
        "content_type": "text/html; charset=utf-8",
        "headers": {},
        "body": b"<h1>OK</h1>",
    },

    # ---- Error ----
    "unauthorized": {
        "status": "401 Unauthorized",
        "content_type": "text/html; charset=utf-8",
        "headers": {},
        "body": (
            "<html><head><title>401</title></head>"
            "<body><h1>401 Unauthorized</h1>"
            "<p>Login <a href='/login.html'>here</a> to visit this page.</p>"
            "</body></html>"
        ).encode("utf-8"),
    },
    "login_failed": {
        "status": "401 Unauthorized",
        "content_type": "text/html; charset=utf-8",
        "headers": {},
        "body": (
            "<html><head><title>Login Failed</title></head>"
            "<body><h1>401 Unauthorized</h1>"
            "<p>Invalid username or password</p>"
            "<p><a href='/login.html'>Try again</a></p>"
            "</body></html>"
        ).encode("utf-8"),
    },
    "not_found": {
        "status": "404 Not Found",
        "content_type": "text/html; charset=utf-8",
        "headers": {},
        "body": b"<h1>404 Not Found</h1>",
    },
})
