#!/usr/bin/env python3
"""Build the Technician License Class course page.

Reads the regenerated lesson/quiz drafts from the VIH goal workspace and
generates a single self-contained index.html for visually-inconvenienced-hams/technician-class
on GitHub Pages, plus copies the diagram PNGs into diagrams/.

Lesson prose and quiz questions/options are used EXACTLY as written in the
source files; nothing is rewritten. Only the page chrome (title, contents,
headings, quiz wiring, read-aloud, diagrams placement) is new.

Run: python3 build_page.py
Output: index.html + diagrams/*.png in ~/workspace/github-pages-staging/technician-class/
"""
import html
import os
import re
import shutil
import sys

SRC = os.path.expanduser(
    "~/workspace/goals/visually-inconvenienced-hams-automated-group-posts/files/technician-class"
)
OUT_DIR = os.path.expanduser("~/workspace/github-pages-staging/technician-class")
GROUP_URL = "https://www.facebook.com/groups/742838019382868"


def lesson_numbers():
    """Lesson numbers present in the source dir, in order.

    Every count in the build derives from this: nothing hardcodes how
    many lessons the course has. The files must be 1..N contiguous.
    """
    nums = []
    for name in os.listdir(SRC):
        m = re.fullmatch(r"lesson-(\d+)\.md", name)
        if m:
            nums.append(int(m.group(1)))
    nums.sort()
    assert nums == list(range(1, len(nums) + 1)), (
        "lesson files are not 1..N contiguous: %r" % nums
    )
    return nums


LESSON_NUMS = lesson_numbers()

SECTIONS = [
    "What you will learn",
    "The idea in plain words",
    "An example",
    "What to remember",
    "Words to know",
]

TITLE_RE = re.compile(r"^Lesson (\d+) — Module 1: (.*)$")
QUIZ_TITLE_RE = re.compile(r"^Lesson (\d+) — Module 2: Check yourself$")
QUESTION_RE = re.compile(r"^Question (\d+) \(pool question ([A-Z0-9]+)\)$")
OPTION_RE = re.compile(r"^([A-D])\. (.*)$")
KEY_RE = re.compile(r"^Question (\d+): ([A-D])\. (.*)$")
ALT_RE = re.compile(r"Alt text(?:\s+(?:for\s+|—\s*)?([A-Za-z0-9_./-]+\.png))?\s*:\s*")


def esc(text):
    return html.escape(text, quote=True)


RATIO_RE = re.compile(r"\b(\d+(?:\.\d+)?):1\b")
_RATIO_ONES = [
    "zero", "one", "two", "three", "four",
    "five", "six", "seven", "eight", "nine",
]
_RATIO_TEENS = [
    "ten", "eleven", "twelve", "thirteen", "fourteen",
    "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
]
_RATIO_TENS = [
    "", "", "twenty", "thirty", "forty",
    "fifty", "sixty", "seventy", "eighty", "ninety",
]


