#!/usr/bin/env python3
"""embed.py — idempotently insert/update a cliproof image block in a README.

The image markdown lives between marker comments keyed by an id:

    <!-- cliproof:start id=<id> -->
    ![alt](path)
    <!-- cliproof:end id=<id> -->

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
import os as _os_k
import sys as _sys_k
_sys_k.path.insert(0, _os_k.path.dirname(_os_k.path.abspath(__file__)))
from _kernel import EXIT_SUCCESS, EXIT_ERROR, success, error, emit, setup_streams

# README/diff text can contain any Unicode; never crash on a cp1252 console.
setup_streams()


def _block(image: str, alt: str, block_id: str) -> str:
    image_md = "![{alt}]({img})".format(alt=alt, img=image.replace("\\", "/"))
    return (
        "<!-- cliproof:start id={id} -->\n"
        "{md}\n"
        "<!-- cliproof:end id={id} -->"
    ).format(id=block_id, md=image_md)


def upsert(text: str, image: str, alt: str, block_id: str, heading: str) -> str:
    block = _block(image, alt, block_id)
    start = re.escape("<!-- cliproof:start id={} -->".format(block_id))
    end = re.escape("<!-- cliproof:end id={} -->".format(block_id))
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
    p = argparse.ArgumentParser(description="Idempotently embed a cliproof image in a README.")
    p.add_argument("readme", help="path to README.md")
    p.add_argument("--image", required=True, help="repo-relative image path")
    p.add_argument("--alt", required=True, help="alt text describing the shot")
    p.add_argument("--id", dest="block_id", required=True, help="stable id for this block")
    p.add_argument("--heading", default="Demo", help="section heading to place a new block under")
    p.add_argument("--dry-run", action="store_true", help="print the diff but do not write")
    p.add_argument("--no-backup", action="store_true", help="do not write a .bak file")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON to stdout")
    args = p.parse_args(argv)

    if os.path.exists(args.readme):
        # utf-8-sig drops a stray BOM (Notepad/VS Code can add one); we write back
        # plain utf-8 so the README stays BOM-free and frontmatter/markdown parse.
        with open(args.readme, "r", encoding="utf-8-sig") as fh:
            original = fh.read()
    else:
        original = "# {}\n".format(os.path.splitext(os.path.basename(args.readme))[0])

    updated = upsert(original, args.image, args.alt, args.block_id, args.heading)

    diff = "".join(difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=args.readme, tofile=args.readme + " (cliproof)",
    ))
    if diff:
        if not args.json:
            sys.stdout.write(diff)
    else:
        print("embed: no change (block already up to date).", file=sys.stderr)
        emit(success("embed", {"readme": args.readme, "diff": ""}), args.json)
        return EXIT_SUCCESS

    if args.dry_run:
        print("\nembed: dry-run, nothing written.", file=sys.stderr)
        emit(success("embed", {"readme": args.readme, "diff": diff[:500]}), args.json)
        return EXIT_SUCCESS

    # newline="\n": deterministic LF output on every platform (no Windows CRLF
    # translation), matching the repo norm and what freeze/GitHub expect.
    if not args.no_backup and os.path.exists(args.readme):
        with open(args.readme + ".bak", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(original)

    try:
        with open(args.readme, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(updated)
    except OSError as exc:
        print("\nembed: write failed: {}".format(exc), file=sys.stderr)
        emit(error("embed", "write_failed", EXIT_ERROR), args.json)
        return EXIT_ERROR
    print("\nembed: wrote {}".format(args.readme), file=sys.stderr)
    emit(success("embed", {"readme": args.readme, "diff": diff[:500]}), args.json)
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
