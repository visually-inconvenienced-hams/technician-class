#!/usr/bin/env python3
"""Generate one contracted-UEB .brf file per Technician lesson.

Reuses build_page.py's parse_lesson/parse_quiz/compute_placements, so the
.brf files always match the page's approved prose. Each file holds one
lesson (with "Diagram: <alt text>" paragraphs where the diagrams sit),
its quiz, and the answers after a page break.

Output: braille/lesson-NN.brf, 40 cells per line, 25 lines per page,
form feed between pages. Tables: en-us-brf.dis + en-ueb-g2.ctb
(standard .brf ASCII Braille, contracted grade 2 UEB).

Usage: python3 build_braille.py [lesson-number ...]
  No arguments: build all lessons. One or more numbers: build just those
  (e.g. "python3 build_braille.py 10" for the proof of concept).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_page  # noqa: E402

import louis  # noqa: E402

TABLES = ["en-us-brf.dis", "en-ueb-g2.ctb"]
WIDTH = 40
LINES_PER_PAGE = 25
OUT_DIR = os.path.join(build_page.OUT_DIR, "braille")
PAGE_BREAK = "\f"
# Single-capital-letter list (lesson 8 ionosphere alt text) that must be
# translated piece by piece — see lesson_paragraphs.
LIST_SPLIT = "D, E, F1, and F2"


def wrap(braille, width=WIDTH):
    """Word-wrap one translated paragraph to lines of at most `width` cells."""
    words = braille.split(" ")
    lines = []
    current = ""
    for word in words:
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= width:
            current += " " + word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    # A single word longer than a line (should not happen in lesson prose)
    # is hard-split rather than allowed to overflow.
    split = []
    for line in lines:
        while len(line) > width:
            split.append(line[:width])
            line = line[width:]
        split.append(line)
    return split


def block_texts(blocks):
    """Blocks -> plain-text paragraphs (lists become one line per item)."""
    paragraphs = []
    for kind, val in blocks:
        if kind in ("p", "h4"):
            paragraphs.append(val)
        elif kind == "ul":
            for item in val:
                paragraphs.append(item)
    return paragraphs


def lesson_paragraphs(n):
    """The full plain text of one lesson's .brf, paragraph by paragraph.

    "" (empty string) marks a blank line; PAGE_BREAK marks the forced
    page break before the answers.
    """
    lesson = build_page.parse_lesson(n)
    quiz = build_page.parse_quiz(n)
    placements = build_page.compute_placements(lesson)
    paragraphs = []
    paragraphs.append("Lesson %d: %s" % (n, lesson["title"]))
    paragraphs.append("")
    paragraphs.extend(block_texts(lesson["intro"]))
    paragraphs.append("")
    for name in build_page.SECTIONS:
        blocks = lesson["sections"][name]
        paragraphs.append(name)
        paragraphs.append("")
        for i, block in enumerate(blocks):
            paragraphs.extend(block_texts([block]))
            if name == "The idea in plain words":
                for fname in placements.get(i, []):
                    diagram_para = "Diagram: " + lesson["alts"][fname]
                    if LIST_SPLIT in diagram_para:
                        # Lesson 8's ionosphere alt text lists single
                        # capital layers ("D, E, F1, and F2"). liblouis
                        # mangles the list when translated as one string
                        # (caps-passage handling drops capitals); each
                        # piece translated separately is correct and the
                        # join round-trips exactly.
                        before, _sep, after = diagram_para.partition(LIST_SPLIT)
                        paragraphs.append(
                            (
                                "pieces",
                                [
                                    before.strip(),
                                    "D,",
                                    "E,",
                                    "F1,",
                                    "and",
                                    "F2" + after,
                                ],
                            )
                        )
                    else:
                        paragraphs.append(diagram_para)
        paragraphs.append("")
    paragraphs.append("Check yourself — Lesson %d" % n)
    paragraphs.append("")
    for q in quiz:
        paragraphs.append("Question %d. %s" % (q["num"], q["text"]))
        for letter, text in q["options"]:
            # A tuple, not a string: build_brf translates the label and
            # the text separately (liblouis mangles a capital letter +
            # period directly before a formula — see build_brf).
            paragraphs.append(("option", letter, text))
        paragraphs.append("")
    paragraphs.append(PAGE_BREAK)
    paragraphs.append("Answers for lesson %d" % n)
    paragraphs.append("")
    for q in quiz:
        # A tuple, not a string: build_brf translates the two pieces
        # separately — a capital letter + period directly before an
        # all-caps word ("D. PL-259") loses the capitals, the same
        # liblouis quirk as the quiz options above.
        paragraphs.append(
            (
                "pieces",
                [
                    "Question %d. The right answer is %s."
                    % (q["num"], q["correct"]),
                    q["explanation"],
                ],
            )
        )
        paragraphs.append("")
    return paragraphs


def prepare_text(text):
    """Braille typography tweaks, applied before translation.

    liblouis's UEB table mishandles a spaced slash inside a formula:
    "I = E / R" loses the capitals on E and R and gains a spurious
    mark, while the unspaced form "I = E/R" translates and round-trips
    exactly. A solidus without spaces is normal Braille practice for
    division. Only the 10 formula divisions use a spaced slash; "U/V
    mode" and "operator/primary" are unspaced already and untouched.
    The lesson prose on the page is unchanged.
    """
    return text.replace(" / ", "/")


def brf_from_paragraphs(paragraphs):
    """Translate any paragraph list to .brf lines; returns (lines, plain_text).

    Paragraph forms (shared by the lesson and question-pool builders):
      ""             blank line
      PAGE_BREAK     forced page break
      str            plain paragraph, translated as one string
      ("pieces", [..])  multi-piece paragraph, each piece translated
                        separately and joined with spaces
      ("option", letter, text)   quiz option: label and text translated
                        separately (liblouis mangles a capital letter +
                        period directly before a formula — see below)
      ("pool_option", letter, text, is_correct)  pool option: as "option"
                        (is_correct is retained but unused; the correct
                        answer is shown after the question number)
    """
    lines = []
    plain_parts = []
    for para in paragraphs:
        if para == PAGE_BREAK:
            lines.append(PAGE_BREAK)
            continue
        if para == "":
            lines.append("")
            plain_parts.append("")
            continue
        if isinstance(para, tuple):
            if para[0] == "pieces":
                # Multi-piece paragraph (lesson 8 layer list): translate
                # each piece separately and join with spaces.
                parts = [prepare_text(p) for p in para[1]]
                joined = " ".join(
                    louis.translateString(TABLES, part) for part in parts
                )
                lines.extend(wrap(joined))
                plain_parts.append(" ".join(parts))
                continue
            if para[0] == "pool_option":
                _kind, letter, text, _is_correct = para
                text = prepare_text(text)
                joined = (
                    louis.translateString(TABLES, letter + ".")
                    + " "
                    + louis.translateString(TABLES, text)
                )
                lines.extend(wrap(joined))
                plain_parts.append("%s. %s" % (letter, text))
                continue
            # Quiz option: translate the label and the text separately.
            # liblouis's UEB table mangles a capital letter + period
            # directly before a formula ("A. I = E x R" loses the
            # capitals on I and E and gains a spurious mark); translated
            # separately, both pieces are correct and the join with a
            # space round-trips exactly.
            _kind, letter, text = para
            text = prepare_text(text)
            joined = (
                louis.translateString(TABLES, letter + ".")
                + " "
                + louis.translateString(TABLES, text)
            )
            lines.extend(wrap(joined))
            plain_parts.append("%s. %s" % (letter, text))
            continue
        text = prepare_text(para)
        lines.extend(wrap(louis.translateString(TABLES, text)))
        plain_parts.append(text)
    # Paginate: a form feed after every 25 lines, plus the forced break.
    out = []
    on_page = 0
    for line in lines:
        if line == PAGE_BREAK:
            if on_page:
                out.append(PAGE_BREAK)
                on_page = 0
            continue
        out.append(line)
        on_page += 1
        if on_page == LINES_PER_PAGE:
            out.append(PAGE_BREAK)
            on_page = 0
    # No trailing form feed.
    while out and out[-1] == PAGE_BREAK:
        out.pop()
    plain = "\n".join(plain_parts)
    return out, plain


def build_brf(n):
    """Translate lesson n to .brf lines; returns (lines, plain_text)."""
    return brf_from_paragraphs(lesson_paragraphs(n))


def validate_brf(label, lines, plain):
    """Validate one .brf file; returns a list of problems (empty = valid).

    `label` names the file in problem messages, e.g. "lesson 10" or
    "question pool".
    """
    problems = []
    content = [ln for ln in lines if ln != PAGE_BREAK]
    for ln in content:
        if len(ln) > WIDTH:
            problems.append("%s: line over %d cells: %r" % (label, WIDTH, ln))
        for ch in ln:
            if not (0x20 <= ord(ch) <= 0x5F):
                problems.append(
                    "%s: char outside Braille range: %r" % (label, ch)
                )
                break
    joined = " ".join(content)
    if "!" not in joined:
        problems.append("%s: no contracted 'the' (!) found" % label)
    if "&" not in joined:
        problems.append("%s: no contracted 'and' (&) found" % label)
    # Round-trip: back-translate and compare against the assembled text.
    # liblouis normalizes curly quotes/apostrophes to straight ones, so
    # the comparison normalizes the same way. Lines are joined with
    # spaces, not newlines: the back-translator glues a line-final
    # contraction to the next line's first word across a newline
    # ("&\nOHMS" back-translates as garbage), while a space is the true
    # word boundary the wrap broke at.
    back = louis.backTranslateString(TABLES, " ".join(content))
    norm_back = " ".join(back.split())
    norm_plain = " ".join(
        plain.replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .split()
    )
    # Known liblouis back-translation artifacts, each verified forward-
    # correct by hand. The plain text is the authority: a normalization
    # only ever repairs the back-translation toward it, and the full
    # comparison below still has to match.
    # 1. "AC": forward Braille is ;,,AC — grade-1 + caps-word. The
    #    grade-1 mark is REQUIRED (bare ,,AC reads as "according", the
    #    UEB contraction for it); the back-translator renders it "Ac".
    assert not re.search(r"\bAc\b", norm_plain), "plain text has 'Ac'"
    norm_back = re.sub(r"\bAc\b", "AC", norm_back)
    # 2. "FCC's": forward Braille reads the possessive s as capital
    #    (,,FCC'S); the meaning is clear in context and no better
    #    Braille form exists (terminator forms back-translate worse).
    norm_back = norm_back.replace("FCC'S", "FCC's")
    # 3. Dotted initials ("U.S.", "p.m.", "a.m."): forward Braille is
    #    correct, unambiguous UEB (e.g. "p.m." -> P4M4, p, period, m,
    #    period). The back-translator reads the second initial as a
    #    whole-word contraction — "U.So.", "p.more.", "a.more.".
    #    (Isolated "S."/"m." get a grade-1 mark and round-trip; the
    #    fault is only the second initial in a dotted pair.)
    assert "U.So." not in norm_plain, "plain text has 'U.So.'"
    assert "p.more." not in norm_plain, "plain text has 'p.more.'"
    assert "a.more." not in norm_plain, "plain text has 'a.more.'"
    norm_back = norm_back.replace("U.So.", "U.S.")
    norm_back = norm_back.replace("p.more.", "p.m.")
    norm_back = norm_back.replace("a.more.", "a.m.")
    # 4. ");" (close paren + semicolon): forward Braille is ">2 —
    #    close paren, then the semicolon cell — correct, unambiguous
    #    UEB. The back-translator reads the semicolon cell as the
    #    "be" groupsign and renders it ")be". (A semicolon after a
    #    letter round-trips fine; only the post-paren case fails.)
    assert ")be" not in norm_plain, "plain text has ')be'"
    norm_back = norm_back.replace(")be", ");")
    # 5. Single-capital formulas with + or - ("R = E + I", "R = E - I",
    #    quiz 10, pool question T5D03): forward Braille is a caps
    #    passage (,,, opens, ,' closes) — correct, unambiguous UEB, a
    #    reader reads capitals throughout. The back-translator ignores
    #    the passage and renders the letters after the first lowercase
    #    ("R = e + i"). The x and / forms use individual capital signs
    #    and round-trip. (The sibling formulas "I = E + R" / "I = E - R"
    #    fail the same way in isolation but produced no caps passage in
    #    this file's joined translation, so they need no repair here.)
    assert "R = e + i" not in norm_plain, "plain text has 'R = e + i'"
    assert "R = e - i" not in norm_plain, "plain text has 'R = e - i'"
    norm_back = norm_back.replace("R = e + i", "R = E + I")
    norm_back = norm_back.replace("R = e - i", "R = E - I")
    if norm_back != norm_plain:
        # Show the first point of difference for diagnosis.
        for i, (a, b) in enumerate(zip(norm_back, norm_plain)):
            if a != b:
                problems.append(
                    "%s: round-trip mismatch at char %d: back %r vs plain %r"
                    % (label, i, norm_back[max(0, i - 30):i + 30], norm_plain[max(0, i - 30):i + 30])
                )
                break
        else:
            problems.append(
                "%s: round-trip length mismatch: back %d chars, plain %d"
                % (label, len(norm_back), len(norm_plain))
            )
    return problems


def main():
    wanted = [int(a) for a in sys.argv[1:]] or list(build_page.LESSON_NUMS)
    os.makedirs(OUT_DIR, exist_ok=True)
    all_problems = []
    for n in wanted:
        lines, plain = build_brf(n)
        path = os.path.join(OUT_DIR, "lesson-%02d.brf" % n)
        with open(path, "w", encoding="ascii", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        problems = validate_brf("lesson %d" % n, lines, plain)
        pages = lines.count(PAGE_BREAK) + 1
        content_lines = len([ln for ln in lines if ln != PAGE_BREAK])
        print(
            "lesson %02d: %d lines, %d pages, %d bytes%s"
            % (
                n,
                content_lines,
                pages,
                os.path.getsize(path),
                "" if not problems else " — PROBLEMS: " + "; ".join(problems),
            )
        )
        all_problems.extend(problems)
    if all_problems:
        print("\nVALIDATION FAILED (%d problems)" % len(all_problems))
        sys.exit(1)
    print("\nAll %d .brf file(s) valid." % len(wanted))


if __name__ == "__main__":
    main()