def ratio_words(num):
    """'1.2' -> 'one point two to one'; the spoken form of an SWR ratio."""
    whole, dot, frac = num.partition(".")
    n = int(whole)
    if n < 10:
        words = _RATIO_ONES[n]
    elif n < 20:
        words = _RATIO_TEENS[n - 10]
    else:
        words = _RATIO_TENS[n // 10]
        if n % 10:
            words += " " + _RATIO_ONES[n % 10]
    if dot:
        words += " point" + "".join(" " + _RATIO_ONES[int(d)] for d in frac)
    return words + " to one"


def mark_ratios(escaped_html):
    """Wrap SWR ratios in escaped HTML so screen readers announce them.

    "1.2:1" becomes an aria-hidden visible "1.2:1" plus a visually hidden
    "one point two to one". Only ratios (number, colon, 1) are wrapped;
    clock times such as 19:00 never match. Call on escaped text only,
    before any tags are added around it.
    """
    return RATIO_RE.sub(
        lambda m: '<span aria-hidden="true">%s</span>'
        '<span class="sr-only">%s</span>' % (m.group(0), ratio_words(m.group(1))),
        escaped_html,
    )


# Formulas: a single capital letter (optionally followed by 2, as in E2),
# "=", a letter, one operator, a letter — e.g. "I = E x R", "R = E - I".
# Every formula in the course (lesson-10, lesson-11, quiz-10, quiz-11)
# matches this shape, and nothing else does: the operator is always one
# of x, /, +, - (hyphen-minus) or − (Unicode minus).
FORMULA_RE = re.compile(r"\b([A-Z][0-9]?) = ([A-Z][0-9]?) ([x/+\-−]) ([A-Z][0-9]?)\b")
FRACTION_RE = re.compile(r"\b(\d+)/(\d+)\b")

_FORMULA_OP_WORDS = {
    "x": "times",
    "/": "divided by",
    "+": "plus",
    "-": "minus",
    "−": "minus",
}

_FRACTION_DENOMS = {
    2: ("half", "halves"),
    3: ("third", "thirds"),
    4: ("quarter", "quarters"),
    5: ("fifth", "fifths"),
    6: ("sixth", "sixths"),
    7: ("seventh", "sevenths"),
    8: ("eighth", "eighths"),
    9: ("ninth", "ninths"),
    10: ("tenth", "tenths"),
    11: ("eleventh", "elevenths"),
    12: ("twelfth", "twelfths"),
}


def _formula_letter(tok):
    """'E2' -> 'E squared'; a plain letter reads as itself."""
    if len(tok) == 2:
        return tok[0] + " squared"
    return tok


def formula_words(m):
    """'I = E2 / R' -> 'I equals E squared divided by R'."""
    return "%s equals %s %s %s" % (
        _formula_letter(m.group(1)),
        _formula_letter(m.group(2)),
        _FORMULA_OP_WORDS[m.group(3)],
        _formula_letter(m.group(4)),
    )


def fraction_words(m):
    """'5/8' -> 'five eighths'; '1/2' -> 'one half'; '1/10' -> 'one tenth'.

    Returns None for a fraction outside the covered range (numerator
    1-19, denominator 2-12); the caller leaves those unwrapped.
    """
    n = int(m.group(1))
    d = int(m.group(2))
    if d not in _FRACTION_DENOMS or n < 1 or n > 19:
        return None
    if n < 10:
        num_word = _RATIO_ONES[n]
    else:
        num_word = _RATIO_TEENS[n - 10]
    denom_word = _FRACTION_DENOMS[d][0] if n == 1 else _FRACTION_DENOMS[d][1]
    return num_word + " " + denom_word


def mark_formulas(escaped_html):
    """Wrap formulas the same way mark_ratios wraps SWR ratios.

    "I = E2 / R" becomes an aria-hidden visible "I = E2 / R" plus a
    visually hidden "I equals E squared divided by R". Screen readers
    at default punctuation skip "=", "x", "/", "+" and "-" (or speak
    them as bare letters), so without this the four options of
    quiz-10 Q1/Q3/Q4 and quiz-11 Q5 collapse toward each other and a
    member answering by ear cannot tell them apart. Pool text is
    untouched: only the hidden spoken form is added.
    """
    return FORMULA_RE.sub(
        lambda m: '<span aria-hidden="true">%s</span>'
        '<span class="sr-only">%s</span>' % (m.group(0), formula_words(m)),
        escaped_html,
    )


def mark_fractions(escaped_html):
    """Wrap fractions the same way mark_ratios wraps SWR ratios.

    "5/8" becomes an aria-hidden visible "5/8" plus a visually hidden
    "five eighths". Without this the slash is skipped and the fraction
    is heard as two separate numbers ("five eight").
    """

    def _sub(m):
        spoken = fraction_words(m)
        if spoken is None:
            return m.group(0)
        return '<span aria-hidden="true">%s</span><span class="sr-only">%s</span>' % (
            m.group(0),
            spoken,
        )

    return FRACTION_RE.sub(_sub, escaped_html)


def mark_spoken(escaped_html):
    """Apply every sr-only spoken-form wrapping: SWR ratios, formulas,
    fractions. Call on escaped text only, before any tags are added
    around it. One wrapper so every render site gets all three; the
    patterns never overlap, so the order does not matter.
    """
    return mark_fractions(mark_formulas(mark_ratios(escaped_html)))


def parse_draft_note(draft_text, lesson_num):
    """Return (diagram files in order, {(lesson, file): alt text}).

    The declaration line names the files ("Diagram: diagrams/x.png." or
    "Diagrams: diagrams/a.png, diagrams/b.png."). Alt texts follow in
    several spellings: "Alt text for <file>:", "Alt text — <file>:",
    "Alt text:" (positional), sometimes on the same line as the declaration.
    Alt text is keyed per (lesson, file): the same PNG has different alt
    text in different lessons (station-grounding in L9 vs L22,
    wavelength-frequency in L7 vs L12).
    """
    diagrams = []
    for line in draft_text.split("\n"):
        if line.startswith("Word count:"):
            for fname in re.findall(r"diagrams/([a-z0-9-]+\.png)", line):
                if fname not in diagrams:
                    diagrams.append(fname)
    # Find every "Alt text" marker and take the text up to the next marker.
    markers = list(ALT_RE.finditer(draft_text))
    alts = {}
    unnamed = []
    for i, m in enumerate(markers):
        start = m.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(draft_text)
        alt = draft_text[start:end].strip()
        # An alt text is one paragraph; cut at a blank line if one follows.
        alt = alt.split("\n\n")[0].strip()
        if not alt:
            raise SystemExit(
                "lesson %d: empty alt text at %r" % (lesson_num, m.group(0))
            )
        fname = m.group(1)
        if fname:
            alts[os.path.basename(fname)] = alt
        else:
            unnamed.append(alt)
    # Positional assignment for alt texts that name no file, in order.
    for fname in diagrams:
        if fname not in alts:
            if not unnamed:
                raise SystemExit(
                    "lesson %d: no alt text for %s" % (lesson_num, fname)
                )
            alts[fname] = unnamed.pop(0)
    if unnamed:
        raise SystemExit(
            "lesson %d: %d unassigned alt texts" % (lesson_num, len(unnamed))
        )
    return diagrams, alts


def to_blocks(lines):
    """Section lines -> [("p", text)] / [("ul", [items])].

    Each non-empty line is one paragraph (the drafts carry no hard wraps);
    consecutive "- " lines form one list.
    """
    blocks = []
    items = None
    for line in lines:
        if line.startswith("### "):
            # Subheading (lesson 15's "### Figure T-N" blocks). "### " does
            # not start with "## " so it never collides with section heads.
            items = None
            blocks.append(("h4", line[4:]))
        elif line.startswith("- "):
            if items is None:
                items = []
                blocks.append(("ul", items))
            items.append(line[2:])
        elif line.strip() == "":
            items = None
        else:
            items = None
            blocks.append(("p", line))
    return blocks


def parse_lesson(n):
    path = os.path.join(SRC, "lesson-%02d.md" % n)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    lines = text.split("\n")
    m = TITLE_RE.match(lines[0])
    assert m and int(m.group(1)) == n, "bad title line in %s" % path
    short_title = m.group(2)
    try:
        draft_idx = lines.index("## Draft note (not part of the post)")
    except ValueError:
        raise SystemExit("no Draft note in %s" % path)
    body_lines = lines[1:draft_idx]
    draft_text = "\n".join(lines[draft_idx + 1:])
    intro_lines = []
    sections = {}
    current = None
    current_lines = []
    for line in body_lines:
        if line.startswith("## "):
            if current is None:
                intro_lines = current_lines
            else:
                sections[current] = current_lines
            current = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current is None:
        intro_lines = current_lines
    else:
        sections[current] = current_lines
    found = list(sections.keys())
    assert found == SECTIONS, "section mismatch in %s: %r" % (path, found)
    diagrams, alts = parse_draft_note(draft_text, n)
    return {
        "num": n,
        "title": short_title,
        "intro": to_blocks(intro_lines),
        "sections": {name: to_blocks(sections[name]) for name in SECTIONS},
        "diagrams": diagrams,
        "alts": alts,
        "source_lines": body_lines,
    }


def parse_quiz(n):
    path = os.path.join(SRC, "quiz-%02d.md" % n)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    head, sep, key_text = text.partition(
        "## Answer key (for the admin — not part of the quiz post)"
    )
    assert sep, "no answer key in %s" % path
    lines = head.split("\n")
    assert QUIZ_TITLE_RE.match(lines[0]), "bad quiz title in %s" % path
    questions = []
    i = 1
    while i < len(lines):
        qm = QUESTION_RE.match(lines[i])
        if not qm:
            i += 1
            continue
        qnum, pool_id = int(qm.group(1)), qm.group(2)
        i += 1
        qlines = []
        while i < len(lines) and not OPTION_RE.match(lines[i]):
            if lines[i].strip():
                qlines.append(lines[i])
            i += 1
        options = []
        while i < len(lines):
            om = OPTION_RE.match(lines[i])
            if not om:
                break
            options.append((om.group(1), om.group(2)))
            i += 1
        assert len(options) == 4, "quiz %d Q%d: %d options" % (n, qnum, len(options))
        questions.append(
            {"num": qnum, "pool": pool_id, "text": " ".join(qlines), "options": options}
        )
    # Quiz sizes vary by lesson (Gregory, 2026-11-16): 4 questions for
    # lessons 1-10, 6 for most later lessons, 12 for the components and
    # modes lessons (13, 14, 15, 18, 19, 27). Lesson 24 has 3: only
    # three pool questions cover exam day.
    assert 1 <= len(questions) <= 12, "quiz %d: %d questions" % (
        n,
        len(questions),
    )
    keys = {}
    for line in key_text.split("\n"):
        km = KEY_RE.match(line)
        if km:
            keys[int(km.group(1))] = (km.group(2), km.group(3))
    assert len(keys) == len(questions), (
        "quiz %d: %d answer keys for %d questions"
        % (n, len(keys), len(questions))
    )
    for q in questions:
        letter, rest = keys[q["num"]]
        q["correct"] = letter
        opt_text = dict(q["options"])[letter]
        if rest.startswith(opt_text + ". "):
            q["explanation"] = rest[len(opt_text) + 2:]
        else:
            # Some keys paraphrase instead of repeating the option text;
            # then the whole remainder is the explanation.
            q["explanation"] = rest
        assert q["explanation"].strip(), "quiz %d Q%d: empty explanation" % (
            n,
            q["num"],
        )
    return questions

CSS = """
:root {
  --bg: #000000;
  --text: #ffffff;
  --good: #00ff00;
  --fair: #ffb300;
  --poor: #ff6666;
  --focus: #ffff00;
  --panel: #0d0d0d;
  --border: #ffffff;
  --muted: #cccccc;
  --on-focus: #000000;
  --on-good: #000000;
  --on-fair: #000000;
  --input-bg: #111111;
  --panel-hover: #1f1f1f;
  --good-hover: #66ff66;
  --reading-bg: #1a1a1a;
  --correct-bg: #003300;
  --wrong-bg: #330000;
  --hairline: #444444;
}
/* Light mode follows the device setting, unless the toggle has set
 * a choice. The bright-on-black palette stays the default. */
@media (prefers-color-scheme: light) {
  :root {
    --bg: #ffffff;
    --text: #000000;
    --good: #007a00;
    --fair: #7a5200;
    --poor: #b00000;
    --focus: #005fcc;
    --panel: #f5f5f5;
    --border: #000000;
    --muted: #555555;
    --on-focus: #ffffff;
    --on-good: #ffffff;
    --on-fair: #ffffff;
    --input-bg: #ffffff;
    --panel-hover: #e0e0e0;
    --good-hover: #005a00;
    --reading-bg: #e6f0ff;
    --correct-bg: #d9f2d9;
    --wrong-bg: #f8d7d7;
    --hairline: #888888;
  }
}
/* A choice from the toggle beats the device setting either way. */
:root[data-theme="dark"] {
  --bg: #000000;
  --text: #ffffff;
  --good: #00ff00;
  --fair: #ffb300;
  --poor: #ff6666;
  --focus: #ffff00;
  --panel: #0d0d0d;
  --border: #ffffff;
  --muted: #cccccc;
  --on-focus: #000000;
  --on-good: #000000;
  --on-fair: #000000;
  --input-bg: #111111;
  --panel-hover: #1f1f1f;
  --good-hover: #66ff66;
  --reading-bg: #1a1a1a;
  --correct-bg: #003300;
  --wrong-bg: #330000;
  --hairline: #444444;
}
:root[data-theme="light"] {
  --bg: #ffffff;
  --text: #000000;
  --good: #007a00;
  --fair: #7a5200;
  --poor: #b00000;
  --focus: #005fcc;
  --panel: #f5f5f5;
  --border: #000000;
  --muted: #555555;
  --on-focus: #ffffff;
  --on-good: #ffffff;
  --on-fair: #ffffff;
  --input-bg: #ffffff;
  --panel-hover: #e0e0e0;
  --good-hover: #005a00;
  --reading-bg: #e6f0ff;
  --correct-bg: #d9f2d9;
  --wrong-bg: #f8d7d7;
  --hairline: #888888;
}
* { box-sizing: border-box; }
html { font-size: 20px; scroll-padding-top: 10rem; }

/* Anchor jumps (contents links, next-lesson links) must clear the sticky
   Reading controls bar pinned to the top of the viewport: without this
   the jumped-to heading hides underneath it (found 2026-11-16). The bar
   is about 154px tall on desktop and up to about 410px on a narrow phone,
   where its controls stack into four rows and the status line can wrap. */
@media (max-width: 600px) {
  html { scroll-padding-top: 22rem; }
}
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: Verdana, Geneva, "Segoe UI", Tahoma, sans-serif;
  line-height: 1.5;
  padding: 1rem;
}
.wrap { max-width: 46rem; margin: 0 auto; }

.skip-link {
  position: absolute;
  left: -9999px;
  top: 0;
  background: var(--focus);
  color: var(--on-focus);
  font-weight: bold;
  padding: 0.75rem 1rem;
  z-index: 10;
}
.skip-link:focus { left: 0.5rem; top: 0.5rem; }

a { color: var(--fair); }
a:focus-visible, button:focus-visible, select:focus-visible {
  outline: 4px solid var(--focus);
  outline-offset: 3px;
}

h1 { font-size: 2rem; line-height: 1.2; margin: 0.5rem 0 0.25rem; }
h2 { font-size: 1.5rem; margin: 1.75rem 0 0.5rem; }
h3 { font-size: 1.25rem; margin: 1.25rem 0 0.5rem; }
h4 { font-size: 1.15rem; margin: 1rem 0 0.5rem; }
p { margin: 0.5rem 0; }
ul, ol { margin: 0.5rem 0; padding-left: 1.5rem; }
li { margin: 0.35rem 0; }

.intro { font-size: 1.1rem; }

.theme-toggle {
  font: inherit;
  font-size: 1.2rem;
  font-weight: bold;
  color: var(--text);
  background: var(--bg);
  border: 3px solid var(--border);
  padding: 0.6rem 1rem;
  min-height: 3rem;
  cursor: pointer;
}
.theme-toggle:hover { background: var(--panel-hover); }
.theme-note { font-size: 1.05rem; color: var(--muted); }

.back-link {
  display: block;
  border: 3px solid var(--border);
  background: var(--panel);
  color: var(--text);
  font-size: 1.25rem;
  font-weight: bold;
  text-align: center;
  text-decoration: underline;
  padding: 1rem;
  margin: 1rem 0 0.5rem;
  min-height: 3.5rem;
}
.back-link:hover { background: var(--panel-hover); }
button.back-link {
  font: inherit;
  cursor: pointer;
  text-decoration: none;
  width: 100%;
}
.close-note {
  font-size: 1.2rem;
  font-weight: bold;
  margin: 0.5rem 0;
}

.listen-controls {
  position: sticky;
  top: 0;
  z-index: 5;
  background: var(--bg);
  border: 3px solid var(--good);
  padding: 0.75rem 1rem;
  margin: 1rem 0;
}
.listen-controls .listen-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
}
.listen-controls .listen-row button {
  flex: 1 1 8rem;
  min-height: 3rem;
  padding: 0.6rem 1rem;
  font: inherit;
  font-size: 1.2rem;
  font-weight: bold;
  color: var(--text);
  background: var(--bg);
  border: 3px solid var(--border);
  cursor: pointer;
}
.listen-controls .listen-row button:hover { background: var(--panel-hover); }
.listen-controls .listen-row button[disabled] { opacity: 0.5; cursor: default; }
.listen-controls .listen-row label { font-size: 1.1rem; font-weight: bold; }
.listen-controls .listen-row select {
  font: inherit;
  font-size: 1.1rem;
  color: var(--text);
  background: var(--input-bg);
  border: 3px solid var(--border);
  padding: 0.5rem;
  min-height: 3rem;
}
.status {
  font-size: 1.2rem;
  font-weight: bold;
  min-height: 1.8em;
  margin: 0.75rem 0 0;
}

button.listen-btn {
  display: block;
  width: 100%;
  min-height: 3.5rem;
  margin: 1rem 0 0.75rem;
  padding: 0.9rem 1rem;
  font: inherit;
  font-size: 1.35rem;
  font-weight: bold;
  color: var(--on-good);
  background: var(--good);
  border: 3px solid var(--good);
  cursor: pointer;
}
button.listen-btn:hover { background: var(--good-hover); }
button.listen-btn[disabled] { opacity: 0.5; cursor: default; }

/* Visually hidden but announced by screen readers: the spoken form of
   SWR ratios ("one to one") lives here while "1:1" stays visible. */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.reading {
  outline: 3px solid var(--focus);
  outline-offset: 4px;
  background: var(--reading-bg);
}

#contents ol li { margin: 0.5rem 0; font-size: 1.15rem; }

.lesson {
  border-top: 3px solid var(--border);
  padding-top: 0.5rem;
  margin-top: 2.5rem;
}

figure.diagram { margin: 1rem 0; }
figure.diagram img {
  max-width: 100%;
  height: auto;
  border: 2px solid var(--border);
}

.quiz {
  border: 3px solid var(--fair);
  background: var(--panel);
  padding: 1rem 1.25rem;
  margin: 1.5rem 0 0;
}
.quiz h2 { margin-top: 0; }
.quiz-question { margin: 1.25rem 0; }
.quiz-text { font-weight: bold; font-size: 1.15rem; }
.pool-id { font-size: 0.95rem; color: var(--muted); margin: 0.25rem 0 0.75rem; }
.quiz-option {
  display: block;
  width: 100%;
  text-align: left;
  min-height: 3rem;
  padding: 0.6rem 1rem;
  margin: 0.5rem 0;
  font: inherit;
  font-size: 1.15rem;
  color: var(--text);
  background: var(--bg);
  border: 3px solid var(--border);
  cursor: pointer;
}
.quiz-option:hover { background: var(--panel-hover); }
.quiz-option[disabled] { cursor: default; }
.quiz-option.chosen-correct { border-color: var(--good); background: var(--correct-bg); }
.quiz-option.chosen-wrong { border-color: var(--poor); background: var(--wrong-bg); }
.quiz-option.correct-answer { border-color: var(--good); }
.opt-letter { font-weight: bold; }
.quiz-feedback {
  font-size: 1.15rem;
  font-weight: bold;
  margin: 0.75rem 0 0;
  padding: 0.75rem 1rem;
  border: 3px solid var(--border);
}
.quiz-feedback.feedback-correct { border-color: var(--good); }
.quiz-feedback.feedback-wrong { border-color: var(--poor); }

.next-link { font-size: 1.2rem; font-weight: bold; margin: 1.25rem 0 0; }

.braille {
  border: 3px solid var(--good);
  background: var(--panel);
  padding: 1rem 1.25rem;
  margin: 2rem 0 0;
}
.braille h2 { margin-top: 0; }

.reference {
  border: 3px solid var(--fair);
  background: var(--panel);
  padding: 1rem 1.25rem;
  margin: 2rem 0 0;
}
.reference h2 { margin-top: 0; }

.about {
  font-size: 1.05rem;
  color: var(--muted);
  margin-top: 2rem;
  border-top: 1px solid var(--hairline);
  padding-top: 1rem;
}
"""

# JavaScript. The read-aloud engine and the close-button / deep-link blocks
# are copied from the Lesson 1 proof-of-concept page (which copied the
# close-button pattern from the HamClock page); the read-aloud queue is
# built per lesson instead of once for a single lesson. The quiz block is
# new. Plain ES5 throughout, matching the PoC.
JS = """
(function () {
  "use strict";

  // ---- Read-aloud (browser speech, no audio files) ---------------------------
  // Each lesson is read sentence by sentence, one short utterance at a time,
  // chained by each utterance's onend event. A single 900-word utterance is
  // unreliable in several browsers (long pauses, cut-offs), and the chained
  // approach means a speed change takes effect on the next sentence.
  // Copied from the Lesson 1 proof-of-concept page; the queue is built from
  // whichever lesson's or quiz's Listen button was pressed, and what the
  // voice speaks goes through prepareSpeech first (see below).
  var listenBtns = document.querySelectorAll(".listen-btn");
  var pauseBtn = document.getElementById("pause-btn");
  var stopBtn = document.getElementById("stop-btn");
  var rateSelect = document.getElementById("rate-select");
  var statusEl = document.getElementById("read-status");

  var SUPPORTED = ("speechSynthesis" in window) && ("SpeechSynthesisUtterance" in window);

  // ---- Speech preparation ---------------------------------------------------
  // The visible text is approved wording and is never changed. What the
  // voice speaks goes through prepareSpeech first, which fixes the ways the
  // voice misreads the text (found by listening through every lesson on
  // 2026-11-16, plus the screen-reader character audit of 2026-11-16):
  //   * "coax" comes out as "cokes" — spoken as "co-ax".
  //   * In formulas, "x" comes out as the letter "ex" and "/" as "slash" —
  //     spoken as "times" and "divided by".
  //   * In formulas, "=" is skipped, "+" and "-" collapse to silence, and
  //     "E2"/"I2" come out as "E two"/"I two" — spoken as "equals",
  //     "plus", "minus", and "squared".
  //   * Fractions come out as two numbers — "5/8" as "five eight" —
  //     spoken as "five eighths".
  //   * A parenthetical abbreviation is expanded by the voice, so
  //     "megahertz (MHz)" comes out as "megahertz megahertz" — spoken as
  //     "megahertz, common abbreviation M H Z".
  // The table below is the complete set of parenthetical abbreviations in
  // the lessons and quizzes (audited 2026-11-16; eight more found by the
  // screen-reader character audit and added 2026-11-17). Bare abbreviations
  // that the voice already reads right — "146.52 MHz", "3 dB", "SWR meter" —
  // are left alone.
  var SPEECH_ABBREVIATIONS = {
    "MHz": "M H Z", "kHz": "k H z", "Hz": "H z",
    "DC": "D C", "AC": "A C", "FCC": "F C C", "SWR": "S W R",
    "LED": "L E D", "IC": "I C", "VHF": "V H F", "UHF": "U H F",
    "RF": "R F", "HF": "H F", "VEC": "V E C", "FRN": "F R N",
    "ARRL": "A R R L", "ID": "I D", "dB": "d B",
    "ISS": "I S S", "ARES": "A R E S", "SSB": "S S B", "PSK": "P S K",
    "VFO": "V F O", "CSCE": "C S C E", "VoIP": "V o I P", "CODEC": "C O D E C"
  };

  function prepareSpeech(text) {
    // Parenthetical abbreviations: "megahertz (MHz)" ->
    // "megahertz, common abbreviation M H Z". Only the abbreviations in
    // the table are rewritten; word parentheticals such as "(Yagi)",
    // "(amp)" or "(coil)" are left to read as ordinary words. When more
    // words follow the parenthesis, a comma closes the spoken aside so
    // the voice pauses: "megahertz, common abbreviation M H Z, is ...".
    text = text.replace(/ \\(([A-Za-z]+)\\)/g, function (match, abbr, offset, str) {
      if (SPEECH_ABBREVIATIONS[abbr] !== undefined) {
        var spoken = ", common abbreviation " + SPEECH_ABBREVIATIONS[abbr];
        if (str.charAt(offset + match.length) === " ") spoken += ",";
        return spoken;
      }
      return match;
    });
    // Formula operators: "E = I x R" -> "E = I times R", "I = E / R" ->
    // "I = E divided by R". Single capital letters (with an optional
    // digit, as in "E2 x R") only, so ordinary words are never touched.
    text = text.replace(/\\b([A-Z][0-9]?) x ([A-Z])\\b/g, "$1 times $2");
    text = text.replace(/\\b([A-Z][0-9]?) \\/ ([A-Z])\\b/g, "$1 divided by $2");
    // "=" is skipped by the voice too, so "E = I x R" came out as
    // "E I times R". "+" and "-" inside formulas likewise: "R = E + I"
    // and "R = E - I" both came out as "R E I". Same single-letter
    // scoping, so ordinary words are never touched.
    text = text.replace(/\\b([A-Z][0-9]?) = ([A-Z][0-9]?)\\b/g, "$1 equals $2");
    text = text.replace(/\\b([A-Z]) \\+ ([A-Z])\\b/g, "$1 plus $2");
    text = text.replace(/\\b([A-Z]) [-−] ([A-Z])\\b/g, "$1 minus $2");
    // Squared notation: "E2" and "I2" come out as "E two" and "I two".
    // The 2 means squared, and no lesson teaches the notation, so the
    // voice says the word. Runs after the "x" rule above: "E2 x R" is
    // already "E2 times R" by now, so the "x" rule still matches.
    text = text.replace(/\\b([EI])2\\b/g, "$1 squared");
    // SWR ratios: "1.2:1" -> "one point two to one". VoiceOver and the
    // read-aloud voice skip colons, so "1:1" came out as "one one".
    // Only ratios (a number, a colon, 1) are rewritten; clock times
    // never match, because their minutes are not the digit 1.
    var ratioOnes = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"];
    var ratioTeens = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"];
    var ratioTens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"];
    function ratioNumberToWords(num) {
      var parts = num.split(".");
      var whole = parseInt(parts[0], 10);
      var words;
      if (whole < 10) words = ratioOnes[whole];
      else if (whole < 20) words = ratioTeens[whole - 10];
      else {
        words = ratioTens[Math.floor(whole / 10)];
        if (whole % 10) words += " " + ratioOnes[whole % 10];
      }
      if (parts.length > 1) {
        words += " point";
        for (var d = 0; d < parts[1].length; d++) {
          words += " " + ratioOnes[parseInt(parts[1].charAt(d), 10)];
        }
      }
      return words;
    }
    text = text.replace(/\\b(\\d+(?:\\.\\d+)?):1\\b/g, function (match, num) {
      return ratioNumberToWords(num) + " to one";
    });
    // Fractions: "5/8" came out as "five eight" or "five slash eight".
    // Only the fractions the course uses are covered (5/8, 1/2, 1/10);
    // anything outside the table below is left alone. ratioOnes and
    // ratioTeens are the arrays from the ratio block just above.
    var fractionDenoms = {2: ["half", "halves"], 3: ["third", "thirds"], 4: ["quarter", "quarters"], 5: ["fifth", "fifths"], 6: ["sixth", "sixths"], 7: ["seventh", "sevenths"], 8: ["eighth", "eighths"], 9: ["ninth", "ninths"], 10: ["tenth", "tenths"], 11: ["eleventh", "elevenths"], 12: ["twelfth", "twelfths"]};
    text = text.replace(/\\b(\\d+)\\/(\\d+)\\b/g, function (match, num, den) {
      var n = parseInt(num, 10), d = parseInt(den, 10);
      if (!fractionDenoms[d] || n < 1 || n > 19) return match;
      var numWord = n < 10 ? ratioOnes[n] : ratioTeens[n - 10];
      return numWord + " " + (n === 1 ? fractionDenoms[d][0] : fractionDenoms[d][1]);
    });
    // "coax" is spoken as "cokes"; "co-ax" comes out right. The word
    // boundary keeps "coaxial" untouched.
    text = text.replace(/\\bcoax\\b/gi, "co-ax");
    return text;
  }

  // Split a block of text into sentences. A period between two digits
  // (146.52) is a decimal point, not a sentence end. Closing quotes or
  // brackets after the terminator stay with the sentence.
  function splitSentences(text) {
    var sentences = [];
    var start = 0;
    for (var i = 0; i < text.length; i++) {
      var ch = text.charAt(i);
      if (ch === "." || ch === "!" || ch === "?") {
        var prev = text.charAt(i - 1), next = text.charAt(i + 1);
        if (ch === "." && prev >= "0" && prev <= "9" && next >= "0" && next <= "9") continue;
        var end = i + 1;
        while (end < text.length && "\\"')]}".indexOf(text.charAt(end)) !== -1) end++;
        if (end >= text.length || /\\s/.test(text.charAt(end))) {
          sentences.push(text.slice(start, end).trim());
          start = end;
        }
      }
    }
    var tail = text.slice(start).trim();
    if (tail) sentences.push(tail);
    return sentences.filter(Boolean);
  }

  // The reading queue: one item per sentence, each tied to the block it came
  // from so that block can be highlighted while it is read. Built fresh
  // from the chosen lesson each time a Listen button is pressed.
  var queue = [];
  var pointer = 0;
  var reading = false;
  var currentBlock = null;
  var currentSection = "Lesson";
  var currentKind = "lesson";
  var currentNum = 0;
  var currentLabel = "";

  // Text of a block as the voice should speak it: the visually hidden
  // ("sr-only") spans are removed first, because they duplicate text the
  // voice already says another way (SWR ratios: the visible "1:1" is
  // spoken as "one to one" by prepareSpeech, and the sr-only span holds
  // the same words for screen readers). The live page is never touched:
  // the clone is thrown away.
  function blockSpokenText(block) {
    var clone = block.cloneNode(true);
    var hidden = clone.querySelectorAll(".sr-only");
    for (var i = 0; i < hidden.length; i++) {
      hidden[i].parentNode.removeChild(hidden[i]);
    }
    return clone.textContent.replace(/\\s+/g, " ").trim();
  }

  function buildQueue(sectionEl) {
    queue = [];
    var blocks = sectionEl.querySelectorAll(".readable");
    for (var b = 0; b < blocks.length; b++) {
      var blockText = prepareSpeech(blockSpokenText(blocks[b]));
      var section = blocks[b].getAttribute("data-section") || "Lesson";
      var sentences = splitSentences(blockText);
      for (var s = 0; s < sentences.length; s++) {
        queue.push({ text: sentences[s], block: blocks[b], section: section });
      }
    }
  }

  // The spoken-only end-of-lesson cue. It is not visible text: it is
  // appended to the queue after the lesson's last sentence, so the
  // listener hears the lesson end and knows the quiz follows.
  function appendEndOfLessonCue(lessonNum) {
    queue.push({
      text: "End of lesson " + lessonNum + ". Your quiz is next.",
      block: null,
      section: "End of lesson"
    });
  }

  // Build the queue for a quiz: the heading, then each question with its
  // four options. The correct answer is never spoken: the queue is built
  // from visible text only, and data-correct is never read here. If a
  // question has already been answered, its feedback (verdict plus the
  // "why" explanation) is read after its options; pressing the quiz's
  // Listen button again after answering is how the feedback is heard.
  // Pool IDs ("Pool question T5D01") are admin metadata, not lesson
  // content, and are not read aloud.
  function buildQuizQueue(quizEl, quizNum) {
    queue = [];
    var heading = quizEl.querySelector("h2");
    if (heading) {
      queue.push({
        text: prepareSpeech(blockSpokenText(heading)),
        block: heading,
        section: "Quiz " + quizNum
      });
    }
    var questions = quizEl.querySelectorAll(".quiz-question");
    for (var qi = 0; qi < questions.length; qi++) {
      var qEl = questions[qi];
      var qNum = qi + 1;
      var qText = qEl.querySelector(".quiz-text");
      var sentences = splitSentences(prepareSpeech(blockSpokenText(qText)));
      for (var s = 0; s < sentences.length; s++) {
        queue.push({ text: sentences[s], block: qText, section: "Question " + qNum });
      }
      var options = qEl.querySelectorAll(".quiz-option");
      for (var oi = 0; oi < options.length; oi++) {
        var optSentences = splitSentences(prepareSpeech(blockSpokenText(options[oi])));
        for (var os = 0; os < optSentences.length; os++) {
          queue.push({ text: optSentences[os], block: options[oi], section: "Question " + qNum });
        }
      }
      var feedback = qEl.querySelector(".quiz-feedback");
      if (feedback && !feedback.hidden) {
        var fbSentences = splitSentences(prepareSpeech(blockSpokenText(feedback)));
        for (var fs = 0; fs < fbSentences.length; fs++) {
          queue.push({ text: fbSentences[fs], block: feedback, section: "Feedback" });
        }
      }
    }
  }

  function setStatus(text) { statusEl.textContent = text; }

  function statusFor(section) {
    if (
      section === currentLabel ||
      section.indexOf("Lesson ") === 0 ||
      section.indexOf("Quiz ") === 0
    ) {
      return "Reading " + section + ".";
    }
    if (section === "End of lesson") {
      return "End of " + currentLabel + ". Your quiz is next.";
    }
    return "Reading " + currentLabel + " — " + section + ".";
  }

  function highlight(block) {
    if (currentBlock) currentBlock.classList.remove("reading");
    currentBlock = block || null;
    if (currentBlock) currentBlock.classList.add("reading");
  }

  function updateButtons() {
    if (!SUPPORTED) {
      for (var li = 0; li < listenBtns.length; li++) listenBtns[li].disabled = true;
      pauseBtn.disabled = true;
      stopBtn.disabled = true;
      rateSelect.disabled = true;
      return;
    }
    pauseBtn.disabled = !reading;
    stopBtn.disabled = !reading;
    pauseBtn.textContent = (reading && window.speechSynthesis.paused) ? "Resume" : "Pause";
  }

  function finish() {
    reading = false;
    highlight(null);
    if (currentKind === "lesson") {
      setStatus("Finished reading " + currentLabel + ". Your quiz is next.");
    } else {
      setStatus("Finished reading " + currentLabel + ".");
    }
    updateButtons();
    // After a lesson, bring the listener to the quiz: scroll it into view
    // and move keyboard focus to its heading, so the next tap lands on
    // the quiz instead of somewhere in the middle of the lesson.
    if (currentKind === "lesson") {
      var quizHeading = document.getElementById("quiz-" + currentNum + "-heading");
      if (quizHeading) {
        quizHeading.scrollIntoView();
        quizHeading.focus();
      }
    }
  }

  function speakNext() {
    if (!reading) return;
    if (pointer >= queue.length) { finish(); return; }
    var item = queue[pointer];
    if (item.block !== currentBlock) {
      highlight(item.block);
      currentSection = item.section;
      setStatus(statusFor(item.section));
    }
    var utterance = new SpeechSynthesisUtterance(item.text);
    utterance.rate = parseFloat(rateSelect.value) || 1;
    utterance.onend = function () {
      if (!reading) return;
      pointer++;
      speakNext();
    };
    utterance.onerror = function () {
      if (!reading) return;
      pointer++;
      speakNext();
    };
    window.speechSynthesis.speak(utterance);
  }

  function startReading(kind, num) {
    if (!SUPPORTED) return;
    var sectionEl = document.getElementById(kind + "-" + num);
    if (!sectionEl) return;
    currentKind = kind;
    currentNum = num;
    currentLabel = (kind === "quiz" ? "Quiz " : "Lesson ") + num;
    // Cancel first with reading off, so any end/error event from the
    // cancelled utterance is ignored instead of advancing the queue.
    reading = false;
    window.speechSynthesis.cancel();
    if (kind === "quiz") {
      buildQuizQueue(sectionEl, num);
    } else {
      buildQueue(sectionEl);
      appendEndOfLessonCue(num);
    }
    pointer = 0;
    reading = true;
    setStatus("Starting to read " + currentLabel + ".");
    updateButtons();
    speakNext();
  }

  // Read a standalone reference section (the phonetic alphabet) aloud.
  // Like a lesson but with no end-of-lesson cue and no quiz handoff.
  function startReadingSection(targetId, label) {
    if (!SUPPORTED) return;
    var sectionEl = document.getElementById(targetId);
    if (!sectionEl) return;
    currentKind = "section";
    currentNum = 0;
    currentLabel = label;
    // Cancel first with reading off, so any end/error event from the
    // cancelled utterance is ignored instead of advancing the queue.
    reading = false;
    window.speechSynthesis.cancel();
    buildQueue(sectionEl);
    pointer = 0;
    reading = true;
    setStatus("Starting to read " + currentLabel + ".");
    updateButtons();
    speakNext();
  }

  function stopReading() {
    reading = false;
    window.speechSynthesis.cancel();
    pointer = 0;
    highlight(null);
    setStatus("Stopped.");
    updateButtons();
  }

  function togglePause() {
    if (!reading) return;
    var synth = window.speechSynthesis;
    if (synth.paused) {
      synth.resume();
      setStatus(statusFor(currentSection));
    } else {
      synth.pause();
      setStatus("Paused.");
    }
    updateButtons();
  }

  if (!SUPPORTED) {
    setStatus("Your browser cannot read this page aloud. You can still read the lessons here, or use your device's screen reader.");
    updateButtons();
  } else {
    for (var lb = 0; lb < listenBtns.length; lb++) {
      (function (btn) {
        btn.addEventListener("click", function () {
          var lessonNum = btn.getAttribute("data-lesson");
          var quizNum = btn.getAttribute("data-quiz");
          var readTarget = btn.getAttribute("data-read");
          if (lessonNum) {
            startReading("lesson", lessonNum);
          } else if (quizNum) {
            startReading("quiz", quizNum);
          } else if (readTarget) {
            startReadingSection(readTarget, btn.getAttribute("data-read-label"));
          }
        });
      })(listenBtns[lb]);
    }
    pauseBtn.addEventListener("click", togglePause);
    stopBtn.addEventListener("click", stopReading);
    updateButtons();
  }

  // ---- Quizzes ----------------------------------------------------------------
  // Each question has four option buttons. Tapping one answers the question:
  // all four options lock, the right one is marked green, and the feedback
  // appears with the explanation from the answer key. Feedback stays hidden
  // until the question is answered.
  var quizQuestions = document.querySelectorAll(".quiz-question");
  for (var qi = 0; qi < quizQuestions.length; qi++) {
    (function (qEl) {
      var options = qEl.querySelectorAll(".quiz-option");
      var feedback = qEl.querySelector(".quiz-feedback");
      var verdict = qEl.querySelector(".verdict");
      var correctLetter = qEl.getAttribute("data-correct-letter");
      var answered = false;
      for (var oi = 0; oi < options.length; oi++) {
        options[oi].addEventListener("click", function () {
          if (answered) return;
          answered = true;
          var isRight = this.getAttribute("data-correct") === "true";
          for (var oj = 0; oj < options.length; oj++) {
            options[oj].disabled = true;
            if (options[oj].getAttribute("data-correct") === "true") {
              options[oj].classList.add("correct-answer");
            }
          }
          if (isRight) {
            this.classList.add("chosen-correct");
            verdict.textContent = "Correct.";
            feedback.classList.add("feedback-correct");
          } else {
            this.classList.add("chosen-wrong");
            verdict.textContent = "Not quite. The right answer is " + correctLetter + ".";
            feedback.classList.add("feedback-wrong");
          }
          feedback.hidden = false;
        });
      }
    })(quizQuestions[qi]);
  }

  // ---- Close buttons in Facebook's in-app browser ---------------------------
  // No link form reaches the group from inside Facebook's own browser: the
  // www address, the mobile address, and the fb:// deep link were each
  // tested fresh on Gregory's phone and each ended at "Page not found"
  // (2026-11-15). So inside that browser the back-links become close
  // buttons instead: window.close() if the browser honours it, and if the
  // page is still open a second later, a plain instruction to use the X
  // button at the top left, which returns to the Facebook app.
  // window.close() is PROVEN not to work in Facebook's iOS webview
  // (tested 2026-11-15), so the fallback instruction is what members
  // actually use. Outside that browser the back-links stay as they are.
  // Copied from the HamClock page via the Lesson 1 proof-of-concept page.
  var FB_WEBVIEW = /FBAN|FBAV|FB_IAB/i.test(navigator.userAgent);
  if (FB_WEBVIEW) {
    var backAnchors = document.querySelectorAll('a[href*="facebook.com/groups/742838019382868"]');
    for (var bi = 0; bi < backAnchors.length; bi++) {
      (function (anchor) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "back-link";
        btn.textContent = "Close this page and return to Facebook";
        var noteShown = false;
        btn.addEventListener("click", function () {
          window.close();
          setTimeout(function () {
            if (!document.hidden && !noteShown) {
              noteShown = true;
              var note = document.createElement("p");
              note.className = "close-note";
              note.setAttribute("role", "status");
              note.textContent = "This browser won't let the page close itself. To go back to Facebook, tap the X button at the top left of the screen.";
              btn.parentNode.insertBefore(note, btn.nextSibling);
            }
          }, 1200);
        });
        anchor.parentNode.replaceChild(btn, anchor);
      })(backAnchors[bi]);
    }
  }

  // ---- Back-to-group links (other mobile browsers) ---------------------------
  // Inside Facebook's own browser the links above are replaced by close
  // buttons (see the block above), because every link form fails there.
  // In other mobile browsers (Safari, Chrome), try the native app deep link
  // fb://group/<id> first — it opens the group in the Facebook app — and
  // fall back to the plain web address if the app does not open. On desktop
  // the web address works fine, so the link behaves normally. Without
  // JavaScript the links are plain web addresses.
  // Copied from the HamClock page via the Lesson 1 proof-of-concept page.
  var GROUP_DEEP_LINK = "fb://group/742838019382868";
  var isMobile = /Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
  if (isMobile) {
    var groupLinks = document.querySelectorAll('a[href*="facebook.com/groups/742838019382868"]');
    for (var gi = 0; gi < groupLinks.length; gi++) {
      groupLinks[gi].addEventListener("click", function (event) {
        event.preventDefault();
        var fallbackUrl = this.href;
        var attemptedAt = Date.now();
        window.location.href = GROUP_DEEP_LINK;
        setTimeout(function () {
          // If the Facebook app opened, this page is hidden or gone; only
          // fall back when we are still here and visible.
          if (!document.hidden && Date.now() - attemptedAt < 5000) {
            window.location.href = fallbackUrl;
          }
        }, 1500);
      });
    }
  }

  // ---- Light and dark mode ---------------------------------------------------
  // The page defaults to the bright-on-black palette. A device set to
  // light mode gets the light palette automatically, and the toggle
  // button lets anyone pick either way. The choice is remembered on
  // this device only. Same pattern as the grid locator page.
  function systemTheme() {
    if (typeof window !== "undefined" && window.matchMedia
      && window.matchMedia("(prefers-color-scheme: light)").matches) return "light";
    return "dark";
  }

  function currentTheme() {
    if (typeof document !== "undefined" && document.documentElement) {
      var t = document.documentElement.getAttribute("data-theme");
      if (t === "light" || t === "dark") return t;
    }
    return systemTheme();
  }

  function themeLabel(theme) {
    return theme === "light" ? "Switch to dark mode" : "Switch to light mode";
  }

  function applyTheme(theme, remember) {
    if (typeof document !== "undefined" && document.documentElement) {
      document.documentElement.setAttribute("data-theme", theme);
    }
    var btn = document.getElementById("theme-toggle");
    if (btn) btn.textContent = themeLabel(theme);
    if (remember) {
      try {
        if (typeof localStorage !== "undefined") {
          localStorage.setItem("technician-class-theme", theme);
        }
      } catch (e) { /* private mode: the choice just is not remembered */ }
    }
  }

  /* Theme toggle: label it for the theme in use, and follow the device
   * if the user has never picked one. */
  var themeBtn = document.getElementById("theme-toggle");
  if (themeBtn) {
    themeBtn.textContent = themeLabel(currentTheme());
    themeBtn.addEventListener("click", function () {
      applyTheme(currentTheme() === "light" ? "dark" : "light", true);
    });
  }
  if (typeof window !== "undefined" && window.matchMedia) {
    var lightQuery = window.matchMedia("(prefers-color-scheme: light)");
    if (lightQuery.addEventListener) {
      lightQuery.addEventListener("change", function () {
        var stored = null;
        try {
          if (typeof localStorage !== "undefined") {
            stored = localStorage.getItem("technician-class-theme");
          }
        } catch (e) { stored = null; }
        if (stored !== "light" && stored !== "dark") {
          applyTheme(lightQuery.matches ? "light" : "dark", false);
        }
      });
    }
  }
})();
"""


def intro_paragraphs(n_lessons):
    """The intro paragraphs under the page title, with live counts."""
    return [
        "This free course takes you from your first look at ham radio to your "
        "Technician exam. It has %d lessons, and each one has a short quiz. Work "
        "through the lessons in order, from Lesson 1 to Lesson %d. Each lesson "
        "takes about 10 minutes to read or hear." % (n_lessons, n_lessons),
        "Every lesson has a Listen button that reads it aloud with the voice "
        "built into your device. No audio files are used. The quizzes use real "
        "questions from the Technician exam pool. The real exam has 35 questions, "
        "and you need 26 right to pass.",
    ]

ABOUT = (
    "Technician License Class. The lessons use plain words and work with "
    "screen readers. Each term is defined right where you meet it. Ask "
    "questions in the group any time."
)

ORDINALS = ["first", "second", "third"]


def render_block(block, section_name):
    kind, val = block
    if kind == "p":
        return '<p class="readable" data-section="%s">%s</p>' % (
            esc(section_name),
            mark_spoken(esc(val)),
        )
    if kind == "h4":
        return '<h4 class="readable" data-section="%s">%s</h4>' % (
            esc(section_name),
            mark_spoken(esc(val)),
        )
    lis = []
    for item in val:
        if section_name == "Words to know" and ": " in item:
            term, definition = item.split(": ", 1)
            lis.append(
                '<li class="readable" data-section="%s"><strong>%s:</strong> %s</li>'
                % (
                    esc(section_name),
                    mark_spoken(esc(term)),
                    mark_spoken(esc(definition)),
                )
            )
        else:
            lis.append(
                '<li class="readable" data-section="%s">%s</li>'
                % (esc(section_name), mark_spoken(esc(item)))
            )
    return "<ul>\n" + "\n".join(lis) + "\n</ul>"


def render_blocks(blocks, section_name):
    return "\n".join(render_block(b, section_name) for b in blocks)


def figure_html(fname, alt):
    return (
        '<figure class="diagram">'
        '<img src="diagrams/%s" alt="%s" loading="lazy" />'
        "</figure>"
    ) % (esc(fname), esc(alt))


def compute_placements(lesson):
    """Where each diagram goes inside "The idea in plain words".

    Returns {block_index: [diagram files]} — each figure is placed right
    after the paragraph (or "### Figure T-N" subsection) that describes it:
      - Lesson 15: figure-tN.png after the "### Figure T-N" subsection.
      - "first/second/third picture" paragraphs (lessons 12, 20).
      - "The picture/diagram with this lesson shows ..." paragraphs.
    Fails loudly if any diagram finds no anchor.
    """
    blocks = lesson["sections"]["The idea in plain words"]
    diagrams = lesson["diagrams"]
    placements = {}
    if not diagrams:
        return placements
    placed = set()
    # Rule 1: "### Figure T-N" subsections.
    h4_indices = [i for i, (k, _v) in enumerate(blocks) if k == "h4"]
    for idx in h4_indices:
        m = re.match(r"Figure T-(\d)", blocks[idx][1])
        if not m:
            continue
        fname = "figure-t%s.png" % m.group(1)
        if fname not in diagrams:
            continue
        nxt = min([j for j in h4_indices if j > idx] or [len(blocks)])
        placements.setdefault(nxt - 1, []).append(fname)
        placed.add(fname)
    # Rules 2/3: anchor paragraphs, in declaration order.
    for di, fname in enumerate(diagrams):
        if fname in placed:
            continue
        anchor = None
        if di < len(ORDINALS):
            needle = ORDINALS[di] + " picture"
            for i, (k, v) in enumerate(blocks):
                if k == "p" and needle in v:
                    anchor = i
                    break
        if anchor is None:
            for i, (k, v) in enumerate(blocks):
                if k == "p" and (
                    v.startswith("The picture with this lesson shows")
                    or v.startswith("The diagram with this lesson shows")
                ):
                    anchor = i
                    break
        if anchor is None:
            raise SystemExit(
                "lesson %d: no anchor paragraph for %s" % (lesson["num"], fname)
            )
        placements.setdefault(anchor, []).append(fname)
        placed.add(fname)
    return placements


def lesson_html(lesson):
    n = lesson["num"]
    title = lesson["title"]
    parts = []
    parts.append(
        '<section class="lesson" id="lesson-%d" aria-labelledby="lesson-%d-heading">'
        % (n, n)
    )
    parts.append(
        '<h2 id="lesson-%d-heading" class="readable" data-section="Lesson %d">'
        "Lesson %d: %s</h2>" % (n, n, n, esc(title))
    )
    parts.append(
        '<button type="button" class="listen-btn" data-lesson="%d">'
        "Listen to this lesson</button>" % n
    )
    parts.append(render_blocks(lesson["intro"], "Introduction"))
    placements = compute_placements(lesson)
    for name in SECTIONS:
        parts.append(
            '<h3 class="readable" data-section="%s">%s</h3>' % (esc(name), esc(name))
        )
        blocks = lesson["sections"][name]
        if name == "The idea in plain words" and placements:
            rendered = []
            for i, block in enumerate(blocks):
                rendered.append(render_block(block, name))
                for fname in placements.get(i, []):
                    rendered.append(figure_html(fname, lesson["alts"][fname]))
            parts.append("\n".join(rendered))
        else:
            parts.append(render_blocks(blocks, name))
    parts.append("</section>")
    html_out = "\n".join(parts)
    # Link the first mention of the phonetic alphabet to the reference
    # section (lessons 3 and 6 only). The source prose is unchanged; the
    # link is added to the rendered page only.
    if n in (3, 6):
        if "phonetic alphabet" not in html_out:
            raise SystemExit(
                "lesson %d: no phonetic alphabet mention to link" % n
            )
        html_out = html_out.replace(
            "phonetic alphabet",
            '<a href="#phonetic-alphabet">phonetic alphabet</a>',
            1,
        )
    return html_out


def quiz_html(n, questions, next_title, lesson):
    parts = []
    parts.append(
        '<section class="quiz" id="quiz-%d" aria-labelledby="quiz-%d-heading">'
        % (n, n)
    )
    parts.append(
        '<h2 id="quiz-%d-heading" tabindex="-1">Check yourself — Lesson %d</h2>'
        % (n, n)
    )
    parts.append(
        '<button type="button" class="listen-btn" data-quiz="%d">'
        "Listen to this quiz</button>" % n
    )
    # Repeat the lesson's diagrams here so the member does not have to
    # scroll back up to the lesson to see the diagram a question refers
    # to. Same files, same alt text as in the lesson.
    for fname in lesson["diagrams"]:
        parts.append(figure_html(fname, lesson["alts"][fname]))
    for q in questions:
        parts.append(
            '<div class="quiz-question" data-correct-letter="%s">' % q["correct"]
        )
        parts.append(
            '<p class="quiz-text">Question %d. %s</p>'
            % (q["num"], mark_spoken(esc(q["text"])))
        )
        parts.append('<p class="pool-id">Pool question %s</p>' % esc(q["pool"]))
        parts.append('<div class="quiz-options">')
        for letter, text in q["options"]:
            parts.append(
                '<button type="button" class="quiz-option" data-correct="%s">'
                '<span class="opt-letter">%s.</span> %s</button>'
                % (
                    "true" if letter == q["correct"] else "false",
                    letter,
                    mark_spoken(esc(text)),
                )
            )
        parts.append("</div>")
        parts.append(
            '<p class="quiz-feedback" hidden role="status">'
            '<strong class="verdict"></strong> '
            '<span class="explanation">%s</span></p>'
            % mark_spoken(esc(q["explanation"]))
        )
        parts.append("</div>")
    if next_title is not None:
        parts.append(
            '<p class="next-link"><a href="#lesson-%d">Next lesson: Lesson %d — %s</a></p>'
            % (n + 1, n + 1, esc(next_title))
        )
    else:
        parts.append(
            '<p class="next-link"><a href="#contents">Back to the contents</a></p>'
        )
    parts.append("</section>")
    return "\n".join(parts)


BRAILLE_INTRO = (
    "Each lesson is also available as a Braille file (.brf) for use on a "
    "Braille display or notetaker. The files use contracted (grade 2) "
    "Unified English Braille, 40 cells per line. Each file holds one "
    "lesson, its quiz, and the answers at the end."
)


def braille_html():
    '''Links to the .brf files — emitted only when every lesson's file
    is staged.'''
    braille_dir = os.path.join(OUT_DIR, "braille")
    names = ["lesson-%02d.brf" % n for n in LESSON_NUMS]
    if not all(os.path.exists(os.path.join(braille_dir, name)) for name in names):
        return ""
    parts = []
    parts.append(
        '      <section class="braille" id="braille" aria-labelledby="braille-heading">'
    )
    parts.append('        <h2 id="braille-heading">Braille files</h2>')
    parts.append("        <p>%s</p>" % esc(BRAILLE_INTRO))
    parts.append("        <ol>")
    for n in LESSON_NUMS:
        parts.append(
            '          <li><a href="braille/lesson-%02d.brf">Lesson %d Braille file (.brf)</a></li>'
            % (n, n)
        )
    parts.append("        </ol>")
    pool_name = "Technician-Question-Pool-2026-2030.brf"
    if os.path.exists(os.path.join(braille_dir, pool_name)):
        parts.append(
            '        <p>The full question pool is here as a Braille file too: '
            '<a href="braille/%s">Technician Question Pool, 2026 to 2030 (.brf)</a>. '
            "It holds all 409 questions, with the correct answer after each question number.</p>"
            % pool_name
        )
    parts.append("      </section>")
    return "\n".join(parts)


PHONETIC_LETTERS = [
    ("A", "Alfa"), ("B", "Bravo"), ("C", "Charlie"), ("D", "Delta"),
    ("E", "Echo"), ("F", "Foxtrot"), ("G", "Golf"), ("H", "Hotel"),
    ("I", "India"), ("J", "Juliett"), ("K", "Kilo"), ("L", "Lima"),
    ("M", "Mike"), ("N", "November"), ("O", "Oscar"), ("P", "Papa"),
    ("Q", "Quebec"), ("R", "Romeo"), ("S", "Sierra"), ("T", "Tango"),
    ("U", "Uniform"), ("V", "Victor"), ("W", "Whiskey"), ("X", "X-ray"),
    ("Y", "Yankee"), ("Z", "Zulu"),
]

PHONETIC_NUMBERS = [
    ("0", "Zero"), ("1", "One"), ("2", "Two"), ("3", "Three"),
    ("4", "Four"), ("5", "Five"), ("6", "Six"), ("7", "Seven"),
    ("8", "Eight"), ("9", "Niner"),
]

PHONETIC_INTRO = [
    "Hams spell out words with special words for each letter and number. "
    "This is the phonetic alphabet. Say the word for the letter, not the "
    "letter itself. For example, to spell the call sign K1ABC, say Kilo 1 "
    "Alfa Bravo Charlie.",
    "Say 9 as Niner, not nine. Niner is clear on a noisy radio.",
]


def phonetic_html():
    '''The phonetic alphabet reference section.'''
    parts = []
    parts.append(
        '      <section class="reference" id="phonetic-alphabet" aria-labelledby="phonetic-alphabet-heading">'
    )
    parts.append(
        '        <h2 id="phonetic-alphabet-heading" class="readable" data-section="The phonetic alphabet">The phonetic alphabet</h2>'
    )
    parts.append(
        '        <button type="button" class="listen-btn" data-read="phonetic-alphabet" data-read-label="The phonetic alphabet">'
        "Listen to the phonetic alphabet</button>"
    )
    for para in PHONETIC_INTRO:
        parts.append(
            '        <p class="readable" data-section="The phonetic alphabet">%s</p>'
            % esc(para)
        )
    parts.append(
        '        <h3 class="readable" data-section="Letters">Letters</h3>'
    )
    parts.append("        <ul>")
    for letter, word in PHONETIC_LETTERS:
        parts.append(
            '          <li class="readable" data-section="Letters">%s — %s</li>'
            % (esc(letter), esc(word))
        )
    parts.append("        </ul>")
    parts.append(
        '        <h3 class="readable" data-section="Numbers">Numbers</h3>'
    )
    parts.append("        <ul>")
    for digit, word in PHONETIC_NUMBERS:
        parts.append(
            '          <li class="readable" data-section="Numbers">%s — %s</li>'
            % (esc(digit), esc(word))
        )
    parts.append("        </ul>")
    parts.append("      </section>")
    return "\n".join(parts)


SOFTWARE_TITLE = "Get the software — EchoLink and AllStarLink."
SOFTWARE_INTRO = (
    "You need an app or a program to use EchoLink and AllStarLink. Pick the "
    "one that fits your phone or computer. All of them need a valid amateur "
    "license. EchoLink and AllStarLink both ask for proof of license when "
    "you sign up."
)
# (text before the link, link text, link URL, text after the link). The
# EchoHam item has no link: it is found on the Mac App Store. All links
# were verified live 2026-11-16. BlueDV is deliberately not listed: it is
# a DMR/D-STAR/Fusion hotspot app, not an EchoLink/AllStarLink app.
SOFTWARE_ECHOLINK = [
    (
        "EchoLink for Windows is free. Get it at ",
        "echolink.org",
        "https://www.echolink.org/download.htm",
        ".",
    ),
    (
        "EchoLink is free on the ",
        "App Store",
        "https://apps.apple.com/us/app/echolink/id350688562",
        " for iPhone and iPad.",
    ),
    (
        "EchoLink is free on ",
        "Google Play",
        "https://play.google.com/store/apps/details?id=org.echolink.android",
        " for Android.",
    ),
    (
        "EchoLink Web runs in your browser. Nothing to install. Go to ",
        "webapp.echolink.org",
        "https://webapp.echolink.org",
        ".",
    ),
    (
        "EchoHam works with EchoLink on a Mac. Find it on the Mac App Store.",
        None,
        None,
        "",
    ),
]
SOFTWARE_ALLSTARLINK = [
    (
        "",
        "RepeaterPhone",
        "https://repeaterphone.com/",
        " costs $7.99 once. It talks to EchoLink and AllStarLink. It was "
        "built with help from VoiceOver users.",
    ),
    (
        "",
        "OpLine",
        "https://apps.apple.com/us/app/opline/id6763101817",
        " costs $6.99 once. It talks to AllStarLink only. It also runs on "
        "a Mac.",
    ),
    (
        "",
        "Transceive",
        "https://islandmagic.co/transceive/",
        " is for Mac. It connects to AllStarLink nodes, up to eight at "
        "once, and lets you manage your linked nodes. It costs 19 dollars "
        "and 99 cents, once.",
    ),
    (
        "",
        "DVSwitch Mobile",
        "https://play.google.com/store/apps/details?id=org.dvswitch",
        " is free. It talks to AllStarLink. It can also reach DMR and other "
        "digital modes.",
    ),
    (
        "",
        "DroidStar",
        "https://play.google.com/store/apps/details?id=org.dudetronics.droidstar",
        " is free. It talks to AllStarLink and to DMR, D-STAR, and more.",
    ),
    (
        "You can run your own AllStarLink node on a Raspberry Pi or a "
        "computer. The software is free at ",
        "allstarlink.org",
        "https://www.allstarlink.org",
        ". You do not need your own node to use the apps above.",
    ),
]
SOFTWARE_NOTE = (
    "RepeaterPhone and OpLine do not run on Android. Android users pick "
    "DVSwitch Mobile or DroidStar."
)
SOFTWARE_LINKS = [
    "https://www.echolink.org/download.htm",
    "https://apps.apple.com/us/app/echolink/id350688562",
    "https://play.google.com/store/apps/details?id=org.echolink.android",
    "https://webapp.echolink.org",
    "https://repeaterphone.com/",
    "https://apps.apple.com/us/app/opline/id6763101817",
    "https://islandmagic.co/transceive/",
    "https://play.google.com/store/apps/details?id=org.dvswitch",
    "https://play.google.com/store/apps/details?id=org.dudetronics.droidstar",
    "https://www.allstarlink.org",
    "https://www.pa7lim.nl/peanut/",
]
# Digital voice networks (D-STAR/DMR/Fusion/M17) — a separate heading inside
# the section, since these are different networks from EchoLink/AllStarLink.
# Peanut is free, for licensed hams only, and needs a free Peanut code from
# the Peanut site. Android and Windows confirmed; the Apple beta is
# unconfirmed (its stated end date passed), so no iPhone/iPad claim is made.
SOFTWARE_DIGITAL_VOICE = [
    (
        "Peanut is free. It talks to D-STAR, DMR, Fusion, and M17 rooms from "
        "your phone or computer. You need a Peanut code, free from the ",
        "Peanut site",
        "https://www.pa7lim.nl/peanut/",
        ", and a license.",
    ),
]


def software_html():
    """The "Get the software" reference section (EchoLink, AllStarLink,
    and digital voice)."""

    def item_html(item, section):
        before, link_text, href, after = item
        if link_text is None:
            body = esc(before)
        else:
            body = '%s<a href="%s">%s</a>%s' % (
                esc(before),
                esc(href),
                esc(link_text),
                esc(after),
            )
        return (
            '          <li class="readable" data-section="%s">%s</li>'
            % (esc(section), body)
        )

    parts = []
    parts.append(
        '      <section class="reference" id="get-the-software" aria-labelledby="get-the-software-heading">'
    )
    parts.append(
        '        <h2 id="get-the-software-heading" class="readable" data-section="Get the software">%s</h2>'
        % esc(SOFTWARE_TITLE)
    )
    parts.append(
        '        <button type="button" class="listen-btn" data-read="get-the-software" data-read-label="Get the software">'
        "Listen to Get the software</button>"
    )
    parts.append(
        '        <p class="readable" data-section="Get the software">%s</p>'
        % esc(SOFTWARE_INTRO)
    )
    parts.append('        <h3 class="readable" data-section="EchoLink">EchoLink</h3>')
    parts.append("        <ul>")
    for item in SOFTWARE_ECHOLINK:
        parts.append(item_html(item, "EchoLink"))
    parts.append("        </ul>")
    parts.append('        <h3 class="readable" data-section="AllStarLink">AllStarLink</h3>')
    parts.append("        <ul>")
    for item in SOFTWARE_ALLSTARLINK:
        parts.append(item_html(item, "AllStarLink"))
    parts.append("        </ul>")
    parts.append(
        '        <p class="readable" data-section="Get the software">%s</p>'
        % esc(SOFTWARE_NOTE)
    )
    parts.append('        <h3 class="readable" data-section="Digital voice">Digital voice</h3>')
    parts.append("        <ul>")
    for item in SOFTWARE_DIGITAL_VOICE:
        parts.append(item_html(item, "Digital voice"))
    parts.append("        </ul>")
    parts.append("      </section>")
    return "\n".join(parts)


def build_page(lessons, quizzes):
    out = []
    out.append("<!doctype html>")
    out.append('<html lang="en">')
    out.append("  <head>")
    out.append('    <meta charset="utf-8" />')
    out.append(
        '    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />'
    )
    out.append('    <meta name="color-scheme" content="dark" />')
    out.append('    <link rel="icon" href="data:," />')
    # Apply a stored light/dark choice before first paint, so the page
    # never flashes the wrong theme. Same pattern as the grid locator.
    out.append(
        '    <script>try{var t=localStorage.getItem("technician-class-theme");'
        'if(t==="light"||t==="dark"){document.documentElement.setAttribute'
        '("data-theme",t);}}catch(e){}</script>'
    )
    out.append("    <title>Technician License Class</title>")
    out.append("    <style>" + CSS + "    </style>")
    out.append("  </head>")
    out.append("  <body>")
    out.append(
        '    <a class="skip-link" href="#contents">Skip to the course contents</a>'
    )
    out.append('    <header class="wrap">')
    out.append("      <h1>Technician License Class</h1>")
    out.append(
        '      <p><button type="button" class="theme-toggle" id="theme-toggle">'
        "Switch to light mode</button></p>"
    )
    out.append(
        '      <p class="theme-note">Your light or dark choice is saved on '
        "this device only. It is never sent anywhere.</p>"
    )
    for para in intro_paragraphs(len(lessons)):
        out.append('      <p class="intro">%s</p>' % esc(para))
    out.append(
        '      <a class="back-link" href="%s">Back to Visually Inconvenienced Hams on Facebook</a>'
        % GROUP_URL
    )
    out.append("    </header>")
    out.append('    <main class="wrap">')
    out.append(
        '      <div class="listen-controls" role="region" aria-label="Reading controls">'
    )
    out.append('        <div class="listen-row">')
    out.append(
        '          <button type="button" id="pause-btn" disabled>Pause</button>'
    )
    out.append('          <button type="button" id="stop-btn" disabled>Stop</button>')
    out.append('          <label for="rate-select">Reading speed:</label>')
    out.append('          <select id="rate-select">')
    out.append('            <option value="0.8">Slower</option>')
    out.append('            <option value="1" selected>Normal</option>')
    out.append('            <option value="1.25">Faster</option>')
    out.append("          </select>")
    out.append("        </div>")
    out.append(
        '        <p class="status" id="read-status" role="status">Press a lesson\u2019s '
        "\u201cListen to this lesson\u201d button, or a quiz\u2019s \u201cListen to this "
        "quiz\u201d button, to hear it read aloud.</p>"
    )
    out.append("      </div>")
    out.append('      <nav id="contents" aria-label="Course contents">')
    out.append("        <h2>Contents</h2>")
    out.append("        <ol>")
    for lesson in lessons:
        out.append(
            '          <li><a href="#lesson-%d">Lesson %d: %s</a></li>'
            % (lesson["num"], lesson["num"], esc(lesson["title"]))
        )
    out.append(
        '          <li><a href="#phonetic-alphabet">The phonetic alphabet</a></li>'
    )
    out.append(
        '          <li><a href="#get-the-software">Get the software — EchoLink and AllStarLink.</a></li>'
    )
    out.append("        </ol>")
    out.append("      </nav>")
    for lesson in lessons:
        out.append(lesson_html(lesson))
        n = lesson["num"]
        next_title = (
            lessons[n]["title"] if n < len(lessons) else None
        )  # lessons list is 0-indexed; the last lesson has no next lesson
        out.append(quiz_html(n, quizzes[n], next_title, lesson))
    out.append(phonetic_html())
    out.append(software_html())
    out.append(braille_html())
    out.append("    </main>")
    out.append('    <footer class="wrap">')
    out.append('      <p class="about">%s</p>' % esc(ABOUT))
    out.append(
        '      <a class="back-link" href="%s">Back to Visually Inconvenienced Hams on Facebook</a>'
        % GROUP_URL
    )
    out.append("    </footer>")
    out.append("")
    out.append("<script>" + JS + "</script>")
    out.append("  </body>")
    out.append("</html>")
    out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}


