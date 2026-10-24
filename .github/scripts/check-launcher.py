"""Checks the public launcher before GitHub Pages serves it to every Outlook user.

This repository is the add-in's public front door: it must hold the launcher only, with no data,
no token and nothing that moves its address. Run: python3 .github/scripts/check-launcher.py
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
ALLOWED_SUFFIXES = {".html", ".png", ".ico", ".svg", ".md"}
# Scripts may come from the repository itself or from Microsoft's Office.js host, nowhere else.
SCRIPT_HOSTS = {"appsforoffice.microsoft.com"}
SECRETS = [
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "a GitHub fine-grained token"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), "a GitHub token"),
    (re.compile(r"glpat-[A-Za-z0-9_-]{20,}"), "a GitLab token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "a private key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "an AWS access key"),
    (re.compile(r"\bsig=[A-Za-z0-9%]{30,}"), "a signed URL (SAS / flow trigger signature)"),
]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts, self.refs = [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("src"):
            self.scripts.append(attrs["src"])
        for key in ("src", "href"):
            if attrs.get(key):
                self.refs.append(attrs[key])


def files():
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT)
        if path.is_file() and not rel.parts[0].startswith("."):
            yield path, rel.as_posix()


def main() -> int:
    problems = []
    if (ROOT / "CNAME").exists():
        problems.append("CNAME: a custom Pages domain changes the add-in's address, which the released "
                        "manifest fixes for good. Remove it.")
    for path, rel in files():
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            problems.append(f"{rel}: only the launcher's pages and icons belong here ({', '.join(sorted(ALLOWED_SUFFIXES))})")
            continue
        if path.suffix.lower() not in (".html", ".md", ".svg"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern, what in SECRETS:
            if pattern.search(text):
                problems.append(f"{rel}: contains what looks like {what}. This repository is public.")
        if path.suffix.lower() != ".html":
            continue
        parser = Links()
        parser.feed(text)
        for src in parser.scripts:
            url = urlparse(src)
            if url.scheme in ("http", "https") and url.hostname not in SCRIPT_HOSTS:
                problems.append(f"{rel}: loads a script from {url.hostname}; only {', '.join(sorted(SCRIPT_HOSTS))} "
                                "or files in this repository are allowed")
            elif url.scheme == "http":
                problems.append(f"{rel}: loads a script over plain http")
        for ref in parser.refs:
            url = urlparse(ref)
            if url.scheme or ref.startswith(("#", "//", "data:", "mailto:")) or not url.path:
                continue
            target = (ROOT / url.path.lstrip("/")) if url.path.startswith("/") else (path.parent / url.path)
            if not target.exists():
                problems.append(f"{rel}: links to {ref}, which isn't in the repository")
    for problem in problems:
        print(f"::error::{problem}" if "GITHUB_ACTIONS" in __import__("os").environ else f"ERROR: {problem}")
    print(f"Checked {sum(1 for _ in files())} files: {'OK' if not problems else f'{len(problems)} problem(s)'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
