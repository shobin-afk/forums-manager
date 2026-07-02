# forums-manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the three-mode `forums-manager` Claude Code skill (discussion finder, reply writer, question generator) as a self-contained skill mirroring `quora-manager`.

**Architecture:** A `SKILL.md` orchestrates three modes and defers deterministic work (domain parsing, dedup, date parsing, relevance scoring, ranking, table rendering, output naming) to a pure-stdlib `scripts/forums_utils.py`. Style enforcement lives in `references/style-gate.md`. Generated markdown lands in `output/forums-manager/`.

**Tech Stack:** Python 3 (stdlib only) for utils; pytest for tests; Markdown for the skill and references. External work at runtime uses WebFetch, Apify MCP, FireCrawl MCP, and DataForSEO MCP (not exercised by unit tests).

## Global Constraints

- Skill root dir: `d:\Claude Code\Claude Skills\Forums Manager` (spaces in path — quote in shells).
- `scripts/forums_utils.py`: **stdlib only**, no third-party imports. Run with system `python`.
- Draft only — the skill never posts to any forum.
- Reddit is out of scope (handled by separate tooling).
- Tool priority for all page reads: WebFetch primary → Apify → FireCrawl last. DataForSEO used only for keyword seed expansion.
- Output written to `output/forums-manager/<timestamp>-<mode>.md` AND printed to chat.
- Style gate (`references/style-gate.md`) is a hard gate on all Mode 2/3 generated text: no em-dashes, no banned AI-slop phrases.
- Mode 1: min 5, max 20 discussions per forum; single relevance-ranked table per forum.
- Mode 2: 3 replies, all mention brand (distinct angles) when brand provided.
- Mode 3: 3 question variations.

---

### Task 1: Scaffold + domain/query helpers

**Files:**
- Create: `scripts/forums_utils.py`
- Create: `tests/test_forums_utils.py`
- Create: `output/forums-manager/.gitkeep` (empty)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `domain_of(url: str) -> str` — registrable netloc, `www.` stripped, lowercased.
  - `build_site_query(domain: str, term: str) -> str` — Google `site:` query string.
  - `same_domain(url: str, domain: str) -> bool` — True if url's domain equals or is a subdomain of `domain`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_forums_utils.py
from datetime import date
import scripts.forums_utils as fu


def test_domain_of_strips_www_and_lowercases():
    assert fu.domain_of("https://WWW.Example.com/forum/thread-1") == "example.com"


def test_build_site_query_quotes_term():
    assert fu.build_site_query("example.com", " garage cleanout ") == 'site:example.com "garage cleanout"'


def test_same_domain_matches_subdomains():
    assert fu.same_domain("https://community.example.com/t/5", "example.com") is True
    assert fu.same_domain("https://example.com.evil.com/x", "example.com") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_forums_utils.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.forums_utils'` (or `AttributeError`).

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/forums_utils.py
"""Pure stdlib helpers for the forums-manager skill."""
import re
from datetime import date, timedelta
from urllib.parse import urlsplit


