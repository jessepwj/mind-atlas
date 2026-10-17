#!/usr/bin/env python3
"""Record a reply to one piece of page feedback and rebuild the page.

Usage:
    python3 reply.py <workdir> <feedback-id> ["details"] [--summary "one-line conclusion"]
                     [--status done|doing|planned|dropped|needs-you] [--node "node path"]...
                     [--ask "the question for the user"] [--orig "the user's original words"]
                     [--no-build] [--no-paths]

<feedback-id> is the id in square brackets in the feedback block the user pasted (or that
pull_feedback.py printed), for example F1016-162301-ab. The reply is appended to
<workdir>/replies.json and the page is rebuilt; when the user refreshes the page, the reply shows up
under their feedback. A reply is a one-line conclusion (bold) + a status label + collapsible details +
the related nodes; every part is optional, so a plain "reply text" still works.

    details     the full reply; folded away on the page. May be left out when --summary is given.
    --summary   one sentence the user can understand at a glance. Without it the first sentence of the
                details is used. Write a whole sentence, never a half sentence cut with an ellipsis.
    --status    where the matter stands (Chinese spellings work too):
                  done       finished, the user need not do anything      (已做)
                  doing      sent off or under way, not finished          (在做)
                  planned    decided, not started yet                     (定了待做)
                  dropped    decided not to do it                         (不做)
                  needs-you  the user must answer or act                  (要你定)
                needs-you must be paired with --node pointing at the [NEEDS-YOU] item in the "now"
                branch (the build warns when it is not).
    --node      a related node, repeatable: a path (the root may be left out, levels joined with ›) or a
                title that identifies it uniquely. Clicking it on the page jumps to the node.
    --ask       the question to put to the user when the status is needs-you; giving --ask without
                --status means needs-you.
    --orig      the user's original words. When the user opens the page in another browser, where
                their own feedback is not stored, this keeps the reply readable; always pass it.
    --no-build  only write replies.json (answer many items, then build once).
    --no-paths  passed on to build.py (for pages that will be shared or published).

The same id can be answered more than once; the page orders the replies by time and the last one's status
counts (a needs-you question is settled once a later reply has another status).

Standard library only; Python 3.9 or newer.
"""
import datetime
import json
import os
import pathlib
import subprocess
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent

# Same table as build.STATUS_ALIASES (a test checks that the two agree).
STATUSES = ["done", "doing", "planned", "dropped", "needs-you"]
STATUS_ALIASES = {
    "已做": "done", "done": "done",
    "在做": "doing", "doing": "doing", "in progress": "doing", "in-progress": "doing",
    "定了待做": "planned", "planned": "planned",
    "不做": "dropped", "dropped": "dropped",
    "要你定": "needs-you", "needs-you": "needs-you", "needs you": "needs-you",
}


def normalize_status(value):
    """Canonical status key for any accepted spelling; empty stays empty; anything else is an error."""
    value = (value or "").strip()
    if not value:
        return ""
    status = STATUS_ALIASES.get(value.lower())
    if status is None:
        raise SystemExit("error: --status must be one of %s (Chinese spellings work too); got %r"
                         % (", ".join(STATUSES), value))
    return status


def add_reply(workdir, feedback_id, text="", orig="", summary="", status="", nodes=(), ask=""):
    """Append a reply to replies.json (created when missing). Returns the number of replies stored."""
    wd = pathlib.Path(workdir).resolve()
    if not (wd / "meta.json").exists():
        raise SystemExit("error: %s has no meta.json; it does not look like a mind-atlas work directory" % wd)
    feedback_id, text, summary, ask = feedback_id.strip(), text.strip(), summary.strip(), ask.strip()
    if not feedback_id:
        raise SystemExit("error: the feedback id must not be empty")
    if not (text or summary):
        raise SystemExit("error: write the reply text, or at least --summary")
    status = normalize_status(status) or ("needs-you" if ask else "")
    nodes = [n.strip() for n in nodes if n.strip()]
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
    record = {"id": feedback_id, "ts": now.strftime("%Y-%m-%d %H:%M:%S"), "text": text, "orig": orig}
    if summary:
        record["summary"] = summary
    if status:
        record["status"] = status
    if nodes:
        record["nodes"] = nodes
    if status == "needs-you":
        record["ask"] = ask or summary
    replies.append(record)
    with open(str(path), "w", encoding="utf-8", newline="\n") as f:
        json.dump(replies, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return len(replies)


def parse_args(argv):
    """Hand-rolled so that a reply text beginning with "-" is not mistaken for an option.

    Returns (workdir, feedback_id, text, options) where options holds orig, summary, status, ask, nodes,
    no_paths and no_build.
    """
    args = list(argv)
    opts = {"orig": "", "summary": "", "status": "", "ask": "", "nodes": [], "no_paths": False, "no_build": False}
    flags = {"--no-paths": "no_paths", "--no-build": "no_build"}
    valued = {"--orig": "orig", "--summary": "summary", "--status": "status", "--ask": "ask", "--node": "nodes"}
    positional = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in flags:
            opts[flags[a]] = True
        elif a in valued:
            if i + 1 >= len(args):
                raise SystemExit("error: %s needs a value" % a)
            if a == "--node":
                opts["nodes"].append(args[i + 1])
            else:
                opts[valued[a]] = args[i + 1]
            i += 1
        else:
            positional.append(a)
        i += 1
    if len(positional) == 2:
        positional.append("")
    if len(positional) != 3:
        raise SystemExit(__doc__)
    return positional[0], positional[1], positional[2], opts


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if any(a in ("-h", "--help") for a in argv[:1]):
        print(__doc__)
        return
    workdir, feedback_id, text, o = parse_args(argv)
    add_reply(workdir, feedback_id, text, o["orig"], o["summary"], o["status"], o["nodes"], o["ask"])
    status = normalize_status(o["status"]) or ("needs-you" if o["ask"].strip() else "")
    print("Replied to %s%s" % (feedback_id.strip(), " (%s)" % status if status else ""))
    if status == "needs-you" and not o["nodes"]:
        print("WARNING: status is needs-you but there is no --node: point it at the item tagged [NEEDS-YOU] in the "
              "\"now\" branch (the build checks this too)", file=sys.stderr)
    if o["no_build"]:
        return
    cmd = [sys.executable, str(SCRIPT_DIR / "build.py"), workdir]
    if o["no_paths"]:
        cmd.append("--no-paths")
    sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
