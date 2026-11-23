# llm-api-performance

Getting Started

To run the evaluation yourself, clone the repository and install the
dependencies:
git clone https://github.com/samestrin/llm-api-performance-evaluation.git
cd llm-api-performance-evaluation
npm install
Then create a .env file in the project root with an API key for each provider:
AI21_API_KEY=
ANTHROPIC_API_KEY=
CLOUDFLARE_API_KEY=
COHERE_API_KEY=
FIREWORKS_API_KEY=
GEMINI_API_KEY=
GOOSE_API_KEY=
GROQ_API_KEY=
HUGGINGFACE_API_KEY=
MISTRAL_API_KEY=
OPENAI_API_KEY=
PERPLEXITY_API_KEY=
REKA_API_KEY=
Run the test:
node testLatency.js
