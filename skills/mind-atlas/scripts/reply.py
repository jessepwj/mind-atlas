#!/usr/bin/env python3
"""Record a reply to one piece of page feedback and rebuild the page.

Usage:
    python3 reply.py <workdir> <feedback-id> "reply text" [--orig "the user's original words"] [--no-paths]

<feedback-id> is the id in square brackets in the feedback block the user pasted,
for example F1016-162301-ab. The reply is appended to <workdir>/replies.json and the page is
rebuilt; when the user refreshes the page, the reply shows up under their feedback.
Pass --orig so that the reply still reads well if the user opens the page in a different
browser (where their own feedback is not stored). The same id can be answered more than once.

Standard library only; Python 3.9 or newer.
"""
import datetime
import json
import os
import pathlib
import subprocess
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent


def add_reply(workdir, feedback_id, text, orig=""):
    """Append a reply to replies.json (created when missing). Returns the number of replies stored."""
    wd = pathlib.Path(workdir).resolve()
    if not (wd / "meta.json").exists():
        raise SystemExit("error: %s has no meta.json; it does not look like a mind-atlas work directory" % wd)
    feedback_id, text = feedback_id.strip(), text.strip()
    if not feedback_id or not text:
        raise SystemExit("error: the feedback id and the reply text must not be empty")
    path = wd / "replies.json"
    replies = []
    if path.exists():
        try:
            replies = json.loads(path.read_text(encoding="utf-8-sig"))
        except ValueError as e:
            raise SystemExit("error: %s is not valid JSON: %s" % (path, e))
        if not isinstance(replies, list):
            raise SystemExit("error: %s must contain a JSON list" % path)
    stamp = os.environ.get("SOURCE_DATE_EPOCH", "")
    now = (datetime.datetime.fromtimestamp(int(stamp), datetime.timezone.utc) if stamp.isdigit()
           else datetime.datetime.now())
    replies.append({"id": feedback_id, "ts": now.strftime("%Y-%m-%d %H:%M:%S"), "text": text, "orig": orig})
    with open(str(path), "w", encoding="utf-8", newline="\n") as f:
        json.dump(replies, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return len(replies)


def parse_args(argv):
    """Hand-rolled so that a reply text beginning with "-" is not mistaken for an option."""
    args = list(argv)
    orig, no_paths = "", False
    if "--no-paths" in args:
        args.remove("--no-paths")
        no_paths = True
    if "--orig" in args:
        i = args.index("--orig")
        if i + 1 >= len(args):
            raise SystemExit("error: --orig needs a value")
        orig = args[i + 1]
        del args[i:i + 2]
    if len(args) != 3:
        raise SystemExit(__doc__)
    return args[0], args[1], args[2], orig, no_paths


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if any(a in ("-h", "--help") for a in argv[:1]):
        print(__doc__)
        return
    workdir, feedback_id, text, orig, no_paths = parse_args(argv)
    add_reply(workdir, feedback_id, text, orig)
    print("Replied to %s" % feedback_id.strip())
    cmd = [sys.executable, str(SCRIPT_DIR / "build.py"), workdir]
    if no_paths:
        cmd.append("--no-paths")
    sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
