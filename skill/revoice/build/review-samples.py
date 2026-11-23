#!/usr/bin/env python3
"""Mark each extracted sample KEEP or DROP with plain rules, on this machine.

Reads samples/index.csv (from extract-samples.py), judges every sample file
with the rules below, and adds the columns verdict, score and reason to
index.csv. Existing columns and rows are kept. build-profile.py then uses only
the KEEP rows, best score first. Nothing is sent anywhere: the script uses the
standard library only and makes no network call.

A sample is DROPPED when it is: broken extraction (mostly signature or contact
lines, many replacement or non-letter characters, or cut off mid-sentence and
very short); mostly quoted, forwarded or boilerplate lines; mostly list, table,
code or log lines (code includes NAME=value settings and shell commands); a near-duplicate form letter within the set; not in the
author's usual language; or signed with a clearly different name than --author.
score is 1-5 from prose length and paragraph structure. reason is one fixed
label (see REASONS), never a quote from the email.

--mode says where the samples came from (default email). For passages from
documents (extract-documents.py), writing and brand turn the email rules off:
quoted, forwarded and header lines, unsubscribe boilerplate, and sign-off names.
writing drops a passage whose first or
last line is a byline ("By <Name>") naming someone other than --author; brand
keeps every author. Both also drop quoted model output (a lead-in naming a model,
a prompt or a response, then the answer; answers under vendor headings such as
"Small Model Responses (OpenAI)" over half the passage; or mostly code-like lines) and table
text (mostly short lines, many of them numbers). Both print a coverage: line (KEEP
passages, and the distinct source values among them), warn below the minimum in
MINIMUMS, and exit with status 3 below the floor in FLOORS, after index.csv is
written so the verdicts can be read.

In writing and brand, a passage that passes is then cut before it is judged again:
code, NAME=value and shell command lines (or runs of them inside a line), each
model answer (from a vendor heading such as "OpenAI Response", found inside a
joined PDF line too, to the next heading; or the paragraph after a lead-in that
says the model's words follow, "Here is what ChatGPT said:", or that is quoted),
and a lead-in left with nothing after it ("Common Commands:"). A lead-in that
only names a model ("Claude's summary captured the difference:") before the
author's own paragraph is cut alone, and a title line over a cut lead-in stays
("Step 1. Checkout ..." over "Clone the repository:"). Only the rest is
judged and kept: the sample file is rewritten with it, its words column updated,
and a cut column in index.csv says what was cut. Under MIN_REMAINDER_WORDS left,
the passage is dropped for what was cut. Email samples are never cut.

index.csv and the cut sample files are written only after every sample was
judged, so a failed run leaves them as they were. A rerun reviews every sample
again and keeps the cut note of a file it already cut.
"""
from __future__ import annotations
import argparse
import csv
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

COLUMNS = ["verdict", "score", "reason"]
CUT_COLUMN = "cut"  # writing and brand only

KEEP_REASON = "own writing"
REASONS = [KEEP_REASON, "broken extraction", "quoted or forwarded text",
           "list, table, code or log", "form letter", "not in the author's language",
           "written in another name", "written by someone else", "quoted model output",
           "table or numbers"]

MODES = ["email", "writing", "brand"]
# Per document mode: (KEEP passages, distinct documents). Below the floor the build
# stops (exit 3); below the minimum it warns that the profile will be weaker.
FLOORS = {"writing": (10, 0), "brand": (10, 3)}
MINIMUMS = {"writing": (20, 5), "brand": (20, 5)}
FLOOR_EXIT = 3

# A rule fires when at least this share of the non-blank lines match.
MOSTLY = 0.5
SIGNATURE_SHARE = 0.6
# Broken extraction: replacement characters, and letters among non-space characters.
MAX_REPLACEMENT_SHARE = 0.02
MIN_LETTER_SHARE = 0.5
# "Very short" for the cut-off check.
CUT_OFF_WORDS = 12
# Near-duplicates: word n-grams, and the bounds on the work done per sample.
NGRAM = 5
MIN_SHINGLES = 8  # shorter samples (a one-line reply) can repeat honestly
MAX_SHINGLES = 500  # shingles looked at per sample
BUCKET = 50  # samples remembered per shingle
DUPLICATE_OVERLAP = 0.7
# Language: share of common function words of the author's language (see LANGUAGE_WORDS).
MIN_LANGUAGE_WORDS = 20
LANGUAGE_SHARE = 0.12  # below this a sample does not look like the author's language
LANGUAGE_AUTHOR_SHARE = 0.2  # the set's median must reach this for the check to run

FUNCTION_WORDS = frozenset(
    "the a an and or but of to in on at for with from by as is are was were be been it this "
    "that these those i you he she we they my your our their me us them not no if so do does "
    "did have has had will would can could should there what which who when about".split())
GERMAN_FUNCTION_WORDS = frozenset(
    "der die das den dem des ein eine einen einem einer eines und oder aber von zu zum zur in "
    "im an am auf aus bei mit nach für über um ist sind war waren sein bin bist hat haben habe "
    "hatte wird werden wurde es ich du er sie wir ihr mich mir dich dir uns euch ihn ihm ihnen "
    "nicht kein keine wenn dass ob als wie was wer wo auch noch nur schon sehr doch da hier "
    "mein dein unser kann können muss müssen soll sollte will würde weil".split())
