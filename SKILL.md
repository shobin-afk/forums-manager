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
