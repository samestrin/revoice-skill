# llm-api-performance

Which Would I Avoid?
Goose AI is a commercial product that while it comes with a $9.99 credit does require a
credit card when you sign up. I don’t mind spending money for a quality product, however
the results provided by Goose AI were lacking to say the least. This is true regardless of
the model used. (I’ve provided all collected responses a bit further in this article.)
Why Is jamba-instruct Tested Twice?
At the time of publishing AI21 Studio had only one model available, jamba-instruct. I was
curious about the performance of this model, because AI21 opted to not offer a
smaller/faster model similar to most other LLM providers. Overall, it performed well,
even beating OpenAI davinci-002.
Reproducing My Comparison
If you’d like to reproduce my test, checkout the comparing-llm-api-performance
repository, which contains my original testLLMPerformance.js script and follow the
directions below.
Step 1. Checkout comparing-llm-api-performance
Clone the repository:
git clone https://github.com/samestrin/comparing-llm-api-performance.git
cd comparing-llm-api-performance
Step 2. Install the required npm packages:
npm install llm-interface ping cli-progress dotenv
Step 3. Create your .env File
To run the script, you must first create an .ENV file with valid API keys, there is an
included ENV file you can use as a template. (I’ve provided links below if you don’t have
API keys.)
AI21_API_KEY=
ANTHROPIC_API_KEY=
CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_API_KEY=
FIREWORKSAI_API_KEY=
GEMINI_API_KEY=
GOOSEAI_API_KEY=
GROQ_API_KEY=
HUGGINGFACE_API_KEY=
MISTRALAI_API_KEY=
OPENAI_API_KEY=
PERPLEXITY_API_KEY=
REKAAI_API_KEY=
Step 4. Run The Tests
node testLLMPerformance.js
Step 5. Review The Results