SPANISH_FUNCTION_WORDS = frozenset(
    "el la lo los las un una unos unas y e o u pero de del a al en con por para sin sobre "
    "entre hasta desde es son era eran fue ser estar está están estaba hay ha han he has "
    "tengo tiene tienen yo tú él ella nosotros ellos ellas me te se nos le les mi mis tu tus "
    "su sus no ni si que qué como cuando donde porque muy más ya también este esta esto ese "
    "esa eso todo puede quiero voy va".split())
FRENCH_FUNCTION_WORDS = frozenset(
    "le la les un une des du de et ou mais à au aux en dans sur sous avec pour par sans chez "
    "est sont était être ai as a avons avez ont je tu il elle on nous vous ils elles me te se "
    "moi toi lui leur mon ma mes ton ta tes son sa ses notre votre ne pas plus que qui si "
    "comme quand où parce ce cette ces très aussi bien y peux peut veux vais va".split())
# The author's language is the one with the highest median share; English wins a tie.
# FUNCTION_WORDS stays English: other_name uses it to tell a name from an ordinary word.
# Spanish and French share many short words (de, la, que, se...); only the words that tell
# them apart count, or a stray sample in one would pass in the other.
LANGUAGE_WORDS = {"english": FUNCTION_WORDS, "german": GERMAN_FUNCTION_WORDS,
                  "spanish": SPANISH_FUNCTION_WORDS - FRENCH_FUNCTION_WORDS,
                  "french": FRENCH_FUNCTION_WORDS - SPANISH_FUNCTION_WORDS}
DANGLING = frozenset(
    "the a an and or but of to in on at for with from by as is are was were be that this "
    "which who if so than then because my your our their his her its".split())
COMMON_NON_NAMES = frozenset("will see give talk call let get send thanks soon later again".split())
CLOSINGS = re.compile(
    r"^(thanks|thank you|best|best regards|kind regards|regards|warm regards|cheers|sincerely|"
    r"yours|yours sincerely|yours truly|many thanks|all the best|take care|talk soon)\s*[,!.]?$",
    re.I)
NAME_LINE = re.compile(r"^[^\W\d_][\w.'-]*(\s+[^\W\d_][\w.'-]*){0,2}$")
# "By Jane Doe", "Written by Jane Doe", "*Posted by Jane Doe on March 3*".
BYLINE = re.compile(r"^[*_\s]*(?:written |posted )?by\s+(.+?)(?:\s+on\s.*)?[*_\s]*$", re.I)
DATE_WORDS = frozenset(
    "monday tuesday wednesday thursday friday saturday sunday january february march april "
    "may june july august september october november december today tomorrow tonight".split())

QUOTE = re.compile(r"^\s*>")
FORWARD_START = re.compile(
    r"^\s*(-{2,}\s*(original message|forwarded message)|begin forwarded message|"
    r"_{5,}$|on .{5,120} wrote:\s*$)", re.I)
HEADER = re.compile(r"^\s*(from|sent|to|cc|subject|date):\s", re.I)
BOILERPLATE = re.compile(
    r"confidential|intended (only )?for the|unsubscribe|privacy (notice|policy)|"
    r"disclaimer|this (e-?mail|message) and any attachments|if you are not the intended", re.I)
BULLET = re.compile(r"^\s*([-*\u2022\u25cf]|\d{1,3}[.)])\s+\S")
TABLE = re.compile(r"\|.*\||\t\S.*\t|\S {3,}\S.* {3,}\S")
CODE = re.compile(r"^(\t| {4})\s*\S|^\s*(def |class |import |from \S+ import |#include|\$ |```)|[{};]\s*$")
# A PDF loses code formatting, so a setup section reads as lines like these: one or more
# "NAME=value" settings ("AI21_API_KEY=", "export DEBUG=1"), or a shell command. A command is
# a lowercase command word with at least one argument and no ordinary English word, so a
# wrapped sentence that starts with one ("npm install and then waited for...") is prose.
ENV_LINE = re.compile(r"""^\s*(export\s+)?([A-Z][A-Z0-9_]+=("[^"]*"|'[^']*'|\S*)(\s+|$))+$""")
SHELL_COMMANDS = ("git npm npx pnpm yarn pip pip3 python python3 node export cd curl wget docker "
                  "brew sudo mkdir chmod").split()
SHELL_LINE = re.compile(r"^\s*(\$\s+)?(" + "|".join(SHELL_COMMANDS) + r")\s+\S")
LOG = re.compile(
    r"^\s*\[?(\d{4}-\d\d-\d\d[ T]\d\d:\d\d|\d\d:\d\d:\d\d|"
    r"(TRACE|DEBUG|INFO|WARN(ING)?|ERROR|FATAL)\b)")
CONTACT_LABEL = re.compile(
    r"^\s*(--\s*$|(tel|phone|mobile|cell|fax|address|email|e-mail|web|www)\b[\s.:]|sent from my|"
    r"get outlook|sent via)", re.I)
# An address, URL or phone number; a line is contact-like when little else is on it.
CONTACT_ITEM = re.compile(
    r"\+\d[\d\s().-]{7,}\d|\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}|\S+@\S+\.\S+|https?://\S+|www\.\S+")
