#!/usr/bin/env python3
"""JavaScript tests for the course page.

1. node --check on the whole <script> block (syntax).
2. splitSentences unit tests (extracted from the page's own script).
3. Quiz logic test: the page's own quiz block run against a small fake DOM
   (correct answer scores right, wrong answer names the right one, second
   clicks ignored, feedback hidden until answered).
"""
import os
import re
import subprocess
import sys

STAGING = os.path.expanduser("~/workspace/github-pages-staging/technician-class")
TMP = "/tmp/tech-class-js-tests"
os.makedirs(TMP, exist_ok=True)

with open(os.path.join(STAGING, "index.html"), encoding="utf-8") as f:
    page = f.read()

# The main script is the block that holds splitSentences: the page also
# carries a one-line head script that applies a stored light/dark choice
# before first paint, and that block comes first.
script = next(
    block.split("</script>", 1)[0]
    for block in page.split("<script>")[1:]
    if "splitSentences" in block
)
script_path = os.path.join(TMP, "course-script.js")
with open(script_path, "w", encoding="utf-8") as f:
    f.write(script)


def run_node(path, label):
    proc = subprocess.run(
        ["node", path], capture_output=True, text=True, timeout=60
    )
    print("--- %s ---" % label)
    print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="")
    if proc.returncode != 0:
        print("%s FAILED (exit %d)" % (label, proc.returncode))
        sys.exit(1)
    print("%s PASSED" % label)


# 1. Syntax check on the whole script.
proc = subprocess.run(
    ["node", "--check", script_path], capture_output=True, text=True, timeout=60
)
print("--- node --check (whole script) ---")
print(proc.stdout, end="")
print(proc.stderr, end="")
if proc.returncode != 0:
    print("SYNTAX CHECK FAILED")
    sys.exit(1)
print("SYNTAX CHECK PASSED")


# 2. splitSentences: extract the function with a string-aware brace matcher
# (the function contains a "}" inside the string "\"')]}\"", so a naive
# brace count stops early), then test it.
def extract_function(script_text, signature):
    start = script_text.index(signature)
    depth = 0
    end = start
    quote = None
    escaped = False
    while True:
        ch = script_text[end]
        if quote is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end += 1
                break
        end += 1
    return script_text[start:end]


fn_src = extract_function(script, "function splitSentences(text) {")
assert fn_src.rstrip().endswith("return sentences.filter(Boolean);\n  }"), (
    "splitSentences extraction looks wrong:\n" + fn_src[-120:]
)

sent_tests = r"""
function assertEqual(actual, expected, label) {
  var a = JSON.stringify(actual), e = JSON.stringify(expected);
  if (a !== e) {
    console.log("FAIL " + label + "\n  got:      " + a + "\n  expected: " + e);
    process.exit(1);
  }
  console.log("ok " + label);
}
assertEqual(splitSentences("Hello world. How are you?"),
  ["Hello world.", "How are you?"], "two sentences");
assertEqual(splitSentences("The channel is 146.52 megahertz (MHz)."),
  ["The channel is 146.52 megahertz (MHz)."], "decimal point is not a split");
assertEqual(splitSentences('He said "Hello." Then left.'),
  ['He said "Hello."', "Then left."], "closing quote stays with sentence");
assertEqual(splitSentences("Wait! Really? Yes."),
  ["Wait!", "Really?", "Yes."], "exclamation and question");
assertEqual(splitSentences("No terminator here"),
  ["No terminator here"], "no terminator");
assertEqual(splitSentences("E = I × R. I = E / R."),
  ["E = I × R.", "I = E / R."], "formulas");
assertEqual(splitSentences("First sentence.  Second has  double spaces."),
  ["First sentence.", "Second has  double spaces."], "extra spaces");
console.log("splitSentences: all cases passed");
"""
sent_path = os.path.join(TMP, "test-sentences.js")
with open(sent_path, "w", encoding="utf-8") as f:
    f.write(fn_src + "\n" + sent_tests)
run_node(sent_path, "splitSentences tests")

# 2b. prepareSpeech: the abbreviation table + the function, extracted from
# the page's own script. Every transform is tested against real lesson
# and quiz sentences; unchanged inputs are tested too.
abbr_src = extract_function(script, "var SPEECH_ABBREVIATIONS = {") + ";"
prep_src = extract_function(script, "function prepareSpeech(text) {")
assert prep_src.rstrip().endswith("return text;\n  }"), (
    "prepareSpeech extraction looks wrong:\n" + prep_src[-120:]
)
assert '"MHz": "M H Z"' in abbr_src, "abbreviation table extraction looks wrong"

