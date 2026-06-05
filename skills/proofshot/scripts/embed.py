#!/usr/bin/env python3
"""embed.py — idempotently insert/update a proofshot image block in a README.

The image markdown lives between marker comments keyed by an id:

    <!-- proofshot:start id=<id> -->
    ![alt](path)
    <!-- proofshot:end id=<id> -->

Re-running with the same --id replaces that block in place (no duplicates).
A new --id adds a new block. The rest of the file is never touched.

Usage:
    python embed.py README.md --image .github/media/cli-help.png \\
        --alt "clausa --help running" --id cli-help --heading Demo

    python embed.py README.md --image ... --id ... --dry-run   # print diff only

Behaviour:
    - existing block with id   -> replace its inner markdown
    - else heading "## <h>"    -> insert block right after that heading
    - else                     -> append "## <h>" + block at end of file
    - writes a .bak on first real write; always prints a unified diff

Pure standard library. No network.
"""
import argparse
import difflib
import os
import re
import sys

# README/diff text can contain any Unicode; never crash on a cp1252 console.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _block(image: str, alt: str, block_id: str) -> str:
    image_md = "![{alt}]({img})".format(alt=alt, img=image.replace("\\", "/"))
    return (
        "<!-- proofshot:start id={id} -->\n"
        "{md}\n"
        "<!-- proofshot:end id={id} -->"
    ).format(id=block_id, md=image_md)


def upsert(text: str, image: str, alt: str, block_id: str, heading: str) -> str:
    block = _block(image, alt, block_id)
    start = re.escape("<!-- proofshot:start id={} -->".format(block_id))
    end = re.escape("<!-- proofshot:end id={} -->".format(block_id))
    pattern = re.compile(start + r"[\s\S]*?" + end)

    if pattern.search(text):
        return pattern.sub(lambda _m: block, text, count=1)

    if heading:
        h = re.compile(r"^#{1,6}\s+" + re.escape(heading) + r"\s*$", re.MULTILINE)
        m = h.search(text)
        if m:
            insert_at = m.end()
            return text[:insert_at] + "\n\n" + block + "\n" + text[insert_at:]

    sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    tail = ""
    if heading:
        tail = "## {}\n\n".format(heading)
    return text + sep + tail + block + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Idempotently embed a proofshot image in a README.")
    p.add_argument("readme", help="path to README.md")
    p.add_argument("--image", required=True, help="repo-relative image path")
    p.add_argument("--alt", required=True, help="alt text describing the shot")
    p.add_argument("--id", dest="block_id", required=True, help="stable id for this block")
    p.add_argument("--heading", default="Demo", help="section heading to place a new block under")
    p.add_argument("--dry-run", action="store_true", help="print the diff but do not write")
    p.add_argument("--no-backup", action="store_true", help="do not write a .bak file")
    args = p.parse_args(argv)

    if os.path.exists(args.readme):
        with open(args.readme, "r", encoding="utf-8") as fh:
            original = fh.read()
    else:
        original = "# {}\n".format(os.path.splitext(os.path.basename(args.readme))[0])

    updated = upsert(original, args.image, args.alt, args.block_id, args.heading)

    diff = "".join(difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=args.readme, tofile=args.readme + " (proofshot)",
    ))
    if diff:
        sys.stdout.write(diff)
    else:
        print("embed: no change (block already up to date).", file=sys.stderr)
        return 0

    if args.dry_run:
        print("\nembed: dry-run, nothing written.", file=sys.stderr)
        return 0

    if not args.no_backup and os.path.exists(args.readme):
        with open(args.readme + ".bak", "w", encoding="utf-8") as fh:
            fh.write(original)

    with open(args.readme, "w", encoding="utf-8") as fh:
        fh.write(updated)
    print("\nembed: wrote {}".format(args.readme), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