CONTACT_EXTRA_WORDS = 3
WORD = re.compile(r"[^\W\d_]+(?:['\u2019][^\W\d_]+)?")

# Quoted model output (writing and brand). A lead-in is a short line that either ends in
# ":" and names a model or a prompt ("Here is what ChatGPT said:"), or is a heading whose
# last word is RESPONSE_WORDS after a capitalised name that holds MODEL_NAMES ("AI21 Studio
# Response") or ends in MODEL_KINDS ("Fireworks AI Response"). The bare words output,
# response and answer are no model signal ("Incident Response", "The short answer:");
# vendor names only count in a heading, so "Groq pricing:" or "Our AI roadmap:" is not a
# lead-in, and a generic word only right before the response word ("AI Incident Response"
# is an ordinary heading). "llm-env" is a tool, not a model.
MODEL_WORDS = re.compile(
    r"\b(chatgpt|claude|gpt[\w.-]*|gemini|llms?(?!-)|the model|the prompt|"
    r"(model|assistant|bot|ai)(['\u2019]s)? (response|output|answer|reply|completion))\b", re.I)
MODEL_NAMES = frozenset(
    "chatgpt claude gemini bard llm llama mistral mixtral openai anthropic cohere groq grok "
    "ai21 jamba deepseek qwen copilot perplexity".split())
MODEL_KINDS = frozenset("ai model assistant bot chatbot".split())
RESPONSE_WORDS = frozenset("response output answer reply completion".split())
LEAD_IN_WORDS = 8  # a longer line ending in ":" is a sentence, not a lead-in
# A lead-in that says the model's words follow ("Here is what ChatGPT said:", "AI21 Studio
# Response") marks the block after it. One that only names a model ("Claude's summary
# captured the difference:") marks it only when the block looks quoted (see quoted_block):
# the reader drops a quote or code block, and the author's own paragraph after it is no
# answer, so then only the lead-in is cut.
ANNOUNCES = re.compile(
    r"\b(said|says|wrote|writes|replied|replies|reply|answered|answers?|responded|responds|"
    r"responses?|returned|returns|generated|produced|outputs?|completions?)\b", re.I)
ASSISTANT_OPENER = re.compile(
    r"^(certainly|sure|of course|absolutely|great question|as an ai\b|i'd be happy|"
    r"i would be happy)\b", re.I)
QUOTE_MARKS = "\"\u201c\u2018"  # not "'", an apostrophe too ("'90s")
# After a "...:" lead-in, this many short lines without sentence punctuation are a quoted block.
SHORT_BLOCK = 3
SHORT_LINE_WORDS = 6
SENTENCE_END = re.compile(r"[.!?][\"'\u201d)*_]*$")
CODE_TOKEN = re.compile(r"^\s*(\$(?!\d)|>>>|\{|\[|import\b|def\b|curl\b)")
# A vendor heading ("OpenAI Response", "Small Model Responses (OpenAI)") starts a model's
# answer that runs to the next heading. The response word may be plural, and the model may
# be named before it or in a "(Vendor)" suffix after it. When those answers are over half
# the passage, under half is the author's own text and it is dropped.
HEADING_RESPONSE_WORDS = RESPONSE_WORDS | frozenset(
    "responses outputs answers replies completions".split())
VENDOR_SUFFIX = re.compile(r"^(.*\S)\s*\(([^()]+)\)$")
# Table text: share of lines with TABLE_CELL_WORDS words or fewer, and of mostly-digit lines.
# Cutting (writing and brand). A line is cut as code only on a sure sign: a NAME=value or
# shell line, a code keyword start, or a brace end ("{", "}") or "...;" with "=" in it; a
# wrapped prose line that ends in ";" or is indented stays. Inside a joined line, two or more
# NAME=value settings in a row, or a shell command run (see shell_runs), are cut.
CODE_START = re.compile(r"^\s*(def |class |import |from \S+ import |#include|\$ |```)")
CODE_END = re.compile(r"(^\s*[{}]|[{}]\s*$)")
ENV_RUN = re.compile(
    r"""(?<!\S)(?:(?:export\s+)?[A-Z][A-Z0-9_]+=(?:"[^"]*"|'[^']*'|\S*)(?:\s+|$)){2,}""")
# A token that ends a sentence or a label: what may come right before a marker or a command.
BOUNDARY = re.compile(r"[.!?:)][\"'\u201d\u2019]*$")
# A lead-in is the last sentence of its paragraph; "vs." and "e.g." end none.
SENTENCE_BREAK = re.compile(r"[.!?][\"'\u201d\u2019)\]]*\s+")
ABBREVIATIONS = frozenset("vs e.g i.e eg ie etc approx mr mrs ms dr st no".split())
MIN_REMAINDER_WORDS = 60  # as SHORT_DOC_WORDS in extract-documents.py: less is no passage
CUT_LABELS = {"model": "quoted model output", "code": "code", "orphan": "orphan lead-in"}
TABLE_CELL_WORDS = 3
TABLE_SHORT_SHARE = 0.4
TABLE_DIGIT_SHARE = 0.25
MIN_TABLE_LINES = 4


def body(path: Path) -> str:
    return path.read_text(encoding="utf-8").partition("\n")[2].strip()


