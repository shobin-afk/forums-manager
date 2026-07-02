# forums-manager

A three-mode Claude Code skill for working with online forums and communities. It
**drafts only and never posts**. Reddit is out of scope (use dedicated Reddit tooling).

Modes:

1. **Discussion Finder** - given a list of forum URLs and keywords, find recent relevant
   discussions per forum and write one markdown file, one section per forum.
2. **Reply Writer** - given a thread URL and an optional brand name, draft 3 genuine,
   human-sounding replies that weave the brand in naturally.
3. **Question Generator** - given a forum/section URL, a topic, and an optional brand
   name, draft 3 authentic community-voiced questions.

All generated text passes an anti-AI-tell style gate: no em-dashes, no AI-slop phrases,
varied rhythm, contractions, concrete specifics.

## Install

Copy the skill into your Claude Code skills directory:

```bash
cp -r forums-manager ~/.claude/skills/forums-manager
```

It then loads automatically. Invoke with `/forums-manager` or triggers like
"find forum discussions", "reply to forum thread", "generate forum question".

## Usage

Mode is auto-detected from the input, or forced with a `find:` / `reply:` / `generate:`
prefix.

- **Mode 1:** a list of forum URLs plus keywords.
- **Mode 2:** a single thread URL, optional brand name.
- **Mode 3:** a forum or section URL, a topic, optional brand name.

Output is printed to chat and written to `output/forums-manager/<timestamp>-<mode>.md`.

## Tool priority

- **WebFetch** - primary for reading thread and forum pages.
- **Apify** - discovery (Google Search Scraper, `site:` per forum) and JS-heavy pages.
- **FireCrawl** - last resort for Cloudflare-gated pages (`proxy: "stealth"`).
- **DataForSEO MCP** - keyword seed expansion only.

## Layout

```
SKILL.md                     # entry point, mode workflows
scripts/forums_utils.py      # stdlib helpers: dedup, date parse, scoring, ranking, render
references/style-gate.md      # anti-AI-tell rules enforced on Mode 2/3 output
tests/test_forums_utils.py    # 19 unit tests (python -m pytest tests/)
examples/                     # real outputs from each mode (see below)
docs/superpowers/             # design spec + implementation plan
```

## Examples

Real outputs from a live run against `forums.macrumors.com` (keywords: "battery health",
"battery replacement"; brand: iMazing):

- [`examples/mode1-finder.md`](examples/mode1-finder.md) - 20 ranked discussions
- [`examples/mode2-reply.md`](examples/mode2-reply.md) - 3 brand-woven replies
- [`examples/mode3-question.md`](examples/mode3-question.md) - 3 community-voiced questions

## Tests

```bash
python -m pytest tests/ -v
```

## Notes

- Draft only. This skill never posts to any forum.
- Facts must be real/researched; first-person anecdotes are illustrative composites in
  the community's voice, never claimed as verified events.
