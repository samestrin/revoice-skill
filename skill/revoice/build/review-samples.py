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
code or log lines; a near-duplicate form letter within the set; not in the
author's usual language; or signed with a clearly different name than --author.
score is 1-5 from prose length and paragraph structure. reason is one fixed
label (see REASONS), never a quote from the email.

--mode says where the samples came from (default email). For passages from
documents (extract-documents.py), writing and brand turn the email rules off:
quoted, forwarded and header lines, unsubscribe boilerplate, and sign-off names.
writing drops a passage whose first or
last line is a byline ("By <Name>") naming someone other than --author; brand
keeps every author. Both also drop quoted model output (a lead-in naming a model,
a prompt or a response, then the answer; or mostly code-like lines) and table
text (mostly short lines, many of them numbers). Both print a coverage: line (KEEP
passages, and the distinct source values among them), warn below the minimum in
MINIMUMS, and exit with status 3 below the floor in FLOORS, after index.csv is
written so the verdicts can be read.

index.csv is replaced only after every sample was judged, so a failed run
leaves it as it was. A rerun reviews every sample again.
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
# Response"). The bare words output, response and answer are no model signal ("Incident
# Response", "The short answer:"); vendor names only count before a response word, so
# "Groq pricing:" or "Our AI roadmap:" is not a lead-in.
MODEL_WORDS = re.compile(
    r"\b(chatgpt|claude|gpt[\w.-]*|gemini|llms?|the model|the prompt|the ai|"
    r"(model|assistant|bot|ai)(['\u2019]s)? (response|output|answer|reply|completion))\b", re.I)
MODEL_NAMES = frozenset(
    "chatgpt claude gemini bard llm llama mistral mixtral openai anthropic cohere groq grok "
    "ai21 jamba deepseek qwen copilot perplexity ai model assistant bot chatbot".split())
RESPONSE_WORDS = frozenset("response output answer reply completion".split())
LEAD_IN_WORDS = 8  # a longer line ending in ":" is a sentence, not a lead-in
# After a "...:" lead-in, this many short lines without sentence punctuation are a quoted block.
SHORT_BLOCK = 3
SHORT_LINE_WORDS = 6
SENTENCE_END = re.compile(r"[.!?][\"'\u201d)*_]*$")
CODE_TOKEN = re.compile(r"^\s*(\$(?!\d)|>>>|\{|\[|import\b|def\b|curl\b)")
# Table text: share of lines with TABLE_CELL_WORDS words or fewer, and of mostly-digit lines.
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
    n = sum(1 for l in lines if BULLET.search(l) or TABLE.search(l) or CODE.search(l) or LOG.search(l))
    return n >= 2 and n / len(lines) >= MOSTLY


def is_lead_in(line: str) -> bool:
    """A short line that introduces a model's answer (see MODEL_WORDS)."""
    line = line.strip().strip("#*_ ").strip()
    toks = line.split()
    if not toks or len(toks) > LEAD_IN_WORDS:
        return False
    if line.endswith(":"):
        return bool(MODEL_WORDS.search(line))
    *name, last = toks
    return (last.lower() in RESPONSE_WORDS and bool(name)
            and all(t[0].isupper() and t.lower() not in FUNCTION_WORDS for t in name)
            and any(t.lower() in MODEL_NAMES or t.lower().startswith("gpt") for t in name))


def is_model_output(text: str) -> bool:
    """Quoted model output: after a lead-in, the answer is most of the passage; or a
    "...:" lead-in followed by a block of short lines; or mostly code-like lines."""
    lines = lines_of(text)
    total = len(text.split())
    if sum(len(l.split()) for l in lines if CODE_TOKEN.search(l)) > total * MOSTLY:
        return True
    for k, line in enumerate(lines):
        if not is_lead_in(line):
            continue
        if sum(len(l.split()) for l in lines[k + 1:]) > total * MOSTLY:
            return True
        block = lines[k + 1:k + 1 + SHORT_BLOCK]
        if (line.rstrip("*_ ").endswith(":") and len(block) == SHORT_BLOCK
                and all(len(l.split()) <= SHORT_LINE_WORDS and not SENTENCE_END.search(l.strip())
                        for l in block)):
            return True
    return False


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
    out = []
    for i, t in enumerate(texts):
        if is_broken(t):
            reason = "broken extraction"
        elif email and is_quoted(t):
            reason = "quoted or forwarded text"
        elif is_structured(t):
            reason = "list, table, code or log"
        elif not email and is_table(t):
            reason = "table or numbers"
        elif not email and is_model_output(t):
            reason = "quoted model output"
        elif is_garbled(t):
            reason = "broken extraction"
        elif i in dups:
            reason = "form letter"
        elif (language and len(words(t)) >= MIN_LANGUAGE_WORDS
              and language_share(t, language) < LANGUAGE_SHARE):
            reason = "not in the author's language"
        elif email and other_name(t, author):
            reason = "written in another name"
        elif mode == "writing" and not_author(byline_name(t), author):
            reason = "written by someone else"
        else:
            reason = KEEP_REASON
        out.append({"verdict": "KEEP" if reason == KEEP_REASON else "DROP",
                    "score": score(t), "reason": reason})
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

    verdicts = review([body(args.samples / r["file"]) for r in rows], args.author, args.mode)

    fields += [c for c in COLUMNS if c not in fields]
    fd, tmp = tempfile.mkstemp(dir=args.samples, prefix="index.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows({**r, **v} for r, v in zip(rows, verdicts))
        os.replace(tmp, index)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    keep = sum(v["verdict"] == "KEEP" for v in verdicts)
    print(f"reviewed {len(rows)} samples: {keep} KEEP, {len(rows) - keep} DROP")
    drops = Counter(v["reason"] for v in verdicts if v["verdict"] == "DROP")
    for reason, n in drops.most_common():
        print(f"  dropped {n}: {reason}")
    if args.mode in FLOORS:
        check_coverage(args.mode, keep, documents(rows, verdicts))


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