def lines_of(text: str) -> list[str]:
    return [l for l in text.splitlines() if l.strip()]


def is_contact(line: str) -> bool:
    if CONTACT_LABEL.search(line):
        return True
    rest = CONTACT_ITEM.sub(" ", line)
    return rest != line and len(words(rest)) <= CONTACT_EXTRA_WORDS


def share(lines: list[str], hit) -> float:
    return sum(1 for l in lines if hit(l)) / len(lines) if lines else 0.0


def words(text: str) -> list[str]:
    return [w.lower() for w in WORD.findall(text)]


def is_broken(text: str) -> bool:
    lines = lines_of(text)
    if not lines:
        return True
    if share(lines, is_contact) >= SIGNATURE_SHARE:
        return True
    chars = [c for c in text if not c.isspace()]
    return chars.count("\ufffd") / len(chars) > MAX_REPLACEMENT_SHARE


def is_garbled(text: str) -> bool:
    """Mostly non-letters, or cut off mid-sentence and very short.

    Checked after the list and log rules, which also have few letters.
    """
    chars = [c for c in text if not c.isspace()]
    if sum(c.isalpha() for c in chars) / len(chars) < MIN_LETTER_SHARE:
        return True
    ws = text.split()
    last = ws[-1].lower().strip("\"'")
    return len(ws) < CUT_OFF_WORDS and (
        last.rstrip(",;:-\u2013\u2014(") != last or last in DANGLING)


def is_quoted(text: str) -> bool:
    lines = lines_of(text)
    quoted = 0
    forwarded = False
    for l in lines:
        if FORWARD_START.search(l):
            forwarded = True
        if forwarded or QUOTE.search(l) or BOILERPLATE.search(l) or HEADER.search(l):
            quoted += 1
    return bool(lines) and quoted / len(lines) >= MOSTLY


def is_structured(text: str) -> bool:
    lines = lines_of(text)
    n = sum(1 for l in lines if BULLET.search(l) or TABLE.search(l) or is_code(l) or LOG.search(l))
    return n >= 2 and n / len(lines) >= MOSTLY


def is_code(line: str) -> bool:
    """A code line, a NAME=value setting or a shell command (see ENV_LINE, SHELL_LINE)."""
    return bool(CODE.search(line) or ENV_LINE.match(line)) or is_shell(line)


def is_shell(line: str) -> bool:
    return (bool(SHELL_LINE.match(line)) and not SENTENCE_END.search(line.strip())
            and not any(w in FUNCTION_WORDS for w in words(line)))


def is_cut_code(line: str) -> bool:
    """A line sure enough to be code to cut it (see CODE_START, CODE_END)."""
    if ENV_LINE.match(line) or is_shell(line) or CODE_END.search(line):
        return True
    s = line.strip()
    if CODE_START.match(line) or (s.endswith(";") and "=" in s):
        # The keyword itself ("from", "class") may be an ordinary word; the rest may not.
        return not any(w in FUNCTION_WORDS for w in words(line)[1:])
    return False


def is_lead_in(line: str) -> bool:
    """A short line that introduces a model's answer (see MODEL_WORDS)."""
    line = line.strip().strip("#*_ ").strip()
    toks = line.split()
    if not toks or len(toks) > LEAD_IN_WORDS:
        return False
    if line.endswith(":"):
        return bool(MODEL_WORDS.search(line))
    *name, last = toks
    return last.lower() in RESPONSE_WORDS and is_model_name(name)


def is_model_name(name: list[str]) -> bool:
    """Capitalised words that hold a model or vendor name, or end in MODEL_KINDS."""
    return (bool(name) and all(t[0].isupper() and t.lower() not in FUNCTION_WORDS for t in name)
            and (name[-1].lower() in MODEL_KINDS
                 or any(t.lower() in MODEL_NAMES or t.lower().startswith("gpt") for t in name)))


def is_vendor_heading(line: str) -> bool:
    """A heading over a model's answer: "OpenAI Responses", "Small Model Responses (OpenAI)"."""
    line = line.strip().strip("#*_ ").strip()
    toks = line.split()
    if not toks or len(toks) > LEAD_IN_WORDS or line[-1] in ".:;,!?":
        return False
    m = VENDOR_SUFFIX.match(line)
    if m:
        head = m.group(1).split()
        return head[-1].lower() in HEADING_RESPONSE_WORDS and is_model_name(m.group(2).split())
    *name, last = toks
    return last.lower() in HEADING_RESPONSE_WORDS and is_model_name(name)


