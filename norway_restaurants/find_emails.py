import re
from html.parser import HTMLParser
from urllib.parse import unquote

EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
ROLES = {'post', 'booking', 'kontakt', 'info', 'reservasjon', 'reservasjoner', 'restaurant', 'hello', 'hei', 'mail', 'contact', 'reservation', 'reservations'}


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.links, self.phones = [], [], []
        self.hidden = 0
        self.viewport = False
        self.title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag == 'a':
            href = attrs.get('href', '')
            self.links.append(href)
            if href.lower().startswith('tel:'):
                self.phones.append(unquote(href[4:]).split('?')[0])
        if tag == 'meta' and attrs.get('name', '').lower() == 'viewport':
            self.viewport = True
        if tag == 'title':
            self.title = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)


def parse_page(html):
    parser = PageParser()
    parser.feed(html)
    return parser


def find_emails(html, source_url):
    page = parse_page(html)
    content = ' '.join(page.text + [unquote(link[7:].split('?')[0]) for link in page.links if link.lower().startswith('mailto:')])
    results = []
    for email in sorted(set(match.lower().rstrip('.') for match in EMAIL.findall(content))):
        if email.endswith(('.png', '.jpg', '.svg', '.webp')):
            continue
        role = email.split('@')[0] in ROLES
        results.append({'email': email, 'classification': 'role' if role else 'review_required', 'source_url': source_url})
    return results
