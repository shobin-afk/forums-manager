from datetime import date, timedelta, datetime
import scripts.forums_utils as fu


# Task 1: Domain and query helpers
def test_domain_of_strips_www_and_lowercases():
    assert fu.domain_of("https://WWW.Example.com/forum/thread-1") == "example.com"


def test_build_site_query_quotes_term():
    assert fu.build_site_query("example.com", " garage cleanout ") == 'site:example.com "garage cleanout"'


def test_same_domain_matches_subdomains():
    assert fu.same_domain("https://community.example.com/t/5", "example.com") is True
    assert fu.same_domain("https://example.com.evil.com/x", "example.com") is False


# Task 2: URL dedup
def test_dedup_by_url_normalizes_and_keeps_first():
    items = [
        {"url": "https://example.com/Thread/1/", "title": "a"},
        {"url": "http://WWW.example.com/thread/1", "title": "b"},
        {"url": "https://example.com/thread/2", "title": "c"},
    ]
    out = fu.dedup_by_url(items)
    assert [i["title"] for i in out] == ["a", "c"]


# Task 3: Date parsing and recency label
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


# Task 4: Relevance scoring and band
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


# Task 5: Ranking and table rendering
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


# Task 6: Output filename
def test_output_filename_slug_and_stamp():
    now = datetime(2026, 7, 2, 9, 5)
    assert fu.output_filename("Mode 1 Finder", now) == "2026-07-02-0905-mode-1-finder.md"