def marker(line: str) -> tuple[int, int] | None:
    """(start, end) of the first vendor heading inside a line ("... their responses. OpenAI
    Response Low latency ..."): capitalised words that name a model before a capitalised
    response word, or a "(Vendor)" after it. It starts the line or follows a BOUNDARY
    token, and the answer after it starts with a capital, a digit or a quote."""
    toks = [(m.start(), m.end(), m.group()) for m in re.finditer(r"\S+", line)]
    for i, (_, _, tok) in enumerate(toks):
        if tok.lower() not in HEADING_RESPONSE_WORDS or not tok[0].isupper():
            continue
        last = i
        if i + 1 < len(toks) and toks[i + 1][2].startswith("("):
            j = next((j for j in range(i + 1, min(i + 5, len(toks))) if toks[j][2].endswith(")")),
                     None)
            if j is not None and is_model_name(
                    " ".join(t for _, _, t in toks[i + 1:j + 1])[1:-1].split()):
                last = j
        k = i
        while (k > 0 and i - k < LEAD_IN_WORDS - 1 and toks[k - 1][2][0].isupper()
               and toks[k - 1][2].lower() not in FUNCTION_WORDS
               and not BOUNDARY.search(toks[k - 1][2])):
            k -= 1
        if last == i and not is_model_name([t for _, _, t in toks[k:i]]):
            continue
        if k > 0 and not BOUNDARY.search(toks[k - 1][2]):
            continue
        if last + 1 < len(toks) and not re.match(r"[A-Z0-9\"'\u201c\u2018*(]", toks[last + 1][2]):
            continue
        return toks[k][0], toks[last][1]
    return None


def marker_start(line: str) -> int | None:
    m = marker(line)
    return m[0] if m else None


def split_markers(text: str) -> list[str]:
    """The lines of text, with a vendor heading inside a line put on a line of its own."""
    out = []
    for line in text.splitlines():
        m = marker(line)
        if m and line[:m[0]].strip() + line[m[1]:].strip():
            out += [p for p in (line[:m[0]].rstrip(), line[m[0]:m[1]], line[m[1]:].strip()) if p]
        else:
            out.append(line)
    return out


def is_heading(line: str, alone: bool = False) -> bool:
    """A short title-case line, or a markdown heading: it ends a vendor heading's section.
    With alone (the line is its own paragraph), a sentence-case line is one too.

    A pdftotext line wrap, a bold "Label:" or a list item inside the answer is none.
    """
    if line.lstrip().startswith("#"):
        return True
    if BULLET.search(line):
        return False
    line = line.strip().strip("*_ ").strip()
    toks = line.split()
    if not toks or len(toks) > LEAD_IN_WORDS or line[-1] in ".:;," or "," in line:
        return False
    caps = [t for t in (t.lstrip("(\"'“") for t in toks) if t and t[0].isalpha()]
    if not caps or not caps[0][0].isupper():
        return False
    return alone or all(t[0].isupper() or t.lower() in FUNCTION_WORDS for t in caps)


def vendor_section_words(text: str) -> int:
    """Words under vendor headings (the headings too), each up to the next heading."""
    raw = split_markers(text)
    return sum(len(raw[k].split()) for k in vendor_lines(raw))


def vendor_lines(raw: list[str]) -> list[int]:
    """Indexes of the lines under vendor headings (the headings too)."""
    out, inside = [], False
    for k, l in enumerate(raw):
        if not l.strip():
            continue
        alone = (k == 0 or not raw[k - 1].strip()) and (k + 1 == len(raw) or not raw[k + 1].strip())
        if is_vendor_heading(l):
            inside = True
        elif is_heading(l, alone):
            inside = False
        if inside:
            out.append(k)
    return out


def lead_in_block(raw: list[str], k: int) -> list[int]:
    """Indexes of the block a lead-in at raw[k] introduces: the lines after it up to the
    next blank line, or the next paragraph when a blank line follows it."""
    j = k + 1
    if j < len(raw) and not raw[j].strip():
        while j < len(raw) and not raw[j].strip():
            j += 1
    block = []
    while j < len(raw) and raw[j].strip():
        block.append(j)
        j += 1
    return block


def marks_block(lead_in: str, block: list[str]) -> bool:
    """The lines after a lead-in are the model's (see ANNOUNCES)."""
    return bool(ANNOUNCES.search(lead_in)) or quoted_block(block)


def quoted_block(block: list[str]) -> bool:
    """A block that looks quoted: it opens with a quote mark or an assistant's opener
    ("Certainly!"), or has a "> " quote line, a code line or **bold** in it."""
    if not block:
        return False
    first = block[0].strip().lstrip("*_ ")
    return (first[:1] in QUOTE_MARKS or bool(ASSISTANT_OPENER.match(first))
            or any(QUOTE.search(l) or CODE_TOKEN.search(l) or is_cut_code(l) or "**" in l
                   for l in block))


def is_model_output(text: str) -> bool:
    """Quoted model output: the block after a lead-in (see lead_in_block and marks_block)
    is most of the passage; or a "...:" lead-in followed by a block of short lines; or
    answers under vendor headings are over half of it; or mostly code-like lines."""
    lines = lines_of(text)
    total = len(text.split())
    if sum(len(l.split()) for l in lines if CODE_TOKEN.search(l)) > total * MOSTLY:
        return True
    if vendor_section_words(text) > total * MOSTLY:
        return True
    raw = text.splitlines()
    for k, line in enumerate(raw):
        if not line.strip() or not is_lead_in(line):
            continue
        block = [raw[j] for j in lead_in_block(raw, k)]
        if sum(len(l.split()) for l in block) > total * MOSTLY and marks_block(line, block):
            return True
    for k, line in enumerate(lines):
        if not is_lead_in(line):
            continue
        block = lines[k + 1:k + 1 + SHORT_BLOCK]
        if (line.rstrip("*_ ").endswith(":") and len(block) == SHORT_BLOCK
                and all(len(l.split()) <= SHORT_LINE_WORDS and not SENTENCE_END.search(l.strip())
                        for l in block)):
            return True
    return False


def cut(text: str) -> tuple[str, Counter]:
    """(what is left of a passage, words cut per CUT_LABELS key). Model answers, code
    lines and code runs inside a line are cut, then the lead-ins they leave orphaned;
    a cut run of lines leaves a paragraph break."""
    raw = split_markers(text)
    kind: list[str | None] = [None] * len(raw)
    cuts: Counter = Counter()
    for k in vendor_lines(raw):
        kind[k] = "model"
    for k, line in enumerate(raw):
        if kind[k] is None and line.strip() and is_lead_in(line):
            block = lead_in_block(raw, k)
            if not marks_block(line, [raw[j] for j in block]):
                kind[k] = "orphan"
                continue
            for j in [k, *block]:
                kind[j] = kind[j] or "model"
    for k, line in enumerate(raw):
        if kind[k] is None and line.strip():
            if is_cut_code(line):
                kind[k] = "code"
            else:
                raw[k], n, orphan = cut_runs(line)
                cuts["code"] += n
                cuts["orphan"] += orphan
                if not raw[k].strip():
                    kind[k] = "code"
    for k, line in enumerate(raw):
        if kind[k]:
            cuts[kind[k]] += len(line.split())
    # Paragraphs of what is left; None stands for a cut run.
    paras: list[list[str] | None] = []
    for k, line in enumerate(raw):
        if kind[k]:
            if paras[-1:] != [None]:
                paras.append(None)
        elif not line.strip():
            if paras and paras[-1]:
                paras.append([])
        elif paras and paras[-1] is not None:
            paras[-1].append(line)
        else:
            paras.append([line])
    paras = [p for p in paras if p != []]
    # Right to left: a lead-in before a cut, the end, or another lead-in is an orphan.
    after_lead_in = True  # the end of the passage
    for i in range(len(paras) - 1, -1, -1):
        p = paras[i]
        if p is None:
            after_lead_in = True
            continue
        lead_in = p[-1].strip().strip("*_ ").endswith(":")
        if lead_in and after_lead_in:
            kept, n = drop_lead_in("\n".join(p))
            cuts["orphan"] += n
            paras[i] = kept.split("\n") if kept else []
            lead_in = not kept  # the sentences before it stay, and they end in no ":"
        after_lead_in = lead_in
    if not +cuts:
        return text, Counter()
    rest = "\n\n".join("\n".join(p) for p in paras if p)
    return rest.strip(), +cuts


def cut_runs(line: str) -> tuple[str, int, int]:
    """(line without its NAME=value and shell command runs, words cut, orphan lead-in words)."""
    spans = [m.span() for m in ENV_RUN.finditer(line)] + shell_runs(line)
    if not spans:
        return line, 0, 0
    n = orphan = 0
    for a, b in sorted(spans, reverse=True):
        n += len(line[a:b].split())
        before = line[:a].rstrip()
        if before.endswith(":"):
            before, o = drop_lead_in(before)
            orphan += o
        line = (before + " " + line[b:].lstrip()).strip()
    return line, n, orphan


def shell_runs(line: str) -> list[tuple[int, int]]:
    """Spans of shell commands inside a line: a command word after a BOUNDARY token (or with
    a path, URL or flag as its first argument), up to the next capitalised word, with at
    least one argument, no ordinary English word and no sentence end."""
    toks = [(m.start(), m.end(), m.group()) for m in re.finditer(r"\S+", line)]
    out, i = [], 0
    while i < len(toks):
        if toks[i][2] not in SHELL_COMMANDS or i + 1 == len(toks):
            i += 1
            continue
        arg = toks[i + 1][2]
        if not (i == 0 or BOUNDARY.search(toks[i - 1][2]) or arg.startswith("-")
                or re.search(r"\w[./]\w", arg)):
            i += 1
            continue
        j = i + 1
        while j < len(toks) and not toks[j][2][0].isupper():
            j += 1
        run = line[toks[i][0]:toks[j - 1][1]]
        if j - i >= 2 and not SENTENCE_END.search(run) and not any(
                w in FUNCTION_WORDS for w in words(run)):
            out.append((toks[i][0], toks[j - 1][1]))
            i = j
        else:
            i += 1
    return out


def drop_lead_in(text: str) -> tuple[str, int]:
    """(text without its last sentence, the words of that sentence). A title line over
    the lead-in stays ("Step 1. Checkout comparing-llm-api-performance" over "Clone the
    repository:"): a line with no ordinary word, or a title-case one, before a line
    that starts with a capital. A wrapped sentence goes whole."""
    start = 0
    for m in SENTENCE_BREAK.finditer(text):
        word = text[:m.start()].split()[-1].lower() if text[:m.start()].split() else ""
        if word.strip("(\"'") not in ABBREVIATIONS:
            start = m.end()
    for m in re.finditer(r"\n", text):
        head, rest = text[start:m.start()], text[m.end():].lstrip()
        if (m.start() > start and head.strip() and rest[:1].isupper()
                and (not any(w in FUNCTION_WORDS for w in words(head)) or is_heading(head))):
            start = m.end()
    return text[:start].rstrip(), len(text[start:].split())


