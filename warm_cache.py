"""
Run all demo queries through the full pipeline and save snapshots to demo/snapshots/.
Populates serp_cache/ and llm_cache/ so the live demo is instant.
"""
import json
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

from serp import get_live_context
from llm import get_llm_answer, compute_delta

SNAPSHOT_DIR = pathlib.Path(__file__).parent / "demo" / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

QUERIES = [
    "Who is the CEO of OpenAI?",
    "What is the latest Claude model from Anthropic?",
    "What is the current US Federal Reserve interest rate?",
    "What is the current status of TikTok in the United States?",
    "Who won the 2025 NBA Championship?",
    "What is the latest GPT model from OpenAI?",
    "Who is the current US Secretary of State?",
    "What is NVIDIA's current market cap?",
    "Who is the current UK Prime Minister?",
    "Who is the current Formula 1 World Champion?",
]


def run_query(query: str) -> dict:
    print(f"  fetching: {query}", flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        llm_f  = pool.submit(get_llm_answer, query)
        serp_f = pool.submit(get_live_context, query)
        llm_answer = llm_f.result()
        live_data  = serp_f.result()
    delta = compute_delta(query, llm_answer, live_data)
    return {"query": query, "llm_answer": llm_answer, "delta": delta,
            "live_snippets": live_data["snippets"], "headlines": live_data["headlines"]}


if __name__ == "__main__":
    print(f"\nWarming {len(QUERIES)} queries...\n", flush=True)
    results = []
    for i, q in enumerate(QUERIES, 1):
        try:
            print(f"[{i}/{len(QUERIES)}] {q}", flush=True)
            r = run_query(q)
            results.append(r)
            slug = q[:40].replace(" ", "_").replace("?", "").replace("'", "")
            out  = SNAPSHOT_DIR / f"{i:02d}_{slug}.json"
            out.write_text(json.dumps(r, indent=2), encoding="utf-8")
            score   = r["delta"]["staleness_score"]
            verdict = r["delta"]["verdict"]
            print(f"      Score: {score}/100  Verdict: {verdict}\n", flush=True)
        except Exception as e:
            import traceback
            print(f"      ERROR: {e}", flush=True)
            traceback.print_exc()
            print(flush=True)

    print(f"\nDone. {len(results)}/{len(QUERIES)} queries cached.")
    print(f"Snapshots saved to: {SNAPSHOT_DIR}\n")
