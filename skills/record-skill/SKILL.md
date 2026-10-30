---
name: record-skill
description: Record a workflow and turn it into a reusable Claude skill — like recording a macro. Use when the user says "record this", "start recording", "stop recording", "turn what we just did into a skill", "make a skill from this session", or wants to capture a procedure (and the corrections they gave along the way) from a current or past Claude Code session as a SKILL.md.
---

# Record a skill

The user does a task once with you; you turn the **real transcript** — the steps that worked, the commands, and especially the user's corrections — into a skill. A skill written from a transcript beats one written from a description, because it contains what actually went wrong and how it was fixed.

Script: `python3 <skill-dir>/scripts/transcript_digest.py` (stdlib only). It reads Claude Code transcripts (`~/.claude/projects/<project>/<session>.jsonl`), keeps user prompts, one line per tool call, failures and short assistant notes, collapses repeated reads, summarizes files and commands, and **redacts secrets**. Never read a raw transcript yourself — it is huge.

## Modes
**A. Record from now** ("start recording")
1. Run `date -u +%Y-%m-%dT%H:%M:%SZ` and remember the timestamp (also write it to `.claude/record-skill.since` so it survives `/clear`).
2. Tell the user in one line: recording; do the task normally; say "stop recording" when done. Then just help with the task — don't narrate the recording.
3. On "stop recording": `transcript_digest.py digest latest --since <timestamp>` → go to **Build**.

**B. From this session** ("turn what we just did into a skill")
`transcript_digest.py digest latest` — if the task started mid-session, add `--from-marker "<words from the prompt that started it>"`.

**C. From a past session**
`transcript_digest.py list` (or `list --all`), confirm the session with the user by its first prompt and date, then `digest <id-prefix>`.

The digest is capped at 12k chars (middle cut). If it says chars were cut, narrow with `--since`, `--from-marker`/`--to-marker`; include subagent work with `--sidechains` only if it matters.

## Build
1. **Extract** from the digest, in this order:
   - **Goal & trigger** — what the user wanted, in their words; when they'd want it again.
   - **Inputs** — what changes between runs (file names, URLs, versions, module names) → parameters. Everything specific to this one run gets generalized.
   - **Steps that survived** — the path that worked, not the dead ends. Merge retries into the final working command.
   - **Corrections** — every `U (after actions)` that redirects you ("no, use…", "don't…", "always…") becomes a rule: `Do X, not Y — because <reason>`. These are the most valuable lines in the skill.
   - **Failures and their fixes** — `✗ failed` lines followed by a fix → "If you see <error>, <fix>".
   - **Verification** — how success was checked (tests, a URL, a file); if nothing was checked, add a check.
   - **Reusable code** — a command or script used more than once or longer than ~5 lines → `scripts/` (re-read the actual file, don't rebuild it from the digest).
2. **Ask at most two questions**, only where the digest can't tell you: what varies between runs, and where to save (`.claude/skills/<name>/` for this project, `~/.claude/skills/<name>/` for all projects, or a skills repo).
3. **Write** `SKILL.md`:
   - Frontmatter: `name` (kebab-case, = folder name) and a `description` that says what it does **and when to use it**, with the trigger phrases the user actually used.
   - Body: one-paragraph purpose → inputs → numbered steps → rules from corrections → "if you see X" table → verification → when NOT to use.
   - Under ~150 lines; long reference material → `references/`, code → `scripts/`.
   - No secrets, tokens, personal paths or customer data; use placeholders (`<PROJECT_DIR>`, `$API_URL`).
4. **Test** before calling it done: give a fresh subagent (with an explicit model) only the new SKILL.md and a similar task with different inputs, and ask it to list the steps it would take. Fix the skill where it would go wrong. If the original run hit an error, check the skill prevents it.
5. Show the user: the skill's path, its description, the rules learned from corrections, and anything you generalized that they should confirm.

## Rules
- Record what **worked**, not the whole history. A skill that repeats the dead ends teaches them.
- The user's corrections outrank your own preferences; keep their wording for rules where you can.
- Don't invent steps that weren't in the session; if a step is obviously missing (e.g. no verification), add it and mark it as added.
- A transcript may contain other people's data or secrets the redactor missed — scan the digest before quoting from it, and never copy credentials into a skill.
- If the session doesn't contain a repeatable procedure (one-off debugging, pure Q&A), say so instead of forcing a skill.

## Improving an existing skill
Same digest, but compare against the current SKILL.md: add only the new corrections, failures and steps, and keep the skill's structure. Show the diff.