def cut_note(cuts: Counter) -> str:
    """The cut column: "quoted model output 87 words; code 54 words" (empty if nothing)."""
    return "; ".join(f"{label} {cuts[k]} word{'' if cuts[k] == 1 else 's'}"
                     for k, label in CUT_LABELS.items() if cuts[k])


def is_table(text: str) -> bool:
    """One cell per line: mostly short lines, and many of them numbers."""
    lines = lines_of(text)
    if len(lines) < MIN_TABLE_LINES:
        return False
    short = share(lines, lambda l: len(l.split()) <= TABLE_CELL_WORDS)
    digits = share(lines, lambda l: sum(c.isdigit() for c in l) > len(l.replace(" ", "")) / 2)
    return short > TABLE_SHORT_SHARE and digits >= TABLE_DIGIT_SHARE


def shingles(text: str) -> set[int]:
    ws = words(text)
    grams = (hash(tuple(ws[i:i + NGRAM])) for i in range(len(ws) - NGRAM + 1))
    out: set[int] = set()
    for g in grams:
        out.add(g)
        if len(out) >= MAX_SHINGLES:
            break
    return out


def find_duplicates(texts: list[str], stats: dict | None = None) -> set[int]:
    """Indexes of samples that share most word 5-grams with another sample.

    Work is bounded: at most MAX_SHINGLES shingles per sample, and each
    shingle remembers at most BUCKET samples, so a sample is compared with at
    most BUCKET other samples per shingle however large the set is.
    """
    index: dict[int, list[int]] = {}
    shingles_of: dict[int, set[int]] = {}
    dups: set[int] = set()
    stats = stats if stats is not None else {}
    stats.update(max_candidates=0, max_shingles=0)
    for i, text in enumerate(texts):
        sh = shingles(text)
        stats["max_shingles"] = max(stats["max_shingles"], len(sh))
        if len(sh) < MIN_SHINGLES:
            continue
        seen: Counter = Counter()
        for g in sh:
            for j in index.get(g, ()):
                seen[j] += 1
        stats["max_candidates"] = max(stats["max_candidates"], len(seen))
        for j, n in seen.items():
            if n / min(len(sh), len(shingles_of[j])) >= DUPLICATE_OVERLAP:
                dups.update((i, j))
        for g in sh:
            bucket = index.setdefault(g, [])
            if len(bucket) < BUCKET:
                bucket.append(i)
        shingles_of[i] = sh
    return dups


def language_share(text: str, language: str) -> float:
    ws, common = words(text), LANGUAGE_WORDS[language]
    return sum(w in common for w in ws) / len(ws) if ws else 0.0


