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

This module provides a http adapter object to manage and persist 
http settings (headers, bodies). The adapter supports both
raw URL paths and RESTful route definitions, and integrates with
Request and Response objects to handle client-server communication.
"""

from .request import Request
from .response import Response
from .response_template import RESPONSE_TEMPLATES
class HttpAdapter:
    """
    A mutable :class:`HTTP adapter <HTTP adapter>` for managing client connections
    and routing requests.

    The `HttpAdapter` class encapsulates the logic for receiving HTTP requests,
    dispatching them to appropriate route handlers, and constructing responses.
    It supports RESTful routing via hooks and integrates with :class:`Request <Request>` 
    and :class:`Response <Response>` objects for full request lifecycle management.

    Attributes:
        ip (str): IP address of the client.
        port (int): Port number of the client.
        conn (socket): Active socket connection.
        connaddr (tuple): Address of the connected client.
        routes (dict): Mapping of route paths to handler functions.
        request (Request): Request object for parsing incoming data.
        response (Response): Response object for building and sending replies.
    """

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
        """
        Initialize a new HttpAdapter instance.

        :param ip (str): IP address of the client.
        :param port (int): Port number of the client.
        :param conn (socket): Active socket connection.
        :param connaddr (tuple): Address of the connected client.
        :param routes (dict): Mapping of route paths to handler functions.
        """

        #: IP address.
        self.ip = ip
        #: Port.
        self.port = port
        #: Connection
        self.conn = conn
        #: Conndection address
        self.connaddr = connaddr
        #: Routes
        self.routes = routes
        #: Request
        self.request = Request()
        #: Response
        self.response = Response()

    def handle_client(self, conn, addr, routes):
        """
        Handle an incoming client connection.

        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.

        :param conn (socket): The client socket connection.
        :param addr (tuple): The client's address.
        :param routes (dict): The route mapping for dispatching requests.
        """

        # Connection handler.
        self.conn = conn        
        # Connection address.
        self.connaddr = addr
        # Request handler
        req = self.request
        # Response handler
        resp = self.response
        try:
        # Handle the request
            msg = conn.recv(1024).decode()
            req.prepare(msg, routes)
            # Task 1A: login
            if req.method == "POST" and req.path == "/login":
                return self.send(resp, self.handle_login(req, resp))

            # Task 1B: cookie guard
            early = self.cookie_auth_guard(req)
            if early is not None:
                return self.send(resp, early)
            raw = self.response.build_response(req)
            self.conn.sendall(raw)
        finally:
            conn.close()
    def handle_login(self, req, resp):
        raw_body = req.body.decode("utf-8", "ignore") if isinstance(req.body, (bytes, bytearray)) else (req.body or "")
        creds = {}
        for pair in raw_body.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                creds[k] = v

        if creds.get("username") == "admin" and creds.get("password") == "password":
            req.path = "/index.html"
            raw = resp.build_response(req)
            body = raw.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in raw else raw
            headers = {
                "Content-Type": "text/html; charset=utf-8",
                "Set-Cookie": "auth=true; Path=/",
            }
            return ("200 OK", headers, body)

        e = RESPONSE_TEMPLATES["login_failed"]
        return (e["status"], {"Content-Type": e["content_type"], **e["headers"]}, e["body"])
    #TASK 1: COOKIES
    def cookie_auth_guard(self, req):
        if req.path in ("/", "/index.html"):
            if req.cookies.get("auth") != "true":
                e = RESPONSE_TEMPLATES["unauthorized"]
                return (e["status"], {"Content-Type": e["content_type"], **e["headers"]}, e["body"])
        if req.path == "/":
            req.path = "/index.html"
        return None
    
    def send(self, resp, triple):
        status, headers, body = triple
        self.conn.sendall(resp.compose(status=status, headers=headers, body=body))


    @property
    def extract_cookies(self, req, resp):
        """
        Build cookies from the :class:`Request <Request>` headers.

        :param req:(Request) The :class:`Request <Request>` object.
        :param resp: (Response) The res:class:`Response <Response>` object.
        :rtype: cookies - A dictionary of cookie key-value pairs.
        """
        cookies = {}
        headers = req.headers if hasattr(req, "headers") else {}
        cookie_header = headers.get("Cookie")
        if cookie_header:
            for pair in cookie_header.split(";"):
                if "=" in pair:
                    key, value = pair.strip().split("=", 1)
                    cookies[key] = value
        return cookies

    def build_response(self, req, resp):
        """Builds a :class:`Response <Response>` object 

        :param req: The :class:`Request <Request>` used to generate the response.
        :param resp: The  response object.
        :rtype: Response
        """
        response = Response()

        # Set encoding.
        response.encoding = resp.headers.get("Content-Encoding", "utf-8")
        response.raw = resp
        response.reason = getattr(resp, "reason", "OK")

        response.url = req.url.decode("utf-8") if isinstance(req.url, bytes) else req.url

        # Add new cookies from the server.
        response.cookies = self.extract_cookies(req)

        # Give the Response some context.
        response.request = req
        response.connection = self

        return response

    # def get_connection(self, url, proxies=None):
        # """Returns a url connection for the given URL. 

        # :param url: The URL to connect to.
        # :param proxies: (optional) A Requests-style dictionary of proxies used on this request.
        # :rtype: int
        # """

        # proxy = select_proxy(url, proxies)

        # if proxy:
            # proxy = prepend_scheme_if_needed(proxy, "http")
            # proxy_url = parse_url(proxy)
            # if not proxy_url.host:
                # raise InvalidProxyURL(
                    # "Please check proxy URL. It is malformed "
                    # "and could be missing the host."
                # )
            # proxy_manager = self.proxy_manager_for(proxy)
            # conn = proxy_manager.connection_from_url(url)
        # else:
            # # Only scheme should be lower case
            # parsed = urlparse(url)
            # url = parsed.geturl()
            # conn = self.poolmanager.connection_from_url(url)

        # return conn


    def add_headers(self, request):
        """
        Add headers to the request.

        This method is intended to be overridden by subclasses to inject
        custom headers. It does nothing by default.

        
        :param request: :class:`Request <Request>` to add headers to.
        """
        pass

    def build_proxy_headers(self, proxy):
        """Returns a dictionary of the headers to add to any request sent
        through a proxy. 

        :class:`HttpAdapter <HttpAdapter>`.

        :param proxy: The url of the proxy being used for this request.
        :rtype: dict
        """
        headers = {}
        #
        # TODO: build your authentication here
        #       username, password =...
        # we provide dummy auth here
        #
        username, password = ("user1", "password")

        if username:
            headers["Proxy-Authorization"] = (username, password)

        return headers