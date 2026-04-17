"""
phases/phase_3_4_query_pipeline/prompt_builder.py
--------------------------------------------------
Step 5 — Prompt Constructor

Builds the system prompt and user message for the LLM (Claude).

Constraints enforced via prompt:
  - Answer ONLY from the provided context (no hallucination)
  - Maximum 3 sentences
  - Facts-only — no investment advice or performance predictions
  - Exactly one Source URL citation
  - Footer: "Last updated from sources: YYYY-MM-DD"
"""

from __future__ import annotations

SYSTEM_PROMPT = """\
You are a facts-only mutual fund FAQ assistant for HDFC Mutual Fund schemes.

SCHEME NAME ALIASES — the same fund may be referred to by multiple names:
- "HDFC Equity Fund Direct Growth" is also known as "HDFC Flexi Cap Fund"
- "HDFC ELSS Tax Saver Fund Direct Plan Growth" is also known as "HDFC ELSS Fund" or "HDFC Tax Saver Fund"
- "HDFC Mid-Cap Fund Direct Growth" is also known as "HDFC Mid Cap Fund"

STRICT RULES — follow all of them without exception:
1. Answer ONLY using the information present in the CONTEXT block below.
   Do NOT use any knowledge outside the provided context.
   When the user asks about a fund alias (e.g. "Flexi Cap"), treat it as
   equivalent to the canonical name in the context.
2. Keep your answer to a maximum of 3 sentences.
3. Do NOT give investment advice, fund recommendations, performance
   predictions, or opinions of any kind.
4. End every answer with exactly these two lines (fill in the values
   from the context metadata):
       Source: <source_url>
       Last updated from sources: <ingestion_date>
5. If the context does not contain enough information to answer the
   question, respond with exactly:
       I don't have sufficient information to answer this question.
       Please refer to the source for full details.
       Source: <source_url from context, or "https://groww.in">
       Last updated from sources: <ingestion_date from context>
6. Never mention returns, performance history, or suitability for any
   investor profile.\
"""


def build_messages(query: str, chunks: list[dict]) -> list[dict]:
    """
    Build the messages list for the Anthropic Claude API.

    Parameters
    ----------
    query  : Original (non-rewritten) user query.
    chunks : Top-N retrieved chunks from retriever.py, each with
             'text', 'metadata', and 'score'.

    Returns
    -------
    List of message dicts suitable for anthropic.messages.create().
    """
    context_parts: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk["metadata"]
        context_parts.append(
            f"[Chunk {i}]\n"
            f"Text: {chunk['text']}\n"
            f"source_url: {meta.get('source_url', 'N/A')}\n"
            f"scheme_name: {meta.get('scheme_name', 'N/A')}\n"
            f"field_type: {meta.get('field_type', 'N/A')}\n"
            f"ingestion_date: {meta.get('ingestion_date', 'N/A')}"
        )

    context_block = "\n\n".join(context_parts)

    user_content = (
        f"CONTEXT:\n{context_block}\n\n"
        f"USER QUESTION:\n{query}"
    )

    return [{"role": "user", "content": user_content}]