prep_tests = r"""
function assertSpeech(input, expected, label) {
  var actual = prepareSpeech(input);
  if (actual !== expected) {
    console.log("FAIL " + label + "\n  got:      " + JSON.stringify(actual) +
      "\n  expected: " + JSON.stringify(expected));
    process.exit(1);
  }
  console.log("ok " + label);
}
// Parenthetical abbreviations -> "common abbreviation" + spelled letters.
assertSpeech("The channel is 146.52 megahertz (MHz).",
  "The channel is 146.52 megahertz, common abbreviation M H Z.",
  "megahertz (MHz)");
assertSpeech("Five kilohertz (kHz) is a small step.",
  "Five kilohertz, common abbreviation k H z, is a small step.",
  "kilohertz (kHz)");
assertSpeech("Hertz (Hz) is the unit of frequency.",
  "Hertz, common abbreviation H z, is the unit of frequency.",
  "Hertz (Hz)");
assertSpeech("House power is alternating current (AC).",
  "House power is alternating current, common abbreviation A C.",
  "alternating current (AC)");
assertSpeech("A radio needs direct current (DC).",
  "A radio needs direct current, common abbreviation D C.",
  "direct current (DC)");
assertSpeech("What is standing wave ratio (SWR)?",
  "What is standing wave ratio, common abbreviation S W R?",
  "standing wave ratio (SWR)");
assertSpeech("decibel (dB): a unit that compares two power levels.",
  "decibel, common abbreviation d B: a unit that compares two power levels.",
  "decibel (dB)");
assertSpeech("The Federal Communications Commission (FCC) urges hams to use it.",
  "The Federal Communications Commission, common abbreviation F C C, urges hams to use it.",
  "Federal Communications Commission (FCC)");
assertSpeech("Each Volunteer Examiner Coordinator (VEC) runs exam sessions.",
  "Each Volunteer Examiner Coordinator, common abbreviation V E C, runs exam sessions.",
  "Volunteer Examiner Coordinator (VEC)");
assertSpeech("Bring a photo identification (ID) to the exam.",
  "Bring a photo identification, common abbreviation I D, to the exam.",
  "identification (ID)");
assertSpeech("An integrated circuit (IC) holds many parts.",
  "An integrated circuit, common abbreviation I C, holds many parts.",
  "integrated circuit (IC)");
assertSpeech("A light emitting diode (LED) gives off light.",
  "A light emitting diode, common abbreviation L E D, gives off light.",
  "light emitting diode (LED)");
assertSpeech("The voice mode for very high frequency (VHF) is FM.",
  "The voice mode for very high frequency, common abbreviation V H F, is FM.",
  "very high frequency (VHF)");
assertSpeech("and ultra high frequency (UHF) above that.",
  "and ultra high frequency, common abbreviation U H F, above that.",
  "ultra high frequency (UHF)");
assertSpeech("You have covered radio frequency (RF) already.",
  "You have covered radio frequency, common abbreviation R F, already.",
  "radio frequency (RF)");
assertSpeech("SSB is the main voice mode on high frequency (HF).",
  "SSB is the main voice mode on high frequency, common abbreviation H F.",
  "high frequency (HF)");
assertSpeech("How to get your FCC Registration Number (FRN).",
  "How to get your FCC Registration Number, common abbreviation F R N.",
  "FCC Registration Number (FRN)");
assertSpeech("Ask your American Radio Relay League (ARRL) club.",
  "Ask your American Radio Relay League, common abbreviation A R R L, club.",
  "American Radio Relay League (ARRL)");
assertSpeech("contact the International Space Station (ISS) on VHF bands?",
  "contact the International Space Station, common abbreviation I S S, on VHF bands?",
  "International Space Station (ISS)");
assertSpeech("What is the Amateur Radio Emergency Service (ARES)?",
  "What is the Amateur Radio Emergency Service, common abbreviation A R E S?",
  "Amateur Radio Emergency Service (ARES)");
assertSpeech("one characteristic of single sideband (SSB) compared to FM?",
  "one characteristic of single sideband, common abbreviation S S B, compared to FM?",
  "single sideband (SSB)");
assertSpeech("Phase shift keying (PSK) sends typed words.",
  "Phase shift keying, common abbreviation P S K, sends typed words.",
  "Phase shift keying (PSK)");
assertSpeech("the Variable Frequency Oscillator (VFO) circuit in a transceiver?",
  "the Variable Frequency Oscillator, common abbreviation V F O, circuit in a transceiver?",
  "Variable Frequency Oscillator (VFO)");
assertSpeech("your Certificate of Successful Completion of Examination (CSCE).",
  "your Certificate of Successful Completion of Examination, common abbreviation C S C E.",
  "Certificate of Successful Completion of Examination (CSCE)");
assertSpeech("What is Voice Over Internet Protocol (VoIP)?",
  "What is Voice Over Internet Protocol, common abbreviation V o I P?",
  "Voice Over Internet Protocol (VoIP)");
assertSpeech("A Coder-Decoder (CODEC) that converts analog voice data to DMR digital data",
  "A Coder-Decoder, common abbreviation C O D E C, that converts analog voice data to DMR digital data",
  "Coder-Decoder (CODEC)");
// Word parentheticals are left alone.
assertSpeech("A beam antenna (Yagi) sends your signal in one direction.",
  "A beam antenna (Yagi) sends your signal in one direction.",
  "(Yagi) untouched");
assertSpeech("The current is 5 amperes (amp).",
  "The current is 5 amperes (amp).",
  "(amp) untouched");
// Formulas: x -> times, / -> divided by, = -> equals, + -> plus,
// - -> minus, E2/I2 -> squared.
assertSpeech("The short form is E = I x R.",
  "The short form is E equals I times R.",
  "E = I x R");
assertSpeech("We write that as I = E / R.",
  "We write that as I equals E divided by R.",
  "I = E / R");
assertSpeech("We write that as R = E / I.",
  "We write that as R equals E divided by I.",
  "R = E / I");
assertSpeech("Use P = E x I.",
  "Use P equals E times I.",
  "P = E x I");
assertSpeech("C. I = E2 x R",
  "C. I equals E squared times R",
  "E2 x R (quiz option)");
assertSpeech("D. I = E2 / R",
  "D. I equals E squared divided by R",
  "E2 / R (quiz option)");
assertSpeech("C. P = I2 x E",
  "C. P equals I squared times E",
  "I2 x E (quiz option)");
assertSpeech("C. R = E + I",
  "C. R equals E plus I",
  "R = E + I (quiz option)");
assertSpeech("D. R = E - I",
  "D. R equals E minus I",
  "R = E - I (quiz option)");
assertSpeech("B. P = E / I",
  "B. P equals E divided by I",
  "P = E / I (quiz option)");
assertSpeech("The short form is E = I x R. We write that as I = E / R.",
  "The short form is E equals I times R. We write that as I equals E divided by R.",
  "both formula transforms");
// Fractions -> words.
assertSpeech("A. 5/8 wave vertical",
  "A. five eighths wave vertical",
  "5/8 wave vertical");
assertSpeech("C. 1/2 wavelength at the operating frequency",
  "C. one half wavelength at the operating frequency",
  "1/2 wavelength");
assertSpeech("B. Time of day accurate to plus or minus 1/10 second",
  "B. Time of day accurate to plus or minus one tenth second",
  "1/10 second");
// coax -> co-ax; coaxial untouched.
assertSpeech("Coaxial cable, or coax, is the most common feed line.",
  "Coaxial cable, or co-ax, is the most common feed line.",
  "coax mid-sentence");
assertSpeech("Coax is easy to use.",
  "co-ax is easy to use.",
  "Coax sentence-initial");
assertSpeech("You check the feed line and find water in the coax connector.",
  "You check the feed line and find water in the co-ax connector.",
  "coax connector");
assertSpeech("Coaxial cable (coax): a feed line with a center wire inside a shield.",
  "Coaxial cable (co-ax): a feed line with a center wire inside a shield.",
  "Coaxial cable (coax)");
assertSpeech("A coaxial cable is a feed line with a center wire inside a shield.",
  "A coaxial cable is a feed line with a center wire inside a shield.",
  "coaxial untouched");
// Bare abbreviations the voice already reads right are left alone.
assertSpeech("146.52 MHz is the national calling channel.",
  "146.52 MHz is the national calling channel.",
  "bare MHz after a number");
assertSpeech("A change of 3 dB means double or half.",
  "A change of 3 dB means double or half.",
  "bare dB after a number");
assertSpeech("Put 12 in place of E and 2 in place of I, then divide 12 by 2.",
  "Put 12 in place of E and 2 in place of I, then divide 12 by 2.",
  "plain sentence untouched");
// SWR ratios -> "X to one"; clock times untouched.
assertSpeech("A reading of 1:1 means a perfect match.",
  "A reading of one to one means a perfect match.",
  "1:1");
assertSpeech("The meter reads 1.2:1.",
  "The meter reads one point two to one.",
  "1.2:1");
assertSpeech("A reading of 1.5:1 is still good.",
  "A reading of one point five to one is still good.",
  "1.5:1");
assertSpeech("A reading of 2:1 is fair.",
  "A reading of two to one is fair.",
  "2:1");
assertSpeech("A reading of 3:1 is poor.",
  "A reading of three to one is poor.",
  "3:1");
assertSpeech("C. 1:1",
  "C. one to one",
  "1:1 quiz option");
assertSpeech("At 1:1 no power bounces back.",
  "At one to one no power bounces back.",
  "1:1 explanation");
assertSpeech("10:1 is a bad match.",
  "ten to one is a bad match.",
  "10:1");
assertSpeech("It meets at 19:00 Central on Saturdays.",
  "It meets at 19:00 Central on Saturdays.",
  "19:00 untouched");
assertSpeech("It shows a pass coming over her town at 18:30.",
  "It shows a pass coming over her town at 18:30.",
  "18:30 untouched");
assertSpeech("The mix is 50:50.",
  "The mix is 50:50.",
  "50:50 untouched");

console.log("prepareSpeech: all cases passed");
"""
prep_path = os.path.join(TMP, "test-prepare-speech.js")
with open(prep_path, "w", encoding="utf-8") as f:
    f.write(abbr_src + "\n" + prep_src + "\n" + prep_tests)
