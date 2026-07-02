"""Pure stdlib helpers for the forums-manager skill."""
import re
from datetime import date, timedelta
from urllib.parse import urlsplit


# Task 1: Domain and query helpers
def domain_of(url):
    """Extract registrable netloc from URL, strip www., lowercase."""
    netloc = urlsplit(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def build_site_query(domain, term):
    """Build Google site: query string with quoted term."""
    return 'site:%s "%s"' % (domain, term.strip())


def same_domain(url, domain):
    """Check if URL's domain equals or is a subdomain of domain."""
    d = domain_of(url)
    domain = domain.lower()
    return d == domain or d.endswith("." + domain)


# Task 2: URL dedup
def _normalize_url(url):
    """Normalize URL for dedup: ignore scheme, lowercase domain, path, and keep query string."""
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    q = "?" + parts.query if parts.query else ""
    return "%s%s%s" % (domain_of(url), path.lower(), q)


def dedup_by_url(items):
    """Dedup items by normalized URL, keeping first occurrence. Skips items without a url."""
    seen = set()
    out = []
    for item in items:
        url = item.get("url")
        if not url:
            continue
        key = _normalize_url(url)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


# Task 3: Date parsing and recency label
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

_REL_RE = re.compile(r"(\d+)\s+(day|week|month|year)s?\s+ago", re.I)
_ABS_RE = re.compile(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})")


def parse_relative_date(text, today):
    """Parse absolute (Jan 5, 2026) or relative (2 months ago) date strings."""
    m = _ABS_RE.search(text)
    if m:
        mon = _MONTHS.get(m.group(1)[:3].lower())
        if mon:
            try:
                return date(int(m.group(3)), mon, int(m.group(2)))
            except ValueError:
                pass
    m = _REL_RE.search(text)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        days = {"day": 1, "week": 7, "month": 30.5, "year": 365}[unit] * n
        return today - timedelta(days=int(days))
    return None


def recency_label(d, today):
    """Convert date to human-readable recency label."""
    if d is None:
        return "unknown"
    days = (today - d).days
    if days < 0:
        days = 0
    if days < 10:
        return "~%d days" % max(days, 1)
    if days < 45:
        return "~%d weeks" % round(days / 7)
    if days < 400:
        return "~%d months" % round(days / 30.5)
    return "~%d years" % round(days / 365)


# Task 4: Relevance scoring and band
def keyword_relevance(title, snippet, keywords):
    """Score 0-10 based on keyword coverage (x8) + title bonus (x2)."""
    if not keywords:
        return 0
    hay_title = title.lower()
    hay_all = (title + " " + snippet).lower()
    matched = sum(1 for k in keywords if k.lower() in hay_all)
    in_title = sum(1 for k in keywords if k.lower() in hay_title)
    n = len(keywords)
    score = (matched / n) * 8 + (in_title / n) * 2
    return round(min(10, score))


def relevance_band(score):
    """Categorize score into High (>=7), Med (>=4), Low."""
    if score >= 7:
        return "High"
    if score >= 4:
        return "Med"
    return "Low"


# Task 5: Ranking and table rendering
def rank_questions(items, keywords, today):
    """Sort by relevance_score desc, then dated before undated, then newest first."""
    def key(item):
        score = item.get("relevance_score", 0)
        d = item.get("date")
        has_date = 0 if d is not None else 1
        ordinal = d.toordinal() if d is not None else 0
        return (-score, has_date, -ordinal)
    return sorted(items, key=key)


def _cell(text):
    """Escape pipe and newlines in table cell."""
    return str(text).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def render_forum_table(rows):
    """Render markdown table with title, url, recency, relevance columns."""
    header = "| # | Question | URL | Recency | Relevance |"
    sep = "| --- | --- | --- | --- | --- |"
    lines = [header, sep]
    for i, r in enumerate(rows, start=1):
        lines.append("| %d | %s | %s | %s | %s |" % (
            i, _cell(r.get("title", "")), _cell(r.get("url", "")),
            _cell(r.get("recency", "")), _cell(r.get("relevance", ""))))
    return "\n".join(lines)


# Task 6: Output filename
def output_filename(mode, now):
    """Generate output filename: YYYY-MM-DD-HHMM-<slug>.md."""
    slug = re.sub(r"[^a-z0-9]+", "-", mode.lower()).strip("-")
    return "%s-%s.md" % (now.strftime("%Y-%m-%d-%H%M"), slug)
