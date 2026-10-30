#!/usr/bin/env python3
"""transcript_digest.py — compress a Claude Code session transcript into a short, skill-ready digest.

  transcript_digest.py list [--all] [--limit N]
      Sessions for the current project (newest first): id, start, end, prompts, first prompt.
      --all lists sessions of every project.
  transcript_digest.py digest <latest|SESSION_ID|path.jsonl> [--since ISO] [--until ISO]
                              [--from-marker TEXT] [--to-marker TEXT] [--sidechains]
                              [--max-chars N] [--no-text]
      Prints a markdown digest: user prompts, tool calls (one line each), failures,
      short assistant notes, and a summary of files touched and commands run.
      Secrets (API keys, tokens, passwords) are redacted.

Transcripts live in ~/.claude/projects/<project-dir-with-dashes>/<session>.jsonl
(override with CLAUDE_TRANSCRIPTS_DIR). Python 3 standard library only.
"""
import glob
import json
import os
import re
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone

BASE = os.environ.get("CLAUDE_TRANSCRIPTS_DIR") or os.path.join(os.path.expanduser("~"), ".claude", "projects")
CD_PREFIX = re.compile(r"^(cd\s+\S+\s*(&&|;)\s*)+")
REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
TAGS = re.compile(r"</?(command-name|command-message|command-args|local-command-stdout)[^>]*>")
SECRETS = [
    (re.compile(r"\b(sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{16,})"), "<redacted-key>"),
    (re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"), "<redacted-token>"),
    (re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b"), "<redacted-aws-key>"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "<redacted-slack-token>"),
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{16,}"), r"\1 <redacted>"),
    (re.compile(r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|token|client[_-]?secret)(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|\S+)"),
     r"\1\2<redacted>"),
    (re.compile(r"(?i)(://[^/\s:@]+:)[^@\s/]+@"), r"\1<redacted>@"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "<redacted-private-key>"),
]


def redact(s):
    for rx, rep in SECRETS:
        s = rx.sub(rep, s)
    return s


def project_dir_for(path):
    return os.path.join(BASE, re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(path)))


def parse_ts(s):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def read_jsonl(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if isinstance(o, dict):
                yield o


def user_text(msg):
    """Text a human typed in a user message (not tool results), with system reminders removed."""
    c = msg.get("content") if isinstance(msg, dict) else None
    parts = []
    if isinstance(c, str):
        parts.append(c)
    elif isinstance(c, list):
        for b in c:
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(b.get("text", ""))
    t = TAGS.sub("", REMINDER.sub("", "\n".join(parts))).strip()
    return t


def session_files(all_projects=False):
    if all_projects:
        files = glob.glob(os.path.join(BASE, "*", "*.jsonl"))
    else:
        d = project_dir_for(os.getcwd())
        files = glob.glob(os.path.join(d, "*.jsonl"))
        if not files:      # unusual dir naming: fall back to matching the cwd field
            cwd = os.path.abspath(os.getcwd())
            for f in glob.glob(os.path.join(BASE, "*", "*.jsonl")):
                for o in read_jsonl(f):
                    if "cwd" in o:
                        if os.path.abspath(o["cwd"]) == cwd:
                            files.append(f)
                        break
    return sorted(files, key=os.path.getmtime, reverse=True)


# ------------------------------------------------------------------ list
def cmd_list(argv):
    all_p = "--all" in argv
    limit = 20
    if "--limit" in argv:
        limit = int(argv[argv.index("--limit") + 1])
    files = session_files(all_p)[:limit]
    if not files:
        print(f"no sessions found under {BASE} for {'any project' if all_p else os.getcwd()}")
        return 1
    for f in files:
        first, start, end, prompts = "", None, None, 0
        for o in read_jsonl(f):
            ts = parse_ts(o.get("timestamp"))
            if ts:
                start = start or ts
                end = ts
            if o.get("type") == "user" and not o.get("isMeta") and not o.get("isSidechain"):
                t = user_text(o.get("message"))
                if t:
                    prompts += 1
                    first = first or t.splitlines()[0][:80]
        sid = os.path.splitext(os.path.basename(f))[0]
        fmt = lambda d: d.strftime("%Y-%m-%d %H:%M") if d else "?"
        proj = f"  [{os.path.basename(os.path.dirname(f))}]" if all_p else ""
        print(f"{sid}  {fmt(start)} → {fmt(end)}  prompts={prompts}  \"{redact(first)}\"{proj}")
    return 0


# ------------------------------------------------------------------ digest
def describe_call(name, inp):
    if not isinstance(inp, dict):
        return name
    g = inp.get
    if name == "Bash":
        cmd = str(g("command", "")).strip()
        first = cmd.splitlines()[0] if cmd else ""
        more = f"  (+{cmd.count(chr(10))} lines)" if "\n" in cmd else ""
        bg = " [background]" if g("run_in_background") else ""
        return f"Bash{bg}: {first[:180]}{more}"
    if name in ("Read",):
        rng = f":{g('offset')}+{g('limit')}" if g("offset") or g("limit") else ""
        return f"Read {g('file_path')}{rng}"
    if name == "Write":
        n = str(g("content", "")).count("\n") + 1
        return f"Write {g('file_path')} ({n} lines)"
    if name in ("Edit", "MultiEdit"):
        return f"Edit {g('file_path')}"
    if name == "NotebookEdit":
        return f"NotebookEdit {g('notebook_path')}"
    if name == "Grep":
        return f"Grep '{g('pattern')}' in {g('path') or '.'}" + (f" ({g('glob')})" if g("glob") else "")
    if name == "Glob":
        return f"Glob {g('pattern')}" + (f" in {g('path')}" if g("path") else "")
    if name in ("WebFetch",):
        return f"WebFetch {g('url')}"
    if name == "WebSearch":
        return f"WebSearch '{g('query')}'"
    if name in ("Agent", "Task"):
        return f"Agent[{g('subagent_type') or 'general'}]: {g('description') or str(g('prompt', ''))[:80]}"
    if name == "Skill":
        return f"Skill {g('skill')}" + (f" {g('args')}" if g("args") else "")
    if name in ("TodoWrite", "TaskCreate", "TaskUpdate"):
        return None   # bookkeeping, not part of the procedure
    keys = ", ".join(f"{k}={str(v)[:40]}" for k, v in list(inp.items())[:3])
    return f"{name}({keys})"


def result_error(block, tool_use_result):
    if block.get("is_error"):
        c = block.get("content")
        if isinstance(c, list):
            c = " ".join(b.get("text", "") for b in c if isinstance(b, dict))
        return str(c or "error").strip()
    if isinstance(tool_use_result, dict) and tool_use_result.get("interrupted"):
        return "interrupted"
    return None


def cmd_digest(argv):
    opts = {"since": None, "until": None, "from-marker": None, "to-marker": None, "max-chars": "12000"}
    flags = {"--sidechains": False, "--no-text": False}
    pos, i = [], 0
    while i < len(argv):
        a = argv[i]
        if a in flags:
            flags[a] = True
        elif a.startswith("--") and a[2:] in opts:
            opts[a[2:]] = argv[i + 1]
            i += 1
        else:
            pos.append(a)
        i += 1
    if len(pos) != 1:
        print("usage: transcript_digest.py digest <latest|SESSION_ID|path.jsonl> [options]", file=sys.stderr)
        return 2
    target = pos[0]
    if target == "latest":
        files = session_files()
        if not files:
            print("no sessions for this project", file=sys.stderr)
            return 1
        path = files[0]
    elif os.path.isfile(target):
        path = target
    else:
        hits = glob.glob(os.path.join(BASE, "*", f"{target}*.jsonl"))
        if len(hits) != 1:
            print(f"{'no' if not hits else 'ambiguous'} session match for {target}", file=sys.stderr)
            return 1
        path = hits[0]

    since, until = parse_ts(opts["since"]), parse_ts(opts["until"])
    recs = list(read_jsonl(path))
    root = next((o["cwd"] for o in recs if isinstance(o.get("cwd"), str)), "")

    def short(p):
        p = str(p)
        if root and p.startswith(root.rstrip("/") + "/"):
            return p[len(root.rstrip("/")) + 1:]
        return p

    # marker window: from the LAST user prompt containing from-marker
    start_i, end_i = 0, len(recs)
    if opts["from-marker"]:
        idx = [k for k, o in enumerate(recs) if o.get("type") == "user"
               and opts["from-marker"].lower() in user_text(o.get("message")).lower()]
        if not idx:
            print(f"marker not found: {opts['from-marker']}", file=sys.stderr)
            return 1
        start_i = idx[-1]
    if opts["to-marker"]:
        for k in range(start_i + 1, len(recs)):
            o = recs[k]
            if o.get("type") == "user" and opts["to-marker"].lower() in user_text(o.get("message")).lower():
                end_i = k + 1
                break

    lines, pending = [], {}
    files_written, files_edited, files_read = OrderedDict(), OrderedDict(), Counter()
    commands, failures, prompts = Counter(), 0, 0
    last_kind, run_tool, run_count = None, None, 0

    def flush_run():
        nonlocal run_tool, run_count
        if run_tool and run_count > 1:
            lines.append(f"   (… {run_count - 1} more {run_tool} calls)")
        run_tool, run_count = None, 0

    for o in recs[start_i:end_i]:
        ts = parse_ts(o.get("timestamp"))
        if since and ts and ts < since:
            continue
        if until and ts and ts > until:
            continue
        if o.get("isSidechain") and not flags["--sidechains"]:
            continue
        if o.get("isMeta"):
            continue
        t, msg = o.get("type"), o.get("message")
        content = msg.get("content") if isinstance(msg, dict) else None

        if t == "user":
            t_txt = user_text(msg)
            if t_txt:
                flush_run()
                prompts += 1
                tag = "U" if last_kind in (None, "user") else "U (after actions)"
                body = redact(t_txt)
                if len(body) > 600:
                    body = body[:600] + " …"
                lines.append(f"\n**{tag}:** {body}")
                last_kind = "user"
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        err = result_error(b, o.get("toolUseResult"))
                        if err:
                            flush_run()
                            failures += 1
                            call = pending.get(b.get("tool_use_id"), "?")
                            el = [x.strip() for x in err.splitlines() if x.strip()]
                            first = redact(" | ".join(el[:2]) if el else err)[:200]
                            lines.append(f"   ✗ failed ({call[:60]}): {first}")
        elif t == "assistant" and isinstance(content, list):
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and not flags["--no-text"]:
                    txt = b.get("text", "").strip()
                    if txt:
                        flush_run()
                        first = txt.splitlines()[0]
                        lines.append(f"   _A: {redact(first[:200])}{' …' if len(txt) > len(first) else ''}_")
                elif b.get("type") == "tool_use":
                    name, inp = b.get("name", "?"), b.get("input") or {}
                    d = describe_call(name, inp)
                    if d is None:
                        continue
                    d = redact(d)
                    pending[b.get("id")] = d
                    if isinstance(inp, dict):
                        fp = inp.get("file_path") or inp.get("notebook_path")
                        if name == "Write" and fp:
                            files_written[fp] = 1
                        elif name in ("Edit", "MultiEdit", "NotebookEdit") and fp:
                            files_edited[fp] = 1
                        elif name == "Read" and fp:
                            files_read[fp] += 1
                        if name == "Bash":
                            c = str(inp.get("command", "")).strip().splitlines()
                            if c:
                                c0 = CD_PREFIX.sub("", c[0])
                                commands[redact(c0)[:90]] += 1
                    if name in ("Read", "Grep", "Glob") and run_tool == name:
                        run_count += 1
                        continue
                    flush_run()
                    if name in ("Read", "Grep", "Glob"):
                        run_tool, run_count = name, 1
                    lines.append(f"   → {d}")
                    last_kind = "tool"
    flush_run()

    head = [f"# Session digest — {os.path.splitext(os.path.basename(path))[0]}" + (f" (cwd {root})" if root else ""),
            f"prompts={prompts} failures={failures} files_written={len(files_written)} "
            f"files_edited={len(files_edited)} distinct_commands={len(commands)}"]
    if files_written:
        head.append("**Created:** " + ", ".join(short(f) for f in files_written))
    if files_edited:
        head.append("**Edited:** " + ", ".join(short(f) for f in files_edited))
    if commands:
        head.append("**Commands (count):** " + " · ".join(f"`{c}`×{n}" if n > 1 else f"`{c}`"
                                                         for c, n in commands.most_common(15)))
    if files_read:
        head.append("**Most read:** " + ", ".join(f"{short(f)}×{n}" for f, n in files_read.most_common(8)))
    head.append("\n## Timeline")
    out = "\n".join(head + lines)
    limit = int(opts["max-chars"])
    if len(out) > limit:
        keep = limit // 2
        out = out[:keep] + f"\n\n… [{len(out) - limit} chars cut from the middle; narrow with --since/--from-marker] …\n\n" + out[-keep:]
    print(out)
    return 0


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 2
    if argv[0] == "list":
        return cmd_list(argv[1:])
    if argv[0] == "digest":
        return cmd_digest(argv[1:])
    print(f"unknown command {argv[0]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