def check_tag_balance(page, errors):
    from html.parser import HTMLParser

    class Checker(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.stack = []
            self.problems = []

        def handle_starttag(self, tag, attrs):
            if tag not in VOID_ELEMENTS:
                self.stack.append((tag, self.getpos()))

        def handle_startendtag(self, tag, attrs):
            pass

        def handle_endtag(self, tag):
            if tag in VOID_ELEMENTS:
                return
            if not self.stack:
                self.problems.append("stray </%s> at %s" % (tag, self.getpos()))
                return
            open_tag, pos = self.stack.pop()
            if open_tag != tag:
                self.problems.append(
                    "mismatch: <%s> opened at %s closed by </%s> at %s"
                    % (open_tag, pos, tag, self.getpos())
                )

    checker = Checker()
    checker.feed(page)
    checker.close()
    for problem in checker.problems:
        errors.append("tag balance: " + problem)
    for tag, pos in checker.stack:
        errors.append("tag balance: <%s> opened at %s never closed" % (tag, pos))


def readable_texts(section_html):
    """Text of every class="readable" element, in order, tags stripped."""
    # Remove the visually hidden ratio spellings first: their words are
    # not in the source prose, while the visible ratio is.
    section_html = re.sub(r'<span class="sr-only">.*?</span>', "", section_html)
    found = re.findall(
        r'<(?:h2|h3|h4|p|li)[^>]*class="readable"[^>]*>(.*?)</(?:h2|h3|h4|p|li)>',
        section_html,
        flags=re.DOTALL,
    )
    texts = []
    for raw in found:
        no_tags = re.sub(r"<[^>]+>", "", raw)
        texts.append(re.sub(r"\s+", " ", html.unescape(no_tags)).strip())
    return texts


def expected_readable_texts(lesson):
    """Source lines for one lesson, in the order the page renders them."""
    expected = ["Lesson %d: %s" % (lesson["num"], lesson["title"])]
    for kind, val in lesson["intro"]:
        if kind == "ul":
            expected.extend(val)
        else:
            expected.append(val)
    for name in SECTIONS:
        expected.append(name)
        for kind, val in lesson["sections"][name]:
            if kind == "ul":
                expected.extend(val)
            else:
                expected.append(val)
    return [re.sub(r"\s+", " ", t).strip() for t in expected]


def verify_page(path, lessons, quizzes):
    with open(path, encoding="utf-8") as f:
        page = f.read()
    errors = []

    def check(cond, msg):
        if not cond:
            errors.append(msg)
        return cond

    # Every count derives from the lesson and quiz files: n_lessons
    # lessons, one lesson + one quiz Listen button per lesson, plus one
    # Listen button per reference section (phonetic, software).
    # Question counts vary by lesson (see parse_quiz), so they are
    # summed from the parsed quizzes, not derived from n_lessons.
    n_lessons = len(lessons)
    n_questions = sum(len(qs) for qs in quizzes.values())
    n_ref = page.count('<section class="reference"')
    check(
        page.count('<section class="lesson"') == n_lessons,
        "lesson sections != %d" % n_lessons,
    )
    check(
        page.count('<section class="quiz"') == n_lessons,
        "quiz sections != %d" % n_lessons,
    )
    check(
        page.count('class="quiz-question"') == n_questions,
        "quiz questions != %d" % n_questions,
    )
    check(
        page.count('class="quiz-option"') == 4 * n_questions,
        "quiz options != %d" % (4 * n_questions),
    )
    check(
        page.count('class="listen-btn"') == 2 * n_lessons + n_ref,
        "listen buttons != %d" % (2 * n_lessons + n_ref),
    )
    check(
        page.count('data-lesson="') == n_lessons,
        "lesson listen buttons != %d" % n_lessons,
    )
    check(
        page.count('data-quiz="') == n_lessons,
        "quiz listen buttons != %d" % n_lessons,
    )
    check(
        page.count('data-read="phonetic-alphabet"') == 1,
        "phonetic listen button != 1",
    )
    check(
        page.count('data-correct="true"') == n_questions,
        "correct options != %d" % n_questions,
    )
    check(page.count('class="back-link"') == 2, "back-links != 2")
    check(page.count('id="pause-btn"') == 1, "pause button != 1")
    check(page.count('id="stop-btn"') == 1, "stop button != 1")
    check(page.count('id="rate-select"') == 1, "rate select != 1")

    imgs = re.findall(r'<img src="diagrams/([^"]+)" alt="([^"]*)"', page)
    # Each diagram appears twice: once in its lesson, once repeated in
    # that lesson's quiz section.
    expected_refs = 2 * sum(len(lesson["diagrams"]) for lesson in lessons)
    check(
        len(imgs) == expected_refs,
        "img references != %d (got %d)" % (expected_refs, len(imgs)),
    )
    unique_diagrams = {d for lesson in lessons for d in lesson["diagrams"]}
    check(
        len(set(src for src, _alt in imgs)) == len(unique_diagrams),
        "unique diagrams != %d" % len(unique_diagrams),
    )
    check(all(alt.strip() for _src, alt in imgs), "empty alt text found")

    check("Module 1" not in page, '"Module 1" leaked into the page')
    check("Module 2" not in page, '"Module 2" leaked into the page')
    check(
        page.count("Visually Inconvenienced Hams") == 2,
        '"Visually Inconvenienced Hams" count != 2 (the two back-links)',
    )
    for stale in (24, 25):
        if stale != n_lessons:
            check(
                "%d lessons" % stale not in page,
                'stale "%d lessons" text present' % stale,
            )
    check("proof of concept" not in page.lower(), '"proof of concept" leaked')
    check(
        re.search(r"\d{1,2}:\d{2}\s*([APap]\.?[Mm]\.?)", page) is None,
        "12-hour time found",
    )
    check("<title>Technician License Class</title>" in page, "<title> wrong")
    check("<h1>Technician License Class</h1>" in page, "<h1> wrong")

    # Contents nav: one link per lesson, in order.
    nav_links = re.findall(r'<a href="#lesson-(\d+)">Lesson (\d+): ([^<]+)</a>', page)
    check(
        len(nav_links) == n_lessons,
        "contents links != %d (got %d)" % (n_lessons, len(nav_links)),
    )
    for i, (href_n, text_n, title) in enumerate(nav_links, start=1):
        check(
            int(href_n) == i and int(text_n) == i and title == lessons[i - 1]["title"],
            "contents link %d wrong: %r" % (i, (href_n, text_n, title)),
        )

    # Exact prose per lesson + alt texts per lesson.
    for lesson in lessons:
        n = lesson["num"]
        m = re.search(
            r'<section class="lesson" id="lesson-%d".*?</section>' % n,
            page,
            flags=re.DOTALL,
        )
        check(m is not None, "lesson %d section not found" % n)
        if not m:
            continue
        actual = readable_texts(m.group(0))
        expected = expected_readable_texts(lesson)
        check(
            actual == expected,
            "lesson %d prose mismatch (%d readable blocks vs %d expected)"
            % (n, len(actual), len(expected)),
        )
        if actual != expected:
            for j, (a, e) in enumerate(zip(actual, expected)):
                if a != e:
                    errors.append(
                        "lesson %d first diff at block %d:\n  page:   %r\n  source: %r"
                        % (n, j, a[:160], e[:160])
                    )
                    break
        section_imgs = re.findall(
            r'<img src="diagrams/([^"]+)" alt="([^"]*)"', m.group(0)
        )
        expected_imgs = sorted(
            (fname, lesson["alts"][fname]) for fname in lesson["diagrams"]
        )
        check(
            sorted((s, html.unescape(a)) for s, a in section_imgs) == expected_imgs,
            "lesson %d diagrams/alt mismatch: %r vs %r"
            % (n, section_imgs, expected_imgs),
        )
        qm = re.search(
            r'<section class="quiz" id="quiz-%d".*?</section>' % n,
            page,
            flags=re.DOTALL,
        )
        check(qm is not None, "quiz %d section not found" % n)
        if qm:
            quiz_imgs = re.findall(
                r'<img src="diagrams/([^"]+)" alt="([^"]*)"', qm.group(0)
            )
            check(
                sorted((s, html.unescape(a)) for s, a in quiz_imgs) == expected_imgs,
                "quiz %d repeated diagrams mismatch: %r vs %r"
                % (n, quiz_imgs, expected_imgs),
            )
            check(
                'data-quiz="%d"' % n in qm.group(0),
                "quiz %d listen button missing" % n,
            )
            check(
                '<h2 id="quiz-%d-heading" tabindex="-1">' % n in qm.group(0),
                "quiz %d heading missing tabindex" % n,
            )

    # Quiz data: correct letters in order, verbatim questions/options/explanations.
    # The verbatim checks run against the ratio-unwrapped page, so "1.2:1"
    # reads as "1.2:1" again instead of its two spans.
    plain = re.sub(r'<span class="sr-only">.*?</span>', "", page)
    plain = re.sub(r'<span aria-hidden="true">(.*?)</span>', r"\1", plain)
    letters = re.findall(r'<div class="quiz-question" data-correct-letter="([A-D])">', page)
    expected_letters = [q["correct"] for n in LESSON_NUMS for q in quizzes[n]]
    check(letters == expected_letters, "quiz correct letters mismatch")
    for n in LESSON_NUMS:
        for q in quizzes[n]:
            check(esc(q["text"]) in plain, "quiz %d Q%d text missing" % (n, q["num"]))
            for letter, text in q["options"]:
                check(
                    esc(text) in plain,
                    "quiz %d Q%d option %s missing" % (n, q["num"], letter),
                )
            check(
                esc(q["explanation"]) in plain,
                "quiz %d Q%d explanation missing" % (n, q["num"]),
            )

    # Landmarks: one banner, one main, one contentinfo; every named section
    # points at a heading that exists; heading levels never skip.
    check(page.count("<header") == 1, "header (banner) != 1")
    check(page.count("<main") == 1, "main != 1")
    check(page.count("<footer") == 1, "footer (contentinfo) != 1")
    check(page.count("<h1>") == 1, "h1 != 1")
    check("<nav " in page and 'id="contents"' in page, "contents nav missing")
    for m in re.finditer(r'<section[^>]*aria-labelledby="([^"]+)"', page):
        check(
            'id="%s"' % m.group(1) in page,
            "section labelledby %s has no such heading" % m.group(1),
        )
    levels = [int(d) for d in re.findall(r"<h([1-4])[\s>]", page)]
    check(levels and levels[0] == 1, "first heading is not h1")
    for prev, cur in zip(levels, levels[1:]):
        check(cur <= prev + 1, "heading level skips from h%d to h%d" % (prev, cur))

    # Speech prep + end-of-lesson cue are in the script.
    check("common abbreviation" in page, '"common abbreviation" missing from script')
    check("End of lesson" in page, '"End of lesson" cue missing from script')
    check("prepareSpeech" in page, "prepareSpeech missing from script")

    # Braille links, when the section is present: one per lesson, files on disk.
    braille_links = re.findall(r'href="braille/lesson-(\d\d)\.brf"', page)
    if braille_links:
        check(
            len(braille_links) == len(LESSON_NUMS),
            "braille links != %d" % len(LESSON_NUMS),
        )
        for name in ["lesson-%02d.brf" % n for n in LESSON_NUMS]:
            check(
                os.path.exists(os.path.join(OUT_DIR, "braille", name)),
                "braille file missing from disk: " + name,
            )

    # Phonetic alphabet reference section.
    check('id="phonetic-alphabet"' in page, "phonetic section missing")
    check(
        page.count('href="#phonetic-alphabet"') == 3,
        "phonetic links != 3 (contents + lesson 3 + lesson 6)",
    )
    for letter, word in PHONETIC_LETTERS + PHONETIC_NUMBERS:
        check(
            "%s — %s" % (letter, word) in page,
            "phonetic entry missing: %s %s" % (letter, word),
        )

    # SWR ratios, formulas, and fractions: every one in the lesson
    # bodies and quiz content (stems, options, explanations) is wrapped
    # once; each hidden spelling matches its visible text; times are
    # never wrapped. Alt text is not passed through mark_spoken, so it
    # is not counted.
    def _spoken_counts(text):
        n_frac = sum(
            1 for m in FRACTION_RE.finditer(text) if fraction_words(m) is not None
        )
        return (
            len(RATIO_RE.findall(text)),
            len(FORMULA_RE.findall(text)),
            n_frac,
        )

    expected_ratios = expected_formulas = expected_fractions = 0
    for lesson in lessons:
        r, f, fr = _spoken_counts(" ".join(lesson["source_lines"]))
        expected_ratios += r
        expected_formulas += f
        expected_fractions += fr
    for qs in quizzes.values():
        for q in qs:
            for text in [q["text"]] + [opt for _letter, opt in q["options"]] + [
                q["explanation"]
            ]:
                r, f, fr = _spoken_counts(text)
                expected_ratios += r
                expected_formulas += f
                expected_fractions += fr
    expected_pairs = expected_ratios + expected_formulas + expected_fractions
    spoken_pairs = re.findall(
        r'<span aria-hidden="true">([^<]+)</span><span class="sr-only">([^<]+)</span>',
        page,
    )
    check(
        len(spoken_pairs) == expected_pairs,
        "spoken-form spans != %d (got %d: %d ratios + %d formulas + %d fractions expected)"
        % (
            expected_pairs,
            len(spoken_pairs),
            expected_ratios,
            expected_formulas,
            expected_fractions,
        ),
    )
    for visible, spoken in spoken_pairs:
        m = RATIO_RE.fullmatch(visible)
        if m:
            check(
                spoken == ratio_words(m.group(1)),
                "ratio spelling wrong for %s: %r" % (visible, spoken),
            )
            continue
        m = FORMULA_RE.fullmatch(visible)
        if m:
            check(
                spoken == formula_words(m),
                "formula spelling wrong for %s: %r" % (visible, spoken),
            )
            continue
        m = FRACTION_RE.fullmatch(visible)
        if m:
            check(
                spoken == fraction_words(m),
                "fraction spelling wrong for %s: %r" % (visible, spoken),
            )
            continue
        check(False, "wrapped non-ratio/formula/fraction: %r" % visible)
    check(
        '<span aria-hidden="true">19:00</span>' not in page,
        "19:00 wrapped as a ratio",
    )
    check(
        '<span aria-hidden="true">18:30</span>' not in page,
        "18:30 wrapped as a ratio",
    )
    check(
        '<span aria-hidden="true">50:50</span>' not in page,
        "50:50 wrapped as a ratio",
    )
    check(page.count("19:00") == 2, "19:00 count != 2")
    check(page.count("18:30") == 1, "18:30 count != 1")

    # Sticky-bar fix: anchor jumps clear the Reading controls bar.
    check("scroll-padding-top: 10rem" in page, "scroll-padding-top 10rem missing")
    check("scroll-padding-top: 22rem" in page, "scroll-padding-top 22rem missing")

    # "Get the software" reference section: present, linked, all 11 links.
    check('id="get-the-software"' in page, "software section missing")
    check(
        page.count('data-read="get-the-software"') == 1,
        "software listen button != 1",
    )
    for href in SOFTWARE_LINKS:
        check('href="%s"' % href in page, "software link missing: %s" % href)
    check("BlueDV" not in page, "BlueDV must not appear on the page")

    # Every in-page jump target exists.
    for target in sorted(set(re.findall(r'href="#([^"]+)"', page))):
        check('id="%s"' % target in page, "jump target missing: #%s" % target)

    check_tag_balance(page, errors)

    if errors:
        print("VERIFICATION FAILED (%d problems):" % len(errors))
        for err in errors:
            print("  - " + err)
        return False
    print(
        "VERIFICATION PASSED: %d lessons, %d quizzes, %d questions, %d options,"
        % (n_lessons, n_lessons, n_questions, 4 * n_questions)
    )
    print(
        "  %d listen buttons (%d lesson + %d quiz + phonetic + software), %d diagram references "
        "(%d unique PNGs, each repeated in its quiz), exact prose everywhere,"
        % (
            2 * n_lessons + n_ref,
            n_lessons,
            n_lessons,
            2 * sum(len(lesson["diagrams"]) for lesson in lessons),
            len({d for lesson in lessons for d in lesson["diagrams"]}),
        )
    )
    print("  landmarks (header/main/footer/nav/regions) present, heading levels clean,")
    print("  no Module wording, no 12-hour times, title clean, tags balanced.")
    return True


def main():
    lessons = [parse_lesson(n) for n in LESSON_NUMS]
    quizzes = {n: parse_quiz(n) for n in LESSON_NUMS}
    page = build_page(lessons, quizzes)
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    diag_out = os.path.join(OUT_DIR, "diagrams")
    os.makedirs(diag_out, exist_ok=True)
    unique_diagrams = sorted({d for lesson in lessons for d in lesson["diagrams"]})
    for fname in unique_diagrams:
        shutil.copyfile(
            os.path.join(SRC, "diagrams", fname), os.path.join(diag_out, fname)
        )
    print("wrote %s (%d bytes)" % (out_path, os.path.getsize(out_path)))
    print("diagrams copied: %d PNGs" % len(unique_diagrams))
    print()
    print("Diagram placements (anchor paragraph starts):")
    for lesson in lessons:
        if not lesson["diagrams"]:
            continue
        placements = compute_placements(lesson)
        blocks = lesson["sections"]["The idea in plain words"]
        for idx in sorted(placements):
            for fname in placements[idx]:
                anchor = blocks[idx][1][:70]
                print("  L%-2d %-24s after: %r" % (lesson["num"], fname, anchor))
    print()
    ok = verify_page(out_path, lessons, quizzes)
    # Dump the quiz answer map for a human cross-check against the manifest.
    print()
    print("Quiz answer map (lesson: correct letters in question order):")
    print(
        "  "
        + ", ".join(
            "L%d:%s" % (n, "".join(q["correct"] for q in quizzes[n]))
            for n in LESSON_NUMS
        )
    )
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
