# Comparing 13 LLM Providers API Performance with Node.js: Latency and Response Times Across Models - DEV Community

Why? Latency measures the initial delay in network communication, which is crucial for ensuring quick interactions. Average response time indicates how fast a provider can process and return a response, while the standard deviation measures the consistency of their performance. Quality of responses ensures that the information provided meets the required standards and relevance.

That's why it's important to note that this test does not compare equivalent models. I used small models to aim for the fastest response times, but models can vary significantly in size and fine-tuning. Consequently, this comparison is somewhat like comparing apples and oranges. However, to ensure a more precise assessment, I plan to release an article in the future that examines LLM API performance using the same model (where possible), providing a more accurate comparison.

Ranked by average response time, average latency.

Hugging Face had an average latency of 17.564 ms, an average response time of 117.052 ms, a standard deviation of 92.733 ms, and was not ranked highly for content quality.

Groq had an average latency of 20.364 ms, an average response time of 269.841 ms, a standard deviation of 100.261 ms, and was not ranked highly for content quality.

Google Gemini had an average latency of 17.044 ms, an average response time of 1660.029 ms, a standard deviation of 154.032 ms, and produced high-quality responses.

Ranked by average response time, average latency.

Hugging Face exhibited an average latency of 17.564 ms, an average response time of 87.007 ms, a standard deviation of 2.051 ms, and was not ranked highly for content quality.

Groq had an average latency of 20.364 ms, an average response time of 240.477 ms, a standard deviation of 57.709 ms, and was not ranked highly for content quality.

Google Gemini had an average latency of 17.044 ms, an average response time of 1667.225 ms, a standard deviation of 134.025 ms, and produced high-quality responses.

Ranked by quality of content, average response time, average latency.

Google Gemini demonstrated remarkable consistency across model sizes, maintained low latency, and produced high-quality responses, with a combined average latency of 17.044 ms, a combined average response time of 1663.627 ms, and a combined standard deviation of 144.0285 ms.

Hugging Face showed an overall low average response time and high consistency across model sizes but did not rank highly for content quality. It had a combined average latency of 17.564 ms, a combined average response time of 102.03 ms, and a combined standard deviation of 47.392 ms.

Groq provided reliable and moderate latency and response times for both small and large models but also did not rank highly for content quality. It had a combined average latency of 20.364 ms, a combined average response time of 255.159 ms, and a combined standard deviation of 78.985 ms.

In conclusion, I rank Google Gemini as the top LLM API provider due to its combination of low latency, consistent performance across model sizes, and high-quality responses. Hugging Face is second, offering near real-time responses, high consistency, but comes with strings. Groq is third, providing reliable latency and ultra fast response times. However, OpenAI, Claude, and Google Gemini did not rank the responses from Hugging Face and Groq highly.

Reviewing the actual responses does provide value. It's important to understand the quality of the responses. For example, Goose AI is a product I would avoid even if it came out first in performance. Why? Just skip down to their responses.
