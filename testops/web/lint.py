"""The plain-English lint the case page has to pass (TESTOPS-26).

TESTOPS-23 removed the analyser's voice; this ticket removes the last place the page made a reader
work: the summary was one paragraph, so finding the action meant reading the argument. The lint here
is run as a test over every claim of a real pipeline run, and by ``scripts/lint_corpus.py`` over the
stored corpus, so the rule is checked against the claims the product actually wrote rather than a
hand-made row.

Three checks belong to the scan block:

  * plain English - no word an engineer would not write, and no sentence over 45 words
  * one argument - no clause of six or more words repeated inside the block
  * one quote style - typographic quotes in prose, with code spans keeping their own characters

One more belongs to the page as a whole: a code span's punctuation follows it directly, with no
space between, so a comma never reads as detached from the word it follows (AC10).

``reader_text`` is also the one place markup becomes the reader's words, so the tests and the corpus
script agree on what a sentence is.
"""
from __future__ import annotations

import html as htmllib
import re

# Words the ticket forbids, with the plain replacement a writer should have reached for. The
# replacements are not used by the lint; they are here so a failure can say what to write instead.
BANNED = {
    "dearer": "more expensive",
    "whilst": "while",
    "purportedly": "supposedly",
    "utilise": "use",
    "commence": "start",
    "prior to": "before",
    "in order to": "to",
    "leverage": "use",
    "facilitate": "help",
    "endeavour": "try",
}
MAX_SENTENCE_WORDS = 45
MIN_REPEATED_CLAUSE = 6

# Identifiers that must be rendered in monospace wherever a reader meets them (AC4). Step text is
# checked separately, because it is quoted verbatim from the test file.
IDENTIFIERS = ("HTTP client", "CSS class")
IDENTIFIER = re.compile(r"\bdata-[a-z0-9]+(?:-[a-z0-9]+)*\b")


def reader_text(html: str) -> str:
    """The reader's words: styles, markup and code excerpts removed; block boundaries kept.

    Code is excluded on purpose. A snippet is the source the claim is about, not a sentence the page
    wrote, and counting the asserted line there would make "quoted once" unsatisfiable.
    """
    text = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    text = re.sub(r"<head>.*?</head>", " ", text, flags=re.S)
    text = re.sub(r"<pre.*?</pre>", " ", text, flags=re.S)
    text = re.sub(r"<figure.*?</figure>", " ", text, flags=re.S)
    text = re.sub(r"</(h1|h2|h3|p|li|blockquote|section|div|main)>", "\n", text)
    text = re.sub(r"<(h1|h2|h3|p|li|blockquote|section|div|main)[^>]*>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return htmllib.unescape(text)


def sentences(text: str) -> list[str]:
    """Sentences, with a line boundary treated as one: a heading is not part of the next sentence."""
    out: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        out.extend(part.strip() for part in re.split(r"(?<=[.!?])\s+", line) if part.strip())
    return out


def opening_block(html: str) -> str:
    """The scan block's reader text, or ``""`` when the page has none."""
    match = re.search(r'<section class="scan">(.*?)</section>', html, re.S)
    return reader_text(match.group(1)) if match else ""


def plain_english(text: str) -> list[str]:
    """Every forbidden word and every over-long sentence in one piece of reader text (AC6)."""
    problems: list[str] = []
    lower = text.lower()
    for word, instead in BANNED.items():
        if re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", lower):
            problems.append(f"{word!r} is not plain English; write {instead!r}")
    for sentence in sentences(text):
        words = len(sentence.split())
        if words > MAX_SENTENCE_WORDS:
            problems.append(f"a {words}-word sentence: {sentence!r}")
    return problems


def repeated_clause(text: str, size: int = MIN_REPEATED_CLAUSE) -> str | None:
    """The first clause of ``size`` words that appears twice, or ``None`` (AC3)."""
    tokens = re.findall(r"[a-z0-9]+(?:[-'][a-z0-9]+)*", text.lower())
    seen: set[tuple[str, ...]] = set()
    for start in range(len(tokens) - size + 1):
        clause = tuple(tokens[start:start + size])
        if clause in seen:
            return " ".join(clause)
        seen.add(clause)
    return None


def straight_quotes(html: str) -> list[str]:
    """Prose that still uses a straight quote, outside code spans (AC5)."""
    outside = re.sub(r"<pre.*?</pre>", " ", html, flags=re.S)
    outside = re.sub(r"<code.*?</code>", " ", outside, flags=re.S)
    outside = re.sub(r"<style>.*?</style>", " ", outside, flags=re.S)
    outside = re.sub(r"<[^>]+>", " ", outside)
    text = htmllib.unescape(outside)
    return sorted({quote for quote in ('"', "'") if quote in text})


# A code span ends where its identifier ends, so punctuation written against it must follow it
# directly. A space here renders as "…both loads , but…", with the comma reading as detached from
# the word it qualifies (AC10).
DETACHED_PUNCTUATION = re.compile(r"</code>[ \t\r\n]+([,.;:!?])")


def detached_punctuation(html: str) -> list[str]:
    """Code spans with a space, and then a mark, between them and their punctuation (AC10)."""
    return [f"a space between a code span and {match.group(1)!r}"
            for match in DETACHED_PUNCTUATION.finditer(html)]


def bare_identifiers(html: str, step: str | None = None) -> list[str]:
    """Identifiers a reader meets as prose instead of monospace (AC4)."""
    outside = re.sub(r"<pre.*?</pre>", " ", html, flags=re.S)
    outside = re.sub(r"<code.*?</code>", " ", outside, flags=re.S)
    outside = re.sub(r"<style>.*?</style>", " ", outside, flags=re.S)
    outside = re.sub(r"<[^>]+>", " ", outside)
    text = htmllib.unescape(outside)
    found = [name for name in IDENTIFIERS if name in text]
    found.extend(match.group(0) for match in IDENTIFIER.finditer(text))
    if step and step in text:
        found.append(step)
    return sorted(set(found))


def lint(html: str, step: str | None = None) -> list[str]:
    """Everything this ticket makes the rendered page answer for."""
    text = reader_text(html)
    problems = plain_english(text)
    clause = repeated_clause(opening_block(html))
    if clause:
        problems.append(f"the scan block repeats a {MIN_REPEATED_CLAUSE}-word clause: {clause!r}")
    for quote in straight_quotes(html):
        problems.append(f"a straight {quote!r} survives in prose; the page uses one quote style")
    for name in bare_identifiers(html, step):
        problems.append(f"identifier {name!r} is prose, not monospace")
    problems.extend(detached_punctuation(html))
    return problems
