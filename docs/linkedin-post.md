📌 Post 2/4 — NextLeap PM Fellowship

---

I built an AI assistant that answers HDFC Mutual Fund questions — and refuses to give investment advice. Here's why the refusal was harder to build than the answers. 🧵

---

The brief for Milestone 1 was clear: facts only, no advice, always cite your source.

But most AI systems fail exactly here — they hallucinate numbers, give confident wrong answers, or worse, start sounding like a financial adviser.

So I built a **RAG pipeline** that never answers from memory.

Every response is grounded in real data scraped daily from Groww — chunked, embedded, and retrieved from a vector store before the LLM ever sees the question.

---

🎥 From the demo:

✅ "What is the expense ratio of HDFC Large Cap Fund?" → 1.03%
✅ "NAV of HDFC ELSS Tax Saver Fund?" → ₹1488.922 (as of 2026-04-19)
✅ "Who is the fund manager of HDFC Focused Fund?" → Amit Ganatra & Dhruv Muchhal
✅ "Tell me about HDFC Mid-Cap Fund" → Groww rating 5/5, exit load 1%, NAV ₹220.058
❌ "Can you suggest a scheme to invest?" → Politely refused, redirected to AMFI
🔒 "My PAN is OODFS2600R..." → PII detected, blocked instantly

The last two are my favourite — that's where most assistants fail.

---

🎨 I also designed the UI to feel HDFC-native — white, minimal, clean. Because in financial products, design is trust.

One small detail I'm proud of: type "HDFC L" in the chat box and it ghost-suggests "HDFC Large Cap Fund Direct Growth" — press Tab to complete. Small UX touch, but it makes the product feel intentional.

---

🛠️ Stack & Why

→ **Groq (LLaMA 3.3-70B)** — free tier, sub-second answers
→ **ChromaDB Cloud** — vector store, zero infra
→ **fastembed (ONNX)** — 4× lighter than PyTorch, fits free hosting
→ **GitHub Actions** — daily data refresh at 9:15 AM IST, no extra server
→ **FastAPI + Next.js** — backend + clean chat UI
→ **Render + Vercel** — fully free deployment

---

Building production AI is 20% model and 80% guardrails.

Grateful to my mentor **Saksham Arora** and the entire **@NextLeap** team for pushing me to think beyond demos and build something production-worthy. This fellowship is genuinely changing how I approach product and AI. 🙏

Would love to connect with anyone in RAG, FinTech AI, or product! 💬

@NextLeap

#NextLeapPMFellowship #GenerativeAI #RAG #FinTech #MutualFunds #LLM #ProductThinking #BuildInPublic
