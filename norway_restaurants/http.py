import ipaddress
import socket
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

USER_AGENT = 'NorwayRestaurantResearch/1.0'


def public_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('Expected a public HTTP(S) URL')
    if parts.port not in (None, 80, 443):
        raise ValueError('Nonstandard ports are not allowed')
    addresses = socket.getaddrinfo(parts.hostname, parts.port or 443)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Non-public network destination')
    return url


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self, delay=1.0, timeout=15, user_agent=USER_AGENT, budget=None):
        self.delay, self.timeout, self.user_agent = delay, timeout, user_agent
        self.last_request = 0
        self.opener = build_opener(SafeRedirect())
        self.deadline = time.monotonic() + budget if budget else None

    def get(self, url, max_bytes=2_000_000):
        public_url(url)
        for attempt in range(3):
            pause = max(0, self.delay - (time.monotonic() - self.last_request))
            if self.deadline and time.monotonic() + pause >= self.deadline:
                raise TimeoutError('Website scan time budget exceeded')
            time.sleep(pause)
            self.last_request = time.monotonic()
            try:
                request = Request(url, headers={'User-Agent': self.user_agent, 'Accept': 'application/json,text/html,text/plain'})
                timeout = min(self.timeout, max(0.1, self.deadline - time.monotonic())) if self.deadline else self.timeout
                with self.opener.open(request, timeout=timeout) as response:
                    data = response.read(max_bytes + 1)
                    if len(data) > max_bytes:
                        raise ValueError('Response exceeds size limit')
                    return data.decode(response.headers.get_content_charset() or 'utf-8', errors='replace'), response.url, response.headers.get_content_type()
            except HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise
                retry = exc.headers.get('Retry-After', '')
                pause = min(60, int(retry)) if retry.isdigit() else 2 ** attempt
                if self.deadline and time.monotonic() + pause >= self.deadline:
                    raise TimeoutError('Website retry exceeds scan time budget') from exc
                time.sleep(pause)
