LLM_ANSWER_PROMPT = """Answer this question directly and factually from your training knowledge.
Be specific — include names, dates, numbers, model versions, prices, or titles where relevant.
Do NOT hedge with phrases like "as of my knowledge cutoff" or "I may be outdated."
Give your best, most confident, specific answer as if it is current fact.

Question: {query}"""


DELTA_PROMPT = """You are a precision knowledge auditor. Your job is to find the EXACT gap between an AI's training-data answer and live web reality.

QUESTION:
{query}

AI ANSWER (from training data — potentially months or years old):
{llm_answer}

LIVE WEB DATA (retrieved right now via Google Search + News — this is ground truth):
Organic snippets: {snippets}
Recent news headlines: {headlines}
People Also Ask: {paa}

INSTRUCTIONS:
1. Compare the AI answer against the live web data meticulously.
2. Find specific facts that differ: names, numbers, versions, dates, statuses, prices, roles.
3. Be concrete. "The AI says X but the web says Y" is a good discrepancy. Vague statements are not.
4. The staleness_score should reflect FACTUAL deviation, not recency alone:
   - 0–15: AI answer is accurate and current
   - 16–35: Minor details changed, core answer still holds
   - 36–65: Significant facts have changed — answer misleads
   - 66–85: Most key facts are wrong or outdated
   - 86–100: AI answer directly contradicts current reality

Return ONLY valid JSON — no explanation, no markdown fences:
{{
  "staleness_score": <integer 0-100>,
  "verdict": "<exactly one of: Fresh | Slightly Outdated | Outdated | Contradicted | Unverifiable>",
  "what_changed": "<one clear, specific sentence stating what has changed since the AI was trained — use names and facts>",
  "discrepancies": [
    "<specific fact: 'AI says X, but web shows Y'>",
    "<another concrete discrepancy if present — omit vague ones>"
  ],
  "ai_likely_cutoff_hint": "<estimate when the AI's knowledge on this topic ends, e.g. 'early 2024' or 'pre-2025'>",
  "sources": ["<url from snippets or headlines that directly contradicts or updates the AI answer>"]
}}

If the AI answer is accurate and current, set staleness_score ≤ 15 and verdict to Fresh. Keep discrepancies array empty."""


BATCH_DELTA_PROMPT = """You are a knowledge auditor. For each claim below, rate its freshness against current web data.

LIVE WEB CONTEXT:
{live_context}

CLAIMS TO AUDIT:
{claims}

Return a JSON array, one object per claim:
[
  {{
    "claim": "<original claim text>",
    "staleness_score": <0-100>,
    "verdict": "<Fresh | Slightly Outdated | Outdated | Contradicted>",
    "reason": "<one specific sentence — name what changed>"
  }}
]"""