run_node(prep_path, "prepareSpeech tests")


# 3. Quiz block against a fake DOM.
q_start = script.index("  // ---- Quizzes ")
q_end = script.index("  // ---- Close buttons")
quiz_block = script[q_start:q_end]

quiz_test = r"""
// ---- Fake DOM (only what the quiz block touches) ----
function makeClassList() {
  var set = {};
  return {
    add: function (c) { set[c] = true; },
    contains: function (c) { return !!set[c]; }
  };
}
function makeOption(letter, correct) {
  var listeners = {};
  var el = {
    letter: letter,
    disabled: false,
    classList: makeClassList(),
    attrs: { "data-correct": correct ? "true" : "false" },
    getAttribute: function (n) { return this.attrs[n]; },
    addEventListener: function (ev, fn) { listeners[ev] = fn; },
    click: function () { if (listeners.click) listeners.click.call(this); }
  };
  return el;
}
function makeQuestion(correctLetter) {
  var options = ["A", "B", "C", "D"].map(function (l) {
    return makeOption(l, l === correctLetter);
  });
  var feedback = { hidden: true, classList: makeClassList() };
  var verdict = { textContent: "" };
  return {
    options: options, feedback: feedback, verdict: verdict,
    getAttribute: function (n) {
      return n === "data-correct-letter" ? correctLetter : null;
    },
    querySelectorAll: function (sel) {
      return sel === ".quiz-option" ? options : [];
    },
    querySelector: function (sel) {
      if (sel === ".quiz-feedback") return feedback;
      if (sel === ".verdict") return verdict;
      return null;
    }
  };
}
var q1 = makeQuestion("C");
var q2 = makeQuestion("A");
var document = {
  querySelectorAll: function (sel) {
    return sel === ".quiz-question" ? [q1, q2] : [];
  }
};

// ---- The page's own quiz block runs here ----
""" + quiz_block + r"""
// ---- Assertions ----
function assert(cond, label) {
  if (!cond) { console.log("FAIL " + label); process.exit(1); }
  console.log("ok " + label);
}

// Feedback hidden before answering.
assert(q1.feedback.hidden === true, "feedback hidden before answering");

// Correct answer: pick C on question 1 (correct letter C).
q1.options[2].click();
assert(q1.feedback.hidden === false, "feedback shown after answering");
assert(q1.verdict.textContent === "Correct.", "correct verdict text");
assert(q1.options[2].classList.contains("chosen-correct"), "chosen option marked correct");
assert(q1.options[2].classList.contains("correct-answer"), "correct option marked");
assert(q1.options.every(function (o) { return o.disabled; }), "all options lock after answering");
assert(q1.feedback.classList.contains("feedback-correct"), "feedback marked correct");

// Wrong answer: pick B on question 2 (correct letter A).
q2.options[1].click();
assert(q2.feedback.hidden === false, "feedback shown after wrong answer");
assert(q2.verdict.textContent === "Not quite. The right answer is A.",
  "wrong verdict names the right answer");
assert(q2.options[1].classList.contains("chosen-wrong"), "wrong pick marked wrong");
assert(q2.options[0].classList.contains("correct-answer"), "right option marked after wrong pick");
assert(!q2.options[0].classList.contains("chosen-correct"), "right option not marked chosen");
assert(q2.feedback.classList.contains("feedback-wrong"), "feedback marked wrong");
assert(q2.options.every(function (o) { return o.disabled; }), "options lock after wrong answer");

// Second click is ignored.
q2.options[0].click();
assert(q2.verdict.textContent === "Not quite. The right answer is A.",
  "second click ignored");
console.log("quiz logic: all cases passed");
"""
quiz_path = os.path.join(TMP, "test-quiz.js")
with open(quiz_path, "w", encoding="utf-8") as f:
    f.write(quiz_test)