def domain_of(url):
    netloc = urlsplit(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def build_site_query(domain, term):
    return 'site:%s "%s"' % (domain, term.strip())


def same_domain(url, domain):
    d = domain_of(url)
    domain = domain.lower()
    return d == domain or d.endswith("." + domain)
```

Also create `tests/__init__.py` (empty) and `scripts/__init__.py` (empty) so imports resolve, and `output/forums-manager/.gitkeep` (empty).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_forums_utils.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/ tests/ output/
git commit -m "feat: scaffold forums-manager utils with domain/query helpers"
```

---

### Task 2: URL dedup

**Files:**
- Modify: `scripts/forums_utils.py`
- Modify: `tests/test_forums_utils.py`

**Interfaces:**
- Consumes: `domain_of`.
- Produces: `dedup_by_url(items: list[dict]) -> list[dict]` — keeps first occurrence; dedup key ignores scheme case, `www.`, trailing slash, and path case.

- [ ] **Step 1: Write the failing test**

```python
def test_dedup_by_url_normalizes_and_keeps_first():
    items = [
        {"url": "https://example.com/Thread/1/", "title": "a"},
        {"url": "http://WWW.example.com/thread/1", "title": "b"},
        {"url": "https://example.com/thread/2", "title": "c"},
    ]
    out = fu.dedup_by_url(items)
    assert [i["title"] for i in out] == ["a", "c"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_forums_utils.py::test_dedup_by_url_normalizes_and_keeps_first -v`
Expected: FAIL with `AttributeError: module ... has no attribute 'dedup_by_url'`.

- [ ] **Step 3: Write minimal implementation**

```python
def _normalize_url(url):
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    return "%s://%s%s" % (parts.scheme.lower(), domain_of(url), path.lower())


def dedup_by_url(items):
    seen = set()
    out = []
    for item in items:
        key = _normalize_url(item["url"])
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_forums_utils.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/forums_utils.py tests/test_forums_utils.py
git commit -m "feat: add URL dedup helper"
```

---

### Task 3: Date parsing + recency label

**Files:**
- Modify: `scripts/forums_utils.py`
- Modify: `tests/test_forums_utils.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `parse_relative_date(text: str, today: date) -> date | None` — parses absolute ("Jan 5, 2026") or relative ("2 months ago"); returns None if neither found.
  - `recency_label(d: date | None, today: date) -> str` — human string ("~3 days", "~2 weeks", "~4 months", "~1 years") or "unknown".

- [ ] **Step 1: Write the failing test**

```python
def test_parse_relative_date_absolute():
    assert fu.parse_relative_date("posted Jan 5, 2026", date(2026, 7, 2)) == date(2026, 1, 5)


def test_parse_relative_date_relative():
    assert fu.parse_relative_date("2 months ago", date(2026, 7, 2)) == date(2026, 7, 2) - timedelta(days=61)


def test_parse_relative_date_none():
    assert fu.parse_relative_date("no date here", date(2026, 7, 2)) is None


def test_recency_label_buckets():
    today = date(2026, 7, 2)
    assert fu.recency_label(None, today) == "unknown"
    assert fu.recency_label(today - timedelta(days=3), today) == "~3 days"
    assert fu.recency_label(today - timedelta(days=21), today) == "~3 weeks"
    assert fu.recency_label(today - timedelta(days=61), today) == "~2 months"
    assert fu.recency_label(today - timedelta(days=400), today) == "~1 years"
```

Add `from datetime import timedelta` to the test imports (update the top import line to `from datetime import date, timedelta`).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_forums_utils.py -k "date or recency" -v`
Expected: FAIL (`parse_relative_date` / `recency_label` not defined).

- [ ] **Step 3: Write minimal implementation**

```python
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

_REL_RE = re.compile(r"(\d+)\s+(day|week|month|year)s?\s+ago", re.I)
_ABS_RE = re.compile(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})")


def parse_relative_date(text, today):
    m = _ABS_RE.search(text)
    if m:
        mon = _MONTHS.get(m.group(1)[:3].lower())
        if mon:
            return date(int(m.group(3)), mon, int(m.group(2)))
    m = _REL_RE.search(text)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        days = {"day": 1, "week": 7, "month": 30.5, "year": 365}[unit] * n
        return today - timedelta(days=int(days))
    return None


def recency_label(d, today):
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_forums_utils.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/forums_utils.py tests/test_forums_utils.py
git commit -m "feat: add relative/absolute date parsing and recency labels"
```

---

### Task 4: Relevance scoring + band

**Files:**
- Modify: `scripts/forums_utils.py`
- Modify: `tests/test_forums_utils.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `keyword_relevance(title: str, snippet: str, keywords: list[str]) -> int` — 0-10 score; weights keyword coverage (x8) plus a title-match bonus (x2).
  - `relevance_band(score: int) -> str` — "High" (>=7), "Med" (>=4), else "Low".

- [ ] **Step 1: Write the failing test**

```python
def test_keyword_relevance_full_match_in_title():
    s = fu.keyword_relevance("Junk removal cost in LA", "cheap options", ["junk removal", "cost"])
    assert s == 10


def test_keyword_relevance_partial():
    s = fu.keyword_relevance("Best junk removal", "no price info", ["junk removal", "cost"])
    assert s == 5


def test_keyword_relevance_no_keywords():
    assert fu.keyword_relevance("anything", "anything", []) == 0


def test_relevance_band():
    assert fu.relevance_band(10) == "High"
    assert fu.relevance_band(7) == "High"
    assert fu.relevance_band(5) == "Med"
    assert fu.relevance_band(4) == "Med"
    assert fu.relevance_band(3) == "Low"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_forums_utils.py -k "relevance or band" -v`
Expected: FAIL (functions not defined).

- [ ] **Step 3: Write minimal implementation**

```python
def keyword_relevance(title, snippet, keywords):
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
    if score >= 7:
        return "High"
    if score >= 4:
        return "Med"
    return "Low"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_forums_utils.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/forums_utils.py tests/test_forums_utils.py
git commit -m "feat: add keyword relevance scoring and banding"
```

---

### Task 5: Ranking + table rendering

**Files:**
- Modify: `scripts/forums_utils.py`
- Modify: `tests/test_forums_utils.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `rank_questions(items: list[dict], keywords: list[str], today: date) -> list[dict]` — sorts by `relevance_score` desc, then dated-before-undated, then newest first. Each item may carry `relevance_score` and `date`.
  - `render_forum_table(rows: list[dict]) -> str` — markdown table; each row uses keys `title`, `url`, `recency`, `relevance`.

- [ ] **Step 1: Write the failing test**

```python
def test_rank_questions_orders_by_score_then_recency():
    today = date(2026, 7, 2)
    items = [
        {"title": "low", "relevance_score": 2, "date": today},
        {"title": "high-old", "relevance_score": 9, "date": date(2026, 1, 1)},
        {"title": "high-new", "relevance_score": 9, "date": date(2026, 6, 1)},
        {"title": "high-nodate", "relevance_score": 9, "date": None},
    ]
    out = fu.rank_questions(items, ["x"], today)
    assert [i["title"] for i in out] == ["high-new", "high-old", "high-nodate", "low"]


def test_render_forum_table_escapes_pipes():
    rows = [{"title": "a|b", "url": "u", "recency": "~2 months", "relevance": "High"}]
    md = fu.render_forum_table(rows)
    assert "| 1 | a\\|b | u | ~2 months | High |" in md
    assert md.splitlines()[0].startswith("| # | Question | URL |")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_forums_utils.py -k "rank or render" -v`
Expected: FAIL (functions not defined).

- [ ] **Step 3: Write minimal implementation**

```python
def rank_questions(items, keywords, today):
    def key(item):
        score = item.get("relevance_score", 0)
        d = item.get("date")
        has_date = 0 if d is not None else 1
        ordinal = d.toordinal() if d is not None else 0
        return (-score, has_date, -ordinal)
    return sorted(items, key=key)


def _cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def render_forum_table(rows):
    header = "| # | Question | URL | Recency | Relevance |"
    sep = "| --- | --- | --- | --- | --- |"
    lines = [header, sep]
    for i, r in enumerate(rows, start=1):
        lines.append("| %d | %s | %s | %s | %s |" % (
            i, _cell(r.get("title", "")), _cell(r.get("url", "")),
            _cell(r.get("recency", "")), _cell(r.get("relevance", ""))))
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_forums_utils.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/forums_utils.py tests/test_forums_utils.py
git commit -m "feat: add ranking and forum table rendering"
```

---

### Task 6: Output filename

**Files:**
- Modify: `scripts/forums_utils.py`
- Modify: `tests/test_forums_utils.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `output_filename(mode: str, now) -> str` — `YYYY-MM-DD-HHMM-<slug>.md`; `now` is a `datetime`.

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime


def test_output_filename_slug_and_stamp():
    now = datetime(2026, 7, 2, 9, 5)
    assert fu.output_filename("Mode 1 Finder", now) == "2026-07-02-0905-mode-1-finder.md"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_forums_utils.py -k "output_filename" -v`
Expected: FAIL (`output_filename` not defined).

- [ ] **Step 3: Write minimal implementation**

```python
def output_filename(mode, now):
    slug = re.sub(r"[^a-z0-9]+", "-", mode.lower()).strip("-")
    return "%s-%s.md" % (now.strftime("%Y-%m-%d-%H%M"), slug)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_forums_utils.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/forums_utils.py tests/test_forums_utils.py
git commit -m "feat: add output filename helper"
```

---

### Task 7: Style gate reference

**Files:**
- Create: `references/style-gate.md`

**Interfaces:**
- Consumes: nothing.
- Produces: a reference doc the SKILL.md points to for Mode 2/3 style enforcement.

- [ ] **Step 1: Write the reference file**

```markdown
# Anti-AI-Tell Style Gate

Run this self-check before outputting any Mode 2 reply or Mode 3 question.

## Hard bans (must not appear)
- Em-dashes. Use commas, periods, or parentheses.
- Phrases: "delve", "in today's world", "it's worth noting", "navigate"
  (figurative), "tapestry", "elevate", "game-changer", "when it comes to",
  "dive in", "at the end of the day", "that being said", "a testament to",
  "in the ever-evolving", "unlock", "seamless", "robust".
- Robotic tricolons (three parallel items for rhythm alone).
- Uniform sentence length across a paragraph.

## Enforce (must be present)
- Varied sentence length and rhythm.
- Contractions (it's, you'll, don't).
- Concrete specifics: real names, real numbers, real places over vague filler.
- Natural conversational voice, matched to the target community.

## Character
- Funny, sarcastic, or self-deprecating is welcome. Never insulting. Never overboard.

## Formatting
- Short paragraphs only. No wall-of-text blocks.
- Bullet lists and numbered lists welcome.
- Emojis allowed but sparing (0-2 per reply/question).

## Brand placement (Mode 2 / Mode 3)
- When a brand is provided, integrate it naturally so it reads like a real
  member's recommendation, not an ad. Never force it; make it earn its place.
```

- [ ] **Step 2: Verify content**

Run: `grep -c "Hard bans" references/style-gate.md`
Expected: `1`.

- [ ] **Step 3: Commit**

```bash
git add references/style-gate.md
git commit -m "docs: add anti-AI-tell style gate reference"
```

---

### Task 8: SKILL.md

**Files:**
- Create: `SKILL.md`

**Interfaces:**
- Consumes: `scripts/forums_utils.py` helpers (by name), `references/style-gate.md`.
- Produces: the skill entry point with frontmatter and all three mode workflows.

- [ ] **Step 1: Write SKILL.md**

Write the file with exactly this content:

````markdown
---
name: forums-manager
description: Three-mode forum/community toolkit. Mode 1 finds recent relevant discussions across a list of forum URLs from keywords (DataForSEO + Apify), one section per forum. Mode 2 drafts 3 genuine, human-sounding replies to a thread URL, weaving in an optional brand. Mode 3 generates 3 authentic community-voiced questions on a topic, weaving in an optional brand. Draft only, never posts. Reddit excluded. Triggers - "forums manager", "find forum discussions", "reply to forum thread", "generate forum question", "/forums-manager".
---

# Forums Manager

One skill, three modes. Draft only — never posts. Reddit excluded (use separate tooling).

## Mode detection
- Input has a list of forum URLs + keywords -> **Mode 1** (discussion finder).
- Input has a single thread URL (+ optional brand) -> **Mode 2** (reply writer).
- Input has a forum/section URL + a topic (+ optional brand) -> **Mode 3** (question generator).
- Explicit prefix `find:` / `reply:` / `generate:` overrides detection.
- Ambiguous -> ask the user which mode, once.

## Tool priority (all page reads)
- **WebFetch** — primary for reading thread and forum pages.
- **Apify** — discovery (Google Search Scraper, `site:` per forum) and heavy/JS pages WebFetch cannot render.
- **FireCrawl** — last resort when both fail (Cloudflare-gated). Use `proxy: "stealth"`, `waitFor: 6000`, `onlyMainContent: true`.
- **DataForSEO MCP** — keyword seed expansion only.

## Shared setup
- Helpers: `scripts/forums_utils.py` (stdlib only). Run with system `python`.
- Output: print to chat AND write `output_filename(mode, now)` into `output/forums-manager/`.
- Honesty: never pad counts; report real numbers and name any degraded step.

## Mode 1 — Discussion Finder
Input: `forum_urls[]` (1+), `keywords[]` (1+).

1. **Domains** — `domain_of(url)` for each forum URL.
2. **Seed expansion** — feed keywords to DataForSEO
   (`dataforseo_labs_google_keyword_suggestions`,
   `dataforseo_labs_google_related_keywords`, plus PAA/search-intent). Reshape
   into short problem/question phrasings people actually ask (not raw commercial
   terms). If DataForSEO errors, keep the reasoned keywords and mark volume
   `n/a` (non-blocking).
3. **Discovery** — per forum, run Apify Google Search Scraper with
   `build_site_query(domain, term)` and a past-6-months date filter. Collect
   url + title + snippet.
4. **Dedupe** — `dedup_by_url`; keep only URLs where `same_domain(url, domain)`.
5. **Date + score** — `parse_relative_date(snippet, today)` -> `date`;
   `keyword_relevance(title, snippet, keywords)` -> `relevance_score`;
   `recency_label(date, today)` -> `recency`; `relevance_band(score)` ->
   `relevance`.
6. **Loop** — expand more seed terms and fire more queries until at least 5
   qualifying threads exist per forum, capping at 20. If a forum yields fewer
   than 5, report the shortfall; never pad.
7. **Render** — for each forum, emit an `## <Forum name>` heading, then
   `render_forum_table(rank_questions(items, keywords, today)[:20])`. Print to
   chat and write ONE output file containing every forum's section.

**Seed-term note:** DataForSEO often returns commercial/navigational variants.
Before firing, reshape seeds into short problem/question phrasings ("junk
removal cost", "how to get rid of old furniture") — these surface real question
threads; raw local-business terms rarely do.

## Mode 2 — Reply Writer
Input: one thread URL, optional brand name. Draft only.

1. **Fetch** the original post and all comments/answers via the tool-priority
   chain (WebFetch -> Apify -> FireCrawl). If every path fails, tell the user;
   never fabricate thread content.
2. **Analyze** the real question intent, gaps in existing answers, and the
   platform's culture, tone, and style (formality, typical length, humor, jargon).
3. **Research facts** — the topic and, if a location is named, that location, via
   WebSearch + Firecrawl. Facts, prices, options, and named entities must be
   real/researched. First-person anecdotes are plausible illustrative composites
   in the community's voice, never claimed as specific verified events.
4. **Draft 3 replies**, each a distinct angle (e.g. personal-experience,
   comparison, casual-aside). If a brand is provided, all 3 weave it in naturally
   from different angles. If no brand, 3 genuine helpful replies.
5. **Voice** — match the community. Character welcome (funny, sarcastic,
   self-deprecating); never insulting, never overboard.
6. **Style gate** — apply every rule in `references/style-gate.md`.
7. **Output** — print the 3 replies and write the output file.

## Mode 3 — Question Generator
Input: forum/section URL, topic/keyword, optional brand name.

1. **Read** several ongoing threads at the URL (WebFetch -> fallbacks) to learn
   the community's tone, culture, and style.
2. **Research** the topic (and location, if named).
3. **Generate 3 distinct on-topic questions** in the community's authentic voice,
   with the brand woven in naturally if provided.
4. **Style gate** — apply every rule in `references/style-gate.md`.
5. **Output** — print the 3 questions and write the output file.
````

- [ ] **Step 2: Verify frontmatter and modes present**

Run: `python -c "import re,io; t=open('SKILL.md',encoding='utf-8').read(); assert t.startswith('---'); assert 'name: forums-manager' in t; assert all(m in t for m in ['Mode 1','Mode 2','Mode 3']); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add SKILL.md
git commit -m "feat: add forums-manager SKILL.md with three modes"
```

---

### Task 9: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the whole test suite**

Run: `python -m pytest tests/ -v`
Expected: all tests PASS (Tasks 1-6).

- [ ] **Step 2: Sanity-check the tree**

Run: `python -c "import os; [print(p) for p in ['SKILL.md','scripts/forums_utils.py','references/style-gate.md','output/forums-manager'] if os.path.exists(p)]"`
Expected: all four paths printed.

- [ ] **Step 3: Commit (if anything changed)**

```bash
git add -A
git commit -m "chore: forums-manager complete" || echo "nothing to commit"
```

---

## Self-Review

**Spec coverage:**
- Mode 1 discovery (Apify site: search) → Tasks 1, 8. Seed expansion (DataForSEO) → Task 8. Dedup/date/score/rank/render → Tasks 2-6, 8. Per-forum sections, 5-20 bounds → Task 8. ✓
- Mode 2 (3 brand-aware replies, fetch chain, style gate) → Task 8 + Task 7. ✓
- Mode 3 (3 brand-aware questions, culture read, style gate) → Task 8 + Task 7. ✓
- Tool priority, honesty, output location → Global Constraints + Task 8. ✓
- Reddit excluded → frontmatter + Global Constraints. ✓
- style-gate.md content → Task 7. ✓

**Placeholder scan:** No TBD/TODO; all code and commands are concrete. ✓

**Type consistency:** `domain_of`, `build_site_query`, `same_domain`, `dedup_by_url`, `parse_relative_date`, `recency_label`, `keyword_relevance`, `relevance_band`, `rank_questions`, `render_forum_table`, `output_filename` — names identical across Interfaces, tests, impl, and SKILL.md references. ✓

**Note:** Working dir is not a git repo. Either `git init` first, or treat the `git commit` steps as optional checkpoints.
