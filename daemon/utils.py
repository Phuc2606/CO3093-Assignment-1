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

from urllib.parse import urlparse, parse_qs, unquote

def get_auth_from_url(url):
    """Given a url with authentication components, extract them into a tuple of
    username,password.

    :rtype: (str,str)
    """
    parsed = urlparse(url)
    try:
        user = unquote(parsed.username) if parsed.username else ""
        pwd  = unquote(parsed.password) if parsed.password else ""
    except (AttributeError, TypeError):
        user, pwd = "", ""
    return {"username": user, "password": pwd}