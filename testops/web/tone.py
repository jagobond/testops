"""The tone every verdict wears, declared once (TESTOPS-52).

The blind contract author found ``Cannot assess`` rendered as ``<strong class="verdict hot">`` -
the same alarm red as ``Checked, but this repeats another test`` - so the only thing telling a
reader "the tool could not conclude" apart from "the tool found a problem" was the sentence. That
is reading a legend, which is exactly what the styling is for.

A verdict's tone is a design decision, so it is declared here as a table and nowhere else:

* **alarm** - the verdict asserts a problem;
* **soft** - the tool could not conclude (dashed and muted, never alarm red);
* **settled** - the verdict asserts nothing is wrong, and must not borrow the alarm.

The table covers every name the store has ever accepted, current and retired, because a page may
still render a claim written before the vocabulary settled (TESTOPS-9). ``tests/test_verdict_tone``
iterates the store's own vocabulary and fails if a name has no declared tone, so a verdict cannot
appear on a page untinted.

``tone_of`` has no fallback on purpose. A default would catch every name nobody thought about and
dress it as settled - the defect this ticket exists to remove. An undeclared name raises, and the
test above makes sure that cannot happen for a name the store accepts.
"""
from __future__ import annotations

ALARM = "alarm"
SOFT = "soft"
SETTLED = "settled"

TONES = frozenset({ALARM, SOFT, SETTLED})

VERDICT_TONE = {
    # Current vocabulary (schema.sql / the analysers).
    "distinct": SETTLED,     # checked, nothing wrong
    "review": ALARM,         # checked, but over-tested for what it asserts
    "gap": ALARM,            # not proved: nothing runs what the assertion needs
    "duplicate": ALARM,      # checked, but this repeats another test
    "repeats_product": ALARM,  # checked, but the product already publishes it (TESTOPS-72)
    "unplaced": SOFT,        # cannot tell: no comparison could be made
    # Retired vocabulary (TESTOPS-9), still carried by stored evidence.
    "necessary": SETTLED,
    "optimal": SETTLED,
    "overbuilt": ALARM,
}

# A claim the sources could not be consulted for says "Cannot assess" in the headline; the tool
# reached no conclusion, so it wears the soft treatment whatever the stored verdict says.
NOT_ASSESSABLE_TONE = SOFT

# The class suffix each tone renders as, on the judgement headline and on a badge. Explicit, and
# the settled suffix is empty because "settled" is the absence of a warning - not a default.
_CLASS_SUFFIX = {SETTLED: "", SOFT: " soft", ALARM: " hot"}


def tone_of(verdict: str) -> str:
    """The declared tone for ``verdict``. An undeclared name is an error, never a guess."""
    try:
        return VERDICT_TONE[verdict]
    except KeyError:
        raise KeyError(
            f"verdict {verdict!r} has no declared tone; add it to testops/web/tone.py "
            f"(declared: {', '.join(sorted(VERDICT_TONE))})") from None


def class_suffix(tone: str) -> str:
    """The extra class tokens for ``tone``, including the leading space (``''`` when settled)."""
    try:
        return _CLASS_SUFFIX[tone]
    except KeyError:
        raise KeyError(f"tone {tone!r} is not one of {', '.join(sorted(TONES))}") from None