def author_language(texts: list[str]) -> str | None:
    """The language with the highest median share over the samples long enough to judge.

    None when no language reaches LANGUAGE_AUTHOR_SHARE, and then no sample is
    dropped for its language.
    """
    long = [t for t in texts if len(words(t)) >= MIN_LANGUAGE_WORDS]
    if not long:
        return None
    medians = {}
    for language in LANGUAGE_WORDS:
        shares = sorted(language_share(t, language) for t in long)
        medians[language] = shares[len(shares) // 2]
    best = max(medians, key=medians.get)  # the first, English, on a tie
    return best if medians[best] >= LANGUAGE_AUTHOR_SHARE else None


def signoff_name(text: str) -> str:
    """The name on the line after a closing such as "Thanks," ("" if none)."""
    lines = [l.strip() for l in lines_of(text)]
    for k in range(len(lines) - 2, -1, -1):
        if CLOSINGS.match(lines[k]):
            nxt = lines[k + 1]
            return nxt if NAME_LINE.match(nxt) and len(nxt) <= 40 else ""
    return ""


def other_name(text: str, author: str) -> bool:
    """True when the sign-off name clearly is not the author's."""
    return not_author(signoff_name(text), author)


def byline_name(text: str) -> str:
    """The name in a byline on the first or last line ("" if none)."""
    lines = [l.strip() for l in lines_of(text)]
    for line in lines[:1] + lines[-1:]:
        m = BYLINE.match(line)
        name = m.group(1).strip(" *_") if m else ""
        if (NAME_LINE.match(name) and len(name) <= 40
                and not any(t.lower() in DATE_WORDS for t in name.replace(".", " ").split())):
            return name
    return ""


def not_author(name: str, author: str) -> bool:
    """True when name clearly is a name, and not the author's."""
    mine = author.lower().replace(".", " ").split()
    if not name or not mine:
        return False
    # A name is capitalised and has no ordinary word in it ("Will follow up" is not one).
    toks = name.replace(".", " ").split()
    if any(not t[0].isupper() or t.lower() in FUNCTION_WORDS or t.lower() in COMMON_NON_NAMES
           for t in toks if t.lower() not in mine and not any(a.startswith(t.lower()) for a in mine)):
        return False
    for tok in name.lower().replace(".", " ").split():
        if any(a.startswith(tok) or tok.startswith(a) for a in mine):
            return False
    return True


def score(text: str) -> int:
    n = len(words(text))
    paras = sum(1 for p in re.split(r"\n\s*\n", text) if len(words(p)) >= 8)
    s = 1 if n < 15 else 2 if n < 50 else 3 if n < 100 else 4 if n < 200 else 5
    if s > 2 and paras <= 1:
        s -= 1
    elif s < 5 and paras >= 3 and n >= 60:
        s += 1
    return max(1, min(5, s))


def review(texts: list[str], author: str = "", mode: str = "email") -> list[dict]:
    """Return one {verdict, score, reason} dict per text, in order."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}")
    email = mode == "email"
    dups = find_duplicates(texts)
    language = author_language(texts)

    def judge(t: str, i: int) -> str:
        if is_broken(t):
            return "broken extraction"
        if email and is_quoted(t):
            return "quoted or forwarded text"
        if is_structured(t):
            return "list, table, code or log"
        if not email and is_table(t):
            return "table or numbers"
        if not email and is_model_output(t):
            return "quoted model output"
        if is_garbled(t):
            return "broken extraction"
        if i in dups:
            return "form letter"
        if (language and len(words(t)) >= MIN_LANGUAGE_WORDS
                and language_share(t, language) < LANGUAGE_SHARE):
            return "not in the author's language"
        if email and other_name(t, author):
            return "written in another name"
        if mode == "writing" and not_author(byline_name(t), author):
            return "written by someone else"
        return KEEP_REASON

    out = []
    for i, t in enumerate(texts):
        reason, text, cuts = judge(t, i), t, Counter()
        if reason == KEEP_REASON and not email:
            text, cuts = cut(t)
            if (cuts["model"] or cuts["code"]) and len(text.split()) < MIN_REMAINDER_WORDS:
                reason = ("quoted model output" if cuts["model"] >= cuts["code"]
                          else "list, table, code or log")
            elif cuts:
                reason = judge(text, i)
        out.append({"verdict": "KEEP" if reason == KEEP_REASON else "DROP",
                    "score": score(text), "reason": reason, CUT_COLUMN: cut_note(cuts),
                    "text": text})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--samples", type=Path, default=Path("samples"))
    ap.add_argument("--author", default="",
                    help="the author's name; a sign-off with a clearly different name is dropped "
                         "(email), or a byline with one (writing); unused in brand")
    ap.add_argument("--mode", choices=MODES, default="email",
                    help="where the samples came from: an email export (default), the "
                         "author's own documents, or a brand's documents")
    args = ap.parse_args()

    index = args.samples / "index.csv"
    with open(index, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    if not rows:
        sys.exit(f"error: no samples in {index}")

    texts = [body(args.samples / r["file"]) for r in rows]
    verdicts = review(texts, args.author, args.mode)

    columns = COLUMNS + ([] if args.mode == "email" else [CUT_COLUMN])
    fields += [c for c in columns if c not in fields]
    cut_files = []
    for r, v, t in zip(rows, verdicts, texts):
        if v["verdict"] == "KEEP" and v["text"] != t:
            cut_files.append((args.samples / r["file"], v["text"]))
            if "words" in r:
                r["words"] = str(len(v["text"].split()))
        elif not v[CUT_COLUMN] and r.get(CUT_COLUMN):
            v[CUT_COLUMN] = r[CUT_COLUMN]  # a file cut on an earlier run
    for path, text in cut_files:
        title = path.read_text(encoding="utf-8").partition("\n")[0]
        replace_file(path, f"{title}\n\n{text}\n")
    rows = [{**r, **{c: v[c] for c in columns}} for r, v in zip(rows, verdicts)]
    replace_file(index, rows=rows, fields=fields)
    keep = sum(v["verdict"] == "KEEP" for v in verdicts)
    print(f"reviewed {len(rows)} samples: {keep} KEEP, {len(rows) - keep} DROP")
    drops = Counter(v["reason"] for v in verdicts if v["verdict"] == "DROP")
    for reason, n in drops.most_common():
        print(f"  dropped {n}: {reason}")
    if args.mode in FLOORS:
        check_coverage(args.mode, keep, documents(rows, verdicts))


def replace_file(path: Path, text: str = "", rows: list[dict] | None = None,
                 fields: list[str] | None = None) -> None:
    """Write text, or rows as CSV, to a temp file beside path, then move it over path."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.stem + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            if rows is None:
                f.write(text)
            else:
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                w.writerows(rows)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def documents(rows: list[dict], verdicts: list[dict]) -> int:
    """Distinct non-empty source values among the KEEP rows (0 without the column)."""
    return len({r.get("source") for r, v in zip(rows, verdicts)
                if v["verdict"] == "KEEP" and r.get("source")})


def check_coverage(mode: str, keep: int, docs: int) -> None:
    """Print the coverage: line; exit FLOOR_EXIT below the mode's floor."""
    print(f"coverage: {keep} KEEP passages from {docs} document{'' if docs == 1 else 's'}")
    (floor, floor_docs), (least, least_docs) = FLOORS[mode], MINIMUMS[mode]
    if keep < floor or docs < floor_docs:
        need = f"{floor} KEEP passages" + (f" from {floor_docs} documents" if floor_docs else "")
        print(f"below the floor for {mode}: a profile needs at least {need}; "
              f"add more documents and run the extract again", file=sys.stderr)
        sys.exit(FLOOR_EXIT)
    if keep < least or docs < least_docs:
        print(f"below the minimum for {mode}: {least} KEEP passages from {least_docs} documents "
              f"give a stronger profile; this one will be weaker")


if __name__ == "__main__":
    main()
