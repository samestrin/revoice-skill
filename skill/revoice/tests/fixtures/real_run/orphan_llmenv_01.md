# Stop Juggling API Keys: Meet llm-env — One Command, Any LLM Provider

TL;DR

If you bounce between multiple AI providers like OpenAI, Gemini, Groq, Cerebras, or local LLMs—and you want an OpenAI-compatible workflow—this tiny Bash environment helper is for you. It simplifies LLM provider switching, keeps your API keys organized and secure, and boosts developer productivity.

llm-env is a tiny Bash script that standardizes your Bash environment around the familiar OPENAI_* variables so OpenAI-compatible tools "just work" across providers.

Result: Your existing AI tools (aider, llm, qwen-code, LiteLLM) immediately pick up the right API key, base URL, and model. No manual edits, no copy/paste, no restarts.

Multiple providers, each with different endpoints and auth

OPENAI_* has become the de facto standard—but not every provider uses those names

You end up editing ~/.bashrc or ~/.zshrc over and over

Context switching kills flow, and small mistakes cause mysterious 401s/404s

Sarah, an ML engineer at a fintech startup, prototypes using the Gemini free tier, uses Groq for CI speed, and ships with OpenAI in production. With llm-env, she changes providers with a single command and avoids configuration drift across environments.

The result: faster cycles and fewer “why is this failing?” moments.

A single script that:

Centralizes provider configuration in one place (~/.config/llm-env/llm-env.conf)

Normalizes every provider to OPENAI_* environment variables

Let's you switch providers instantly with llm-env set <provider>

Includes a built-in connectivity test so you know your provider works

Before vs. After:

Common Commands:

Quickly install llm-env with:

Add your keys to your shell profile (examples):

Start using llm-env right away:

llm-env ships with 20 popular providers ready to go and works with any OpenAI‑compatible API. You can easily add your own providers by editing a single config file.

Cloud providers (OpenAI, Groq, Gemini, Cerebras, xAI, and more)

OpenRouter presets (including free options)

Self‑hosted setups (Ollama, LM Studio, vLLM)

Most AI tools already expect these variables:

OPENAI_API_KEY

OPENAI_BASE_URL

OPENAI_MODEL

llm-env embraces that reality. It updates those variables for you—correctly—no matter the provider. Your tools stay unchanged; your provider becomes a one‑line decision.

Keys are masked in output (e.g., ••••15x0) to keep secrets safe on screen and in screenshots.

Security is a top priority:

Keys live in environment variables—never written to config files
