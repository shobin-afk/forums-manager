# forums-manager — Design Spec

**Date:** 2026-07-02
**Status:** Approved for planning

## Overview

`forums-manager` is a three-mode Claude Code skill for working with online forums and
communities. It generalizes the existing `quora-manager` skill from a single platform
(Quora) to arbitrary forums/communities. It **drafts only and never posts**.

Three modes:
1. **Discussion Finder** — given a list of forum URLs + keywords, find relevant
   discussions per forum and output one markdown file, sectioned by forum.
2. **Reply Writer** — given a thread URL and optional brand name, craft 3 genuine,
   human-sounding replies that weave the brand in naturally.
3. **Question Generator** — given a forum/section URL, a topic, and optional brand
   name, craft 3 authentic, community-voiced questions.

## Design decisions (resolved)

| Question | Decision |
|----------|----------|
| Mode 1 discovery | Apify Google Search Scraper with `site:domain` per forum |
| Mode 1 output shape | Single relevance-ranked table per forum |
| Mode 2 brand handling | All 3 replies mention brand, from distinct angles |
| Platform scope | Generic forums; **Reddit excluded** (handled by separate tooling) |
| Mode 3 count | 3 variations |
| Build approach | Self-contained, mirroring quora-manager (own scripts + references) |

## File structure

```
Forums Manager/
  SKILL.md
  scripts/forums_utils.py     # stdlib only: dedup, date-parse, relevance-score, table render
  references/style-gate.md    # anti-AI-tell rules (adapted from quora-manager)
  output/forums-manager/      # generated .md files
```

### Frontmatter

- `name: forums-manager`
- `description:` three-mode summary + triggers: `forums manager`, `find forum discussions`,
  `reply to forum thread`, `generate forum question`, `/forums-manager`.

## Mode detection

Read user input and pick:
- List of forum URLs + keywords → **Mode 1**.
- Single thread URL (+ optional brand) → **Mode 2**.
- Forum/section URL + topic (+ optional brand) → **Mode 3**.
- Explicit prefix `find:` / `reply:` / `generate:` overrides detection.
- Ambiguous → ask the user which mode, once.

## Tool priority (global)

Applies to all page reads unless a step states otherwise.
- **WebFetch** — primary for reading thread and forum pages.
- **Apify** — discovery (Google Search Scraper, `site:` per forum) and heavy/JS pages
  WebFetch cannot render.
- **FireCrawl** — last resort when both fail (e.g. Cloudflare-gated pages), using
  `proxy: "stealth"`, `waitFor: 6000`, `onlyMainContent: true`.
- **DataForSEO MCP** — keyword seed expansion only.

## Mode 1 — Discussion Finder

**Input:** `forum_urls[]` (1+), `keywords[]` (1+).
**Output:** one markdown file, one section per forum, 5-20 discussion rows each.

1. Extract the registrable domain from each forum URL.
2. **Seed expansion** — feed keywords to DataForSEO
   (`dataforseo_labs_google_keyword_suggestions`,
   `dataforseo_labs_google_related_keywords`, plus PAA/search-intent). Reshape into
   short problem/question phrasings people actually ask (not raw commercial terms).
   If DataForSEO errors, keep the reasoned keywords and mark volume `n/a` (non-blocking).
3. **Discovery** — per forum, run Apify Google Search Scraper with
   `site:<domain> <seed term>` and a past-6-months date filter. Collect url + title +
   snippet.
4. **Dedupe** — dedup by URL; keep only URLs on that forum's domain.
5. **Date + score** — parse relative dates from snippets; relevance-score each thread
   0-10 against the original keywords. Keep unknown-date items (best-effort recency).
6. **Loop** — expand more seed terms and fire more queries until at least 5 qualifying
   threads exist per forum (minimum), capping at 20 (maximum). If a forum yields fewer
   than 5, report the shortfall honestly; never pad.
7. **Render** — for each forum: an `## <Forum name>` heading followed by a single
   relevance-ranked table. Columns: `title`, `url`, `recency` (human string, e.g.
   "~2 months" or "unknown"), `relevance` (High/Med/Low). Newest as relevance
   tiebreaker. Print to chat and write the output file.

## Mode 2 — Reply Writer

**Input:** one thread URL, optional brand/business name. Draft only.
**Output:** 3 paste-ready replies.

1. **Fetch** the original post and all comments/answers using the tool-priority chain
   (WebFetch → Apify → FireCrawl). If every path fails, tell the user; never fabricate
   thread content.
2. **Analyze** the thread: real question intent, gaps in existing answers, and the
   platform's culture, tone, and style (formality, typical length, humor, jargon).
3. **Research facts** — the topic and, if a location is named, that location, via
   WebSearch + Firecrawl. Facts, prices, options, and named entities must be
   real/researched. First-person anecdotes are plausible illustrative composites in the
   community's voice, never claimed as specific verified events.
4. **Draft 3 replies**, each a distinct angle (e.g. personal-experience, comparison,
   casual-aside). If a brand is provided, **all 3 weave it in naturally** from different
   angles. If no brand, produce 3 genuine helpful replies.
5. **Voice** — match the community's tone. Character is welcome (funny, sarcastic,
   self-deprecating) but never insulting and never overboard.
6. **Style gate** — apply every rule in `references/style-gate.md`: no em-dashes, no
   banned AI-slop phrases, varied rhythm, contractions, concrete specifics.
7. **Output** — print the 3 replies and write the output file.

## Mode 3 — Question Generator

**Input:** forum/section URL (section or main), topic/keyword, optional brand name.
**Output:** 3 question variations.

1. **Read** several ongoing threads/discussions at the URL (WebFetch → fallbacks) to
   learn the community's tone, culture, and style.
2. **Research** the topic (and location, if named).
3. **Generate 3 distinct on-topic questions** in the community's authentic voice, with
   the brand woven in naturally if provided.
4. **Style gate** — apply every rule in `references/style-gate.md`. Character yes,
   insulting no.
5. **Output** — print the 3 questions and write the output file.

## Shared rules

- `scripts/forums_utils.py`: stdlib only; run with system `python`. Provides dedup,
  relative-date parsing, relevance scoring, recency ranking, table rendering, and
  output-filename helpers.
- **Honesty** — never pad counts; report real numbers and name any degraded step.
- **Output** — print to chat AND write to `output/forums-manager/<mode>-<timestamp>.md`.
- **Style gate** — hard gate on all Mode 2 and Mode 3 generated text.

## references/style-gate.md (content)

Anti-AI-tell rules copied/adapted from quora-manager:
- **Hard bans:** em-dashes; phrases like "delve", "in today's world", "it's worth
  noting", figurative "navigate", "tapestry", "elevate", "game-changer", "when it comes
  to", "dive in", "at the end of the day", "that being said", "a testament to", "in the
  ever-evolving", "unlock", "seamless", "robust"; robotic tricolons; uniform sentence
  length.
- **Enforce:** varied sentence length, contractions, concrete specifics, natural
  conversational voice.
- **Formatting:** short paragraphs, bullet/numbered lists welcome, emojis sparing (0-2).

## Out of scope

- Posting to any forum (draft only, always).
- Reddit (covered by separate tooling).
- Account/login handling beyond optional user-supplied cookies for a gated fetch.
