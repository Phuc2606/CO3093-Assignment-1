#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.httpadapter
~~~~~~~~~~~~~~~~~

HTTP adapter for WeApRous framework — final fixed version.
Features:
- Full-body read for JSON/form requests
- Proper JSON responses
- Static file serving for .html/.css/.js/.png/.jpg
- Compatible with legacy WeApRous routing
"""

from .request import Request
from .response import Response
from .response_template import RESPONSE_TEMPLATES
import json
import os

SESSIONS = {}
SESSION_COUNTER = 0


class HttpAdapter:
    __attrs__ = [
        "ip",
        "port",
        "conn",
        "connaddr",
        "routes",
        "request",
        "response",
    ]

    def __init__(self, ip, port, conn, connaddr, routes):
        self.ip = ip
        self.port = port
        self.conn = conn
        self.connaddr = connaddr
        self.routes = routes
        self.request = Request()
        self.response = Response()

    # =====================================================
    # =============== Utility: read full body ==============
    # =====================================================
    def _recv_full_request(self, conn):
        """Read full HTTP request using Content-Length."""
        msg = b""
        chunk = conn.recv(1024)
        msg += chunk

        # read header first
        while b"\r\n\r\n" not in msg and chunk:
            chunk = conn.recv(1024)
            msg += chunk

        # parse header for content length
        header_part = msg.split(b"\r\n\r\n", 1)[0].decode(errors="ignore")
        content_length = 0
        for line in header_part.split("\r\n"):
            if line.lower().startswith("content-length:"):
                try:
                    content_length = int(line.split(":", 1)[1].strip())
                except ValueError:
                    content_length = 0

        # read remaining body if any
        body_part = b""
        if b"\r\n\r\n" in msg:
            body_part = msg.split(b"\r\n\r\n", 1)[1]
        remaining = content_length - len(body_part)

        while remaining > 0:
            chunk = conn.recv(min(1024, remaining))
            if not chunk:
                break
            msg += chunk
            remaining -= len(chunk)

        return msg.decode(errors="ignore")

    # =====================================================
    # =============== Main client handler =================
    # =====================================================
    def handle_client(self, conn, addr, routes):
        """Handle an incoming client connection."""
        self.conn = conn
        self.connaddr = addr
        req = self.request
        resp = self.response

        try:
            raw_msg = self._recv_full_request(conn)
            req.prepare(raw_msg, routes)
        except Exception as e:
            print(f"[HttpAdapter] Request read error: {e}")
            self._send_error(conn, 400, "Bad Request", str(e))
            return

        # ------------------ Route Handling ------------------
        if req.hook:
            print(f"[HttpAdapter] Hook matched: {req.hook._route_path} {req.hook._route_methods}")
            try:
                hook_result = req.hook(headers=req.headers, body=req.body)
                if hook_result is None:
                    hook_result = {"status": "error", "message": "Empty response"}

                # Determine content type
                if isinstance(hook_result, str):
                    if hook_result.strip().startswith("{") or hook_result.strip().startswith("["):
                        content_type = "application/json"
                        body_bytes = hook_result.encode("utf-8")
                    elif hook_result.strip().startswith("<"):
                        content_type = "text/html; charset=utf-8"
                        body_bytes = hook_result.encode("utf-8")
                    else:
                        content_type = "text/plain; charset=utf-8"
                        body_bytes = hook_result.encode("utf-8")
                else:
                    content_type = "application/json"
                    body_bytes = json.dumps(hook_result).encode("utf-8")

                header = (
                    "HTTP/1.1 200 OK\r\n"
                    f"Content-Type: {content_type}\r\n"
                    f"Content-Length: {len(body_bytes)}\r\n"
                    "Connection: close\r\n\r\n"
                )
                conn.sendall(header.encode("utf-8") + body_bytes)
                conn.close()
                return

            except Exception as e:
                print(f"[HttpAdapter] Hook execution error: {e}")
                self._send_error(conn, 500, "Internal Server Error", str(e))
                return

        # ------------------ Login Handling ------------------
        global SESSION_COUNTER
        if req.method == "POST" and req.path == "/login":
            self._handle_login(conn, req)
            return

        # ------------------ Session Validation ---------------
        cookies = req.headers.get("Cookie", "")
        session_id = None
        for c in cookies.split(";"):
            if "session_id=" in c:
                session_id = c.strip().split("=")[1]
                break

        auth_status = SESSIONS.get(session_id, False)
        if req.path in ["/", "/index.html", "/chat.html"] and not auth_status:
            resp_template = RESPONSE_TEMPLATES["unauthorized"]
            header = (
                f"HTTP/1.1 {resp_template['status']}\r\n"
                f"Content-Type: {resp_template['content_type']}\r\n"
                f"Content-Length: {len(resp_template['body'])}\r\n"
                "Connection: close\r\n\r\n"
            )
            conn.sendall(header.encode("utf-8") + resp_template["body"])
            conn.close()
            return

        # ------------------ Static file handler ---------------
        if req.method == "GET":
            try:
                print(f"[HttpAdapter] GET request path: {req.path}")

                # 1️⃣ Root → index.html
                if req.path == "/" or req.path == "":
                    file_path = os.path.join("www", "index.html")

                # 2️⃣ /login → www/login.html
                elif req.path == "/login":
                    file_path = os.path.join("www", "login.html")

                # 3️⃣ /static/... → static/...
                elif req.path.startswith("/static/"):
                    rel_path = req.path.lstrip("/")
                    file_path = os.path.normpath(rel_path)

                # 4️⃣ /css/... , /images/... , /js/... → static/... (để hỗ trợ HTML cũ)
                elif req.path.startswith(("/css/", "/images/", "/js/")):
                    rel_path = os.path.join("static", req.path.lstrip("/"))
                    file_path = os.path.normpath(rel_path)

                # 5️⃣ Các file HTML khác trong www/
                else:
                    rel_path = req.path.lstrip("/")
                    file_path = os.path.join("www", rel_path)

                print(f"[HttpAdapter] Resolved file path: {file_path}")

                # Kiểm tra tồn tại
                if not os.path.exists(file_path):
                    print(f"[HttpAdapter] File not found: {file_path}")
                    self._send_error(conn, 404, "Not Found", f"File {req.path} not found")
                    return

                # Đọc file
                with open(file_path, "rb") as f:
                    body = f.read()

                # MIME type detection
                if file_path.endswith(".html"):
                    ctype = "text/html; charset=utf-8"
                elif file_path.endswith(".css"):
                    ctype = "text/css"
                elif file_path.endswith(".js"):
                    ctype = "application/javascript"
                elif file_path.endswith((".png", ".jpg", ".jpeg", ".gif")):
                    ctype = "image/png" if file_path.endswith(".png") else "image/jpeg"
                else:
                    ctype = "application/octet-stream"

                # Gửi phản hồi
                header = (
                    "HTTP/1.1 200 OK\r\n"
                    f"Content-Type: {ctype}\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n\r\n"
                )
                conn.sendall(header.encode("utf-8") + body)
                conn.close()
                return

            except Exception as e:
                print(f"[HttpAdapter] Static file handler error: {e}")
                self._send_error(conn, 500, "Internal Server Error", str(e))
                return

        # ------------------ Fallback (404) -------------------
        self._send_error(conn, 404, "Not Found", f"No route for {req.method} {req.path}")

    # =====================================================
    # =============== Helper: send JSON error ==============
    # =====================================================
    def _send_error(self, conn, code, reason, message):
        """Send standardized JSON error."""
        body = json.dumps({"status": "error", "code": code, "message": message})
        header = (
            f"HTTP/1.1 {code} {reason}\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        )
        try:
            conn.sendall(header.encode("utf-8") + body.encode("utf-8"))
        except Exception:
            pass
        conn.close()

    # =====================================================
    # =============== Helper: handle login ================
    # =====================================================
    def _handle_login(self, conn, req):
        """Process POST /login."""
        global SESSION_COUNTER
        try:
            data = {}
            try:
                data = json.loads(req.body)
            except json.JSONDecodeError:
                for pair in req.body.split("&"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        data[k] = v

            username = data.get("username")
            password = data.get("password")

            if username == "admin" and password == "password":
                SESSION_COUNTER += 1
                session_id = str(SESSION_COUNTER)
                SESSIONS[session_id] = True
                file_path = os.path.join("www", "index.html")
                with open(file_path, "r", encoding="utf-8") as f:
                    body = f.read()

                header = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: text/html; charset=utf-8\r\n"
                    f"Set-Cookie: session_id={session_id}; Path=/; HttpOnly\r\n"
                    f"Content-Length: {len(body.encode('utf-8'))}\r\n"
                    "Connection: close\r\n\r\n"
                )
                conn.sendall(header.encode("utf-8") + body.encode("utf-8"))
                conn.close()
                return
            else:
                template = RESPONSE_TEMPLATES["login_failed"]
        except Exception as e:
            print(f"[HttpAdapter] Login error: {e}")
            template = RESPONSE_TEMPLATES["login_failed"]

        header = (
            f"HTTP/1.1 {template['status']}\r\n"
            f"Content-Type: {template['content_type']}\r\n"
            f"Content-Length: {len(template['body'])}\r\n"
            "Connection: close\r\n\r\n"
        )
        conn.sendall(header.encode("utf-8") + template["body"])
        conn.close()

    # =====================================================
    # =============== Cookie Utilities ====================
    # =====================================================
    @property
    def extract_cookies(self, req, resp):
        """Extract cookies from request headers."""
        cookies = {}
        headers = req.headers if hasattr(req, "headers") else {}
        cookie_header = headers.get("Cookie")
        if cookie_header:
            for pair in cookie_header.split(";"):
                if "=" in pair:
                    key, value = pair.strip().split("=", 1)
                    cookies[key] = value
        return cookies

    # =====================================================
    # =============== Build Response Wrapper ==============
    # =====================================================
    def build_response(self, req, resp):
        """Build a Response object from raw request."""
        response = Response()
        response.encoding = resp.headers.get("Content-Encoding", "utf-8")
        response.raw = resp
        response.reason = getattr(resp, "reason", "OK")

        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url

        response.cookies = self.extract_cookies(req, resp)
        response.request = req
        response.connection = self
        return response

    # =====================================================
    # =============== Placeholder Methods =================
    # =====================================================
    def add_headers(self, request):
        """Add headers to the request (can be overridden)."""
        pass

    def build_proxy_headers(self, proxy):
        """Return dummy proxy auth headers (if needed)."""
        headers = {}
        username, password = ("user1", "password")
        if username:
            headers["Proxy-Authorization"] = (username, password)
        return headers
