# llm-api-performance

2 Hugging Face showed an overall low average response time and high consistency across model sizes but did not rank highly for content quality. It had a combined average latency of 17.564 ms, a combined average response time of 102.03 ms, and a combined standard deviation of 47.392 ms.

3 Groq provided reliable and moderate latency and response times for both small and large models but also did not rank highly for content quality. It had a combined average latency of 20.364 ms, a combined average response time of 255.159 ms, and a combined standard deviation of 78.985 ms.

In conclusion, I rank Google Gemini as the top LLM API provider due to its combination of low latency, consistent performance across model sizes, and high-quality responses. Hugging Face is second, offering near real-time responses, high consistency, but comes with strings. Groq is third, providing reliable latency and ultra fast response times. However, OpenAI, Claude, and Google Gemini did not rank the responses from Hugging Face and Groq highly.

The Real Winner?

Developers! Why? It’s simple: the fastest LLM API providers in my test offer free API access. This means you can start building your next AI application without additional expenses. (If you still need to get your free API keys, don’t worry, I’ve provided links below.)

Which Would I Avoid?

Goose AI is a commercial product that while it comes with a $9.99 credit does require a credit card when you sign up. I don’t mind spending money for a quality product, however the results provided by Goose AI were lacking to say the least. This is true regardless of the model used. (I’ve provided all collected responses a bit further in this article.)

Why Is jamba-instruct Tested Twice?

At the time of publishing AI21 Studio had only one model available, jamba-instruct. I was curious about the performance of this model, because AI21 opted to not offer a smaller/faster model similar to most other LLM providers. Overall, it performed well, even beating OpenAI davinci-002.

Reproducing My Comparison

If you’d like to reproduce my test, checkout the comparing-llm-api-performance repository, which contains my original testLLMPerformance.js script and follow the directions below.

That’s why it’s important to note that this test does not compare equivalent models. I used small models to aim for the fastest response times, but models can vary significantly in size and fine-tuning. Consequently, this comparison is somewhat like comparing apples and oranges. However, to ensure a more precise assessment, I plan to release an article in the future that examines LLM API performance using the same model (where possible), providing a more accurate comparison.

That being said, to evaluate the quality of the responses, I used OpenAI, Claude, and Google Gemini. Then I identified the best responses by consensus.

To accomplish this, I simply uploaded the two markdown files generated and supplied the following prompt: “I asked 13 LLMs for a response to the prompt ‘Explain the importance of low latency LLMs.’ Evaluate each file individually; do not interrelate them. Rank the top 3 and explain why? Respond in one paragraph for each file. Repeat for each file.”