run_node(quiz_path, "quiz logic tests")


# 4. buildQueue + appendEndOfLessonCue against a fake lesson section.
# 5. buildQuizQueue against a fake quiz section: questions + options are
#    queued, the correct answer is never exposed, feedback is queued only
#    once its question has been answered.
bq_src = extract_function(script, "function buildQueue(sectionEl) {")
cue_src = extract_function(script, "function appendEndOfLessonCue(lessonNum) {")
quizq_src = extract_function(script, "function buildQuizQueue(quizEl, quizNum) {")
assert "queue.push({ text: sentences[s], block: blocks[b], section: section });" in bq_src, (
    "buildQueue extraction looks wrong"
)
assert '"End of lesson " + lessonNum + ". Your quiz is next."' in cue_src, (
    "appendEndOfLessonCue extraction looks wrong"
)
assert "data-correct" not in quizq_src, (
    "buildQuizQueue must never read data-correct"
)
bsp_src = extract_function(script, "function blockSpokenText(block) {")
assert 'querySelectorAll(".sr-only")' in bsp_src, (
    "blockSpokenText extraction looks wrong"
)

queue_tests = r"""
var queue = [];
function assert(cond, label) {
  if (!cond) { console.log("FAIL " + label); process.exit(1); }
  console.log("ok " + label);
}
function queueTexts() {
  return queue.map(function (item) { return item.text; });
}

// Fake DOM elements need cloneNode: blockSpokenText clones each block and
// strips sr-only spans from the clone before reading its text.
function withClone(el) {
  el.cloneNode = function () {
    return {
      textContent: el.textContent,
      querySelectorAll: function () { return []; }
    };
  };
  return el;
}

// ---- Test 4: lesson queue + end-of-lesson cue ----
function makeBlock(text, section) {
  return withClone({
    textContent: text,
    getAttribute: function (n) { return n === "data-section" ? section : null; }
  });
}
var lessonEl = {
  querySelectorAll: function (sel) {
    if (sel !== ".readable") return [];
    return [
      makeBlock("Lesson 10: Ohm's law and power.", "Lesson 10"),
      makeBlock("The short form is E = I x R.", "The idea in plain words"),
      makeBlock("Coaxial cable, or coax, is the most common feed line.", "The idea in plain words")
    ];
  }
};
buildQueue(lessonEl);
appendEndOfLessonCue(10);
var texts = queueTexts();
assert(texts[0] === "Lesson 10: Ohm's law and power.", "lesson queue starts with the heading");
assert(texts[1] === "The short form is E equals I times R.", "lesson queue applies speech prep (formula)");
assert(texts[2] === "Coaxial cable, or co-ax, is the most common feed line.", "lesson queue applies speech prep (coax)");
assert(texts[texts.length - 1] === "End of lesson 10. Your quiz is next.", "end-of-lesson cue is last");
assert(queue[queue.length - 1].section === "End of lesson", "cue section is End of lesson");
assert(queue[queue.length - 1].block === null, "cue has no block to highlight");

// ---- Test 5: quiz queue ----
function makeOption(letter, text) {
  return withClone({
    textContent: letter + ". " + text,
    getAttribute: function (n) {
      throw new Error("buildQuizQueue must not read " + n);
    }
  });
}
function makeQuestion(qText, options, feedbackText, feedbackHidden) {
  var feedback = withClone({ textContent: feedbackText, hidden: feedbackHidden });
  var qTextEl = withClone({ textContent: qText });
  return {
    feedback: feedback,
    querySelector: function (sel) {
      if (sel === ".quiz-text") return qTextEl;
      if (sel === ".quiz-feedback") return feedback;
      return null;
    },
    querySelectorAll: function (sel) {
      return sel === ".quiz-option" ? options : [];
    }
  };
}
var q1Options = [
  makeOption("A", "Providing personal radio communications for as many citizens as possible"),
  makeOption("B", "Providing communications for international contesting"),
  makeOption("C", "Advancing skills in the technical and communication phases of the radio art"),
  makeOption("D", "All these choices are correct")
];
var q1 = makeQuestion(
  "Question 1. What is standing wave ratio (SWR)?",
  q1Options,
  "Correct. That is right — the ratio compares forward power with reflected power.",
  true);
var q2Options = [
  makeOption("A", "I = E x R"),
  makeOption("B", "I = E / R"),
  makeOption("C", "I = E2 x R"),
  makeOption("D", "I = R / E")
];
var q2 = makeQuestion(
  "Question 2. Which formula finds current?",
  q2Options,
  "Not quite. The right answer is B. Current is voltage divided by resistance.",
  true);
var quizEl = {
  querySelector: function (sel) {
    return sel === "h2" ? withClone({ textContent: "Check yourself — Lesson 21" }) : null;
  },
  querySelectorAll: function (sel) {
    return sel === ".quiz-question" ? [q1, q2] : [];
  }
};
buildQuizQueue(quizEl, 21);
texts = queueTexts();
assert(texts[0] === "Check yourself — Lesson 21", "quiz queue starts with the heading");
assert(texts.indexOf("Question 1.") !== -1, "quiz queue reads the question number");
assert(texts.indexOf("What is standing wave ratio, common abbreviation S W R?") !== -1,
  "quiz queue applies speech prep (SWR)");
assert(texts.indexOf("A.") !== -1 && texts.indexOf("Providing personal radio communications for as many citizens as possible") !== -1,
  "quiz queue reads the options");
assert(texts.indexOf("B.") !== -1 && texts.indexOf("I equals E divided by R") !== -1,
  "quiz queue applies speech prep to options (formula)");
assert(texts.indexOf("C.") !== -1 && texts.indexOf("I equals E squared times R") !== -1,
  "quiz queue applies speech prep to options (E2 x R)");
assert(queue.every(function (item) { return item.section !== "Feedback"; }),
  "no feedback queued before answering");
assert(texts.join(" ").indexOf("data-correct") === -1,
  "queue never mentions data-correct");

// Answer question 1: its feedback is queued on the next read.
q1.feedback.hidden = false;
buildQuizQueue(quizEl, 21);
texts = queueTexts();
assert(queue.some(function (item) { return item.section === "Feedback"; }),
  "feedback queued after answering");
assert(texts.indexOf("Correct.") !== -1, "feedback verdict is read");
assert(texts.indexOf("That is right — the ratio compares forward power with reflected power.") !== -1,
  "feedback explanation is read");
assert(queue.every(function (item) {
  return item.section !== "Feedback" || item.block === q1.feedback;
}), "only the answered question's feedback is queued");
// ---- Test 6: blockSpokenText strips sr-only spans from a clone ----
var srRemoved = false;
var fakeSr = { parentNode: { removeChild: function () { srRemoved = true; } } };
var fakeClone = {
  textContent: "The meter reads 1.2:1.  That is a good match.",
  querySelectorAll: function (sel) {
    return sel === ".sr-only" ? [fakeSr] : [];
  }
};
var fakeBlock = { cloneNode: function () { return fakeClone; } };
assert(blockSpokenText(fakeBlock) === "The meter reads 1.2:1. That is a good match.",
  "blockSpokenText normalizes whitespace");
assert(srRemoved, "blockSpokenText removes sr-only spans from the clone");
var plainClone = {
  textContent: "Plain text here.",
  querySelectorAll: function () { return []; }
};
assert(blockSpokenText({ cloneNode: function () { return plainClone; } }) === "Plain text here.",
  "blockSpokenText passes plain blocks through");

console.log("queue building: all cases passed");
"""
queue_path = os.path.join(TMP, "test-queues.js")
with open(queue_path, "w", encoding="utf-8") as f:
    f.write(abbr_src + "\n" + prep_src + "\n" + fn_src + "\n" + bsp_src + "\n" + bq_src + "\n" + cue_src + "\n" + quizq_src + "\n" + queue_tests)
run_node(queue_path, "queue building tests")

print()
print("ALL JS TESTS PASSED")
