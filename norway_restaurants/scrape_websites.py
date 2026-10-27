from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit, urldefrag
from urllib.robotparser import RobotFileParser

from .find_emails import parse_page

PATHS = ('/', '/contact', '/contactos', '/contato', '/contact-us', '/kontakt', '/om-oss', '/about')


def scrape_website(client, website, max_pages=6):
    queue = [website] + [urljoin(website, path) for path in PATHS]
    pages, errors, seen, robots = [], [], set(), {}

    def allowed(url):
        parts = urlsplit(url)
        origin = f'{parts.scheme}://{parts.netloc}'
        if origin not in robots:
            parser = RobotFileParser()
            try:
                body, _, _ = client.get(origin + '/robots.txt')
                parser.parse(body.splitlines())
            except HTTPError as exc:
                parser.parse([] if exc.code == 404 else ['User-agent: *', 'Disallow: /'])
            except Exception:
                parser.parse(['User-agent: *', 'Disallow: /'])
            robots[origin] = parser
        parser = robots[origin]
        delay = parser.crawl_delay(client.user_agent) or parser.crawl_delay('*')
        if delay:
            client.delay = max(client.delay, delay)
        return parser.can_fetch(client.user_agent, url)

    while queue and len(seen) < max_pages:
        url = urldefrag(queue.pop(0))[0]
        if url in seen:
            continue
        seen.add(url)
        try:
            if not allowed(url):
                errors.append({'url': url, 'error': 'robots_disallowed_or_unavailable'})
                continue
            body, final, content_type = client.get(url)
            if content_type not in ('text/html', 'application/xhtml+xml'):
                continue
            pages.append({'url': final, 'html': body})
            for link in parse_page(body).links:
                candidate = urljoin(final, link)
                if urlsplit(candidate).netloc == urlsplit(final).netloc and any(word in urlsplit(candidate).path.lower() for word in ('kontakt', 'contact', 'contato', 'about', 'om-oss', 'sobre')):
                    queue.insert(0, candidate)
        except Exception as exc:
            errors.append({'url': url, 'error': str(exc)})
    return pages, errors
