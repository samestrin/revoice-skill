# Real-run fixtures (Epic 19, EST-7833)

Short excerpts from the operator's real 0.3.0 end-to-end run, unpacked from
`rv-e2e-evidence.tgz` attached to EST-7827 (sha256
`b2c86d150d203f356b1710511a0786f0dcbc6b70f58cf6bb1ef97a9cee9df262`). The
articles are the owner's own published dev.to posts; the brand page is
estringroup.co. Every file is an excerpt of at most 600 words, never a whole
sample set, never `voice-profile.json`, never a folder named `samples/`.
`test_real_run_fixtures.py` guards those limits. Load them with
`_load.real_run(name)` / `_load.real_run_body(name)`.

The run read 5 sources: three dev.to articles as URLs, plus article 1
("Comparing 13 LLM Providers API Performance with Node.js") also saved as
`llm-api-performance.pdf` and `llm-api-performance.docx`.

## (a) Normal prose, two passages per article

- `prose_comparing13_a.md`, `prose_comparing13_b.md` — from the URL copy of
  "Comparing 13 LLM Providers…" (samples `_02_481d51`, `_06_1fd6aa`).
- `prose_72faster_a.md`, `prose_72faster_b.md` — "72% Faster AI Workflows…"
  (samples `_01_7279c5`, `_02_f70c47`).
- `prose_llmenv_a.md`, `prose_llmenv_b.md` — "Stop Juggling API Keys: Meet
  llm-env…" (samples `_01_a1db93`, `_02_746fc5`).

All six are KEEP, score 5, "own writing" in the real run. Titles keep the
" - DEV Community" suffix exactly as the reader wrote it (bug 8).

## (b) Quoted LLM output as the PDF and DOCX text carries it (bug 2)

- `llm_output_docx_a.md` — AI21 Studio + Anthropic responses
  (DOCX sample `_15_a8a11e`, DROP "list, table, code or log" in the run).
- `llm_output_docx_b.md` — Cohere + Fireworks AI + Google Gemini responses
  (DOCX sample `_16_c34fbc`, KEEP 5 in the run — the bug).
- `llm_output_pdf_a.md` — Google Gemini + Goose AI + Groq responses, with
  pdftotext's hard line wraps (PDF sample `_16_38b8ca`, KEEP 5 — the bug).

F1 (EST-8141), whole samples: `llm_output_docx_c.md` (`_05_9b359e`) and
`llm_output_docx_d.md` (`_06_5d3e37`), evaluations under headings like
`Small Model Responses (OpenAI)`, KEEP on 9ed1577 (the bug);
`llm_output_pdf_b.md` (`_11_dd3091`), vendor responses, already DROP.

## (c) The one-number-per-line table (bug 6)

`table_docx_numbers.md` — DOCX sample `_03_0439f8` whole: the small-model
results table, one cell per line, KEEP score 5 in the run.

## (d) Icon fonts and the terminal widget (bug 5)

`brand_icons_widgets.html` — a minimal reconstruction, not a verbatim page:
the evidence holds extracted text only, no raw HTML. It reproduces exactly
what the real brand samples show (`arrow_forward`, `hub`, `smart_toy`,
`verified_user`, `lock`, `public` in `material-symbols-outlined` spans, and
the `estrin-lab :: status` widget whose lines start with `>`), plus two
genuine prose paragraphs that must survive. On main, `extract-documents.py`
keeps every icon word and the widget lines as prose.

## (e) Three copies of one article, with the straddling passage (bugs 3, 4)

- `copy_article_html.md` — the URL copy's text (title header included).
- `copy_article_pdf.txt` — pdftotext text, hard wraps kept.
- `copy_article_docx.md` — the Word copy's text (curly quotes, `#` title).

Each holds about four trimmed passages. The ranked-results block in the HTML
copy is the duplicated straddling passage: its first part (through "Google
Gemini demonstrated … 144.0285 ms.") is in the PDF copy, its last part
("Hugging Face showed …" on) is in the DOCX copy. Measured on main with
`extract-documents.py` at e945f47, all three copies together:

- kept passages: pdf#1 411w, html#1 363w, docx#1 359w, docx#2 160w;
- html#1's best pairwise 5-gram share is 0.47 (< `DUPLICATE_SHARE` 0.5, so
  main keeps it) but 0.70 of its 5-grams lie in the union of the other kept
  passages — the straddle bug 4;
- html#2 and pdf#2 are dropped as duplicates of docx#1 (0.76 and 1.00), so
  all three sources cluster into one document once T2 groups them;
- docx#2 (genuine prose) stays at union share 0.45, below the threshold;
- the result is identical with the inputs in reverse order.
