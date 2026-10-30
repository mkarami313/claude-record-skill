# record-skill

Record a workflow once and turn the real Claude Code session into a reusable skill — like recording a macro.

A [Claude skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) for Claude Code — Python 3 standard library only, no dependencies. Part of the [mkarami313/Claude-skill](https://github.com/mkarami313/Claude-skill) collection.

Record a workflow once and get a skill — like recording a macro. Instead of describing a procedure from memory, Claude builds the skill from the **real session transcript**: the steps that worked, the commands, the errors and how they were fixed, and — most valuable — every correction you gave along the way.

**Use it when** you say "start recording" … "stop recording", "turn what we just did into a skill", or "make a skill from yesterday's session".

## How it works
| Step | What happens |
|---|---|
| Record | "Start recording" saves a timestamp; you work normally; "stop recording" ends it. Or point at the current or a past session. |
| Digest | `transcript_digest.py` reads the Claude Code transcript (`~/.claude/projects/…/<session>.jsonl`) and compresses it: user prompts, one line per tool call, failures, short notes, files and commands summary. Secrets are redacted; long digests are cut from the middle. |
| Build | Claude extracts goal, inputs (parameters), the steps that survived, rules from your corrections, "if you see X" fixes, and verification; reusable commands go to `scripts/`. |
| Test | A fresh subagent gets only the new SKILL.md and a similar task with different inputs; the skill is fixed where it would go wrong. |

## Digest script
```bash
python3 skills/record-skill/scripts/transcript_digest.py list                 # sessions of this project
python3 skills/record-skill/scripts/transcript_digest.py digest latest --since 2026-10-30T07:00:00Z
python3 skills/record-skill/scripts/transcript_digest.py digest <id> --from-marker "deploy the" --no-text
```

## What's inside
```
skills/record-skill/
├── SKILL.md                     record modes, extraction rules, SKILL.md template, testing
└── scripts/
    └── transcript_digest.py     list sessions; digest one into a short, redacted timeline
```

## Installation

### Claude Code — plugin marketplace (recommended)
```
/plugin marketplace add mkarami313/claude-record-skill
/plugin install record-skill@claude-record-skill
```
Update later with `/plugin marketplace update claude-record-skill`.

### Claude Code — copy the skill folder
```bash
git clone https://github.com/mkarami313/claude-record-skill
cp -r claude-record-skill/skills/record-skill <your-repo>/.claude/skills/     # this project only
cp -r claude-record-skill/skills/record-skill ~/.claude/skills/               # all your projects
```

### Claude.ai / Claude desktop app
Zip the folder so that `record-skill/SKILL.md` is at the root of the archive and upload it in Claude's skills settings:
```bash
cd claude-record-skill/skills && zip -r record-skill.zip record-skill
```

## Testing
`tests/record-skill/scenarios.md` lists pressure scenarios. After changing the skill, walk through each one with the new `SKILL.md` (or give it to a fresh Claude session) and check the expected behaviour still follows.

## Contributing
Issues and PRs welcome. Keep `SKILL.md` lean (long material → `references/`, code → `scripts/`), scripts stdlib-only with LF endings, and add a scenario for every behaviour you change.

## License
[MIT](LICENSE)
