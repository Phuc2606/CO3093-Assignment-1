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
daemon.request
~~~~~~~~~~~~~~~~~

This module provides a Request object to manage and persist 
request settings (cookies, auth, proxies).
"""
from .dictionary import CaseInsensitiveDict
from .utils import get_auth_from_url
class Request():
    """The fully mutable "class" `Request <Request>` object,
    containing the exact bytes that will be sent to the server.

    Instances are generated from a "class" `Request <Request>` object, and
    should not be instantiated manually; doing so may produce undesirable
    effects.

    Usage::

      >>> import deamon.request
      >>> req = request.Request()
      ## Incoming message obtain aka. incoming_msg
      >>> r = req.prepare(incoming_msg)
      >>> r
      <Request>
    """
    __attrs__ = [
        "method",
        "url",
        "headers",
        "body",
        "reason",
        "cookies",
        "body",
        "routes",
        "hook",
    ]

    def __init__(self):
        #: HTTP verb to send to the server.
        self.method = None
        #: HTTP URL to send the request to.
        self.url = None
        #: dictionary of HTTP headers.
        self.headers = None
        #: HTTP path
        self.path = None        
        # The cookies set used to create Cookie header
        self.cookies = None
        #: request body to send to the server.
        self.body = None
        #: Routes
        self.routes = {}
        #: Hook point for routed mapped-path
        self.hook = None

    def extract_request_line(self, request):
        try:
            lines = request.splitlines()
            first_line = lines[0].strip()
            method, path, version = first_line.split()
            return method.strip(), path.strip(), version.strip()
        except Exception:
            print("[Request] Invalid request line:", request)
            return None, None, None
             
    def prepare_headers(self, request):
        """Prepares the given HTTP headers."""
        lines = request.split('\r\n')
        headers = CaseInsensitiveDict()
        for line in lines[1:]:
            if ': ' in line:
                key, val = line.split(': ', 1)
                headers[key.lower()] = val
        return headers

    def prepare(self, request, routes=None):
        """Prepares the entire request with the given parameters."""
        # Prepare the request line from the request header
        self.method, self.path, self.version = self.extract_request_line(request)
        print("[Request] {} path {} version {}".format(self.method, self.path, self.version))

        #
        # @bksysnet Preapring the webapp hook with WeApRous instance
        # The default behaviour with HTTP server is empty routed
        #
        # TODO manage the webapp hook in this mounting point
        self.headers = self.prepare_headers(request)
        #Parse header
        self.prepare_cookies_from_header()

        #Parse routes and hook (for webapp)
        if routes:
            self.routes = routes
            self.hook = routes.get((self.method, self.path))
            if self.hook:
                print(f"[Request] Hook found for {self.path}")

        #Parse body (after blank line)
        body_split = request.split('\r\n\r\n', 1)
        self.body = body_split[1] if len(body_split) > 1 else ""

        #Ensure Content-Length header
        self.prepare_content_length(self.body)

        return self

    def prepare_body(self, data, files, json=None):
        if json is not None:
            try:
               self.body = json.dumps(json)
               self.headers["Content-Type"] = "application/json"
            except Exception:
                self.body = {}
        elif data:
            self.body = data if isinstance(data, str) else str(data)
        else:
            self.body = ""
        #
        # TODO prepare the request authentication
        #
	# self.auth = ...
        self.prepare_content_length(self.body)
        self.prepare_auth(None)
        return


    def prepare_content_length(self, body):
        #
        # TODO prepare the request authentication
        #
	# self.auth = ...
        if self.headers is None:
            self.headers = CaseInsensitiveDict()
        length = len(body.encode('utf-8') if isinstance(body, str) else body)
        self.headers["Content-Length"] = str(length)
        return


    def prepare_auth(self, auth, url=""):
        #
        # TODO prepare the request authentication
        #
	# self.auth = ...
        self.auth = get_auth_from_url(url)
        return self.auth

    def prepare_cookies(self, cookies):
        """Attach cookies to header."""
        if cookies and isinstance(cookies, dict):
            cookie_str = '; '.join(f"{k}={v}" for k, v in cookies.items())
            if not self.headers:
                self.headers = CaseInsensitiveDict()
            self.headers["cookie"] = cookie_str
        return

    def prepare_cookies_from_header(self):
        """Parse cookies from 'cookie' header."""
        self.cookies = {}
        cookie_header = self.headers.get('cookie', '')
        for pair in cookie_header.split(';'):
            if '=' in pair:
                key, value = pair.strip().split('=', 1)
                self.cookies[key] = value