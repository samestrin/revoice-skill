# llm-api-performance

LLM API: Small Model Average Response Times (ms)

Small Model Average Response Times (ms) Results Table

The following table shows the small model average response time. The second column displays the llm-interface small models.

Provider

Small Model

Avg Response Time (ms)

Std Deviation (ms)

Hugging Face

Phi-3-mini-4k-instruct

117.052

92.733

Groq

gemma-7b-it

269.841

100.261

Fireworks AI

phi-3-mini-128k-instruct

802.078

186.151

Anthropic

claude-3-haiku-20240307

1534.910

167.900

Cohere

command-light

1668.845

61.123

Google Gemini

gemini-1.5-flash

1660.029

154.032

AI21 Studio

jamba-instruct

2403.589

253.886

OpenAI

davinci-002

2713.774

305.483

Perplexity

llama-3-sonar-small-32k-online

3182.196

182.791

Mistral AI

mistral-small-latest

3509.565

164.051

Reka AI

reka-edge

8008.077

200.714

Cloudflare AI

tinyllama-1.1b-chat-v1.0

10188.783

375.586

Goose AI

gpt-neo-125m

13673.527

216.091

Evaluating the small model test results, the initial pack leaders had some downward movement: OpenAI had significant slippage, moving from 1st to 8th; Anthropic had minor slippage, down from 3rd to 4th, and Cohere went from 2nd to 5th.

The new leaders are Hugging Face, Groq, and Fireworks AI. Considering the models used by the pack leaders, Hugging Face had the smallest model, Groq had the largest, and Fireworks AI is in the middle. How fast are the leaders? Both Hugging Face and Groq responded in less than 300 ms, and Fireworks AI responded in less than a second.

The Hugging Face model, “Phi-3-mini-4k-instruct,” is a smaller-scale language model from the Phi-3 family with approximately 3 billion parameters, optimized for instructional tasks, and designed to handle a context length of up to 4,000 tokens. Groq’s “gemma-7b-it” is a medium-sized model with 7 billion parameters, tailored for general-purpose tasks with a specific focus on processing and understanding Italian. Lastly, the Fireworks AI model, “phi-3-mini-128k-instruct,” is an extensive version of the Phi-3 series with approximately 3 billion parameters, designed for instruction-based tasks but supporting a significantly larger context window of up to 128,000 tokens.

That’s why it’s important to note that this test does not compare equivalent models. I used small models to aim for the fastest response times, but models can vary significantly in size and fine-tuning. Consequently, this comparison is somewhat like comparing apples and oranges. However, to ensure a more precise assessment, I plan to release an article in the future that examines LLM API performance using the same model (where possible), providing a more accurate comparison.
