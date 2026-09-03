import os
import json
import time
import hashlib
import pathlib
from openai import OpenAI
from dotenv import load_dotenv
from prompts import LLM_ANSWER_PROMPT, DELTA_PROMPT

load_dotenv()

LLM_CACHE_DIR = pathlib.Path(__file__).parent / "llm_cache"
LLM_CACHE_DIR.mkdir(exist_ok=True)

# LLM answers are deterministic (training data is fixed) — cache for 7 days
LLM_CACHE_TTL = 7 * 24 * 3600


def _providers(prefer_small: bool = False, nebius_key: str = "") -> list[dict]:
    """
    Return provider list in priority order.
    prefer_small=True uses Qwen3-32B (faster) for the initial answer call.
    prefer_small=False uses Llama 3.3 70B (more capable) for the delta JSON call.
    """
    small_model = os.getenv("NEBIUS_CHAT_MODEL_SMALL", "Qwen/Qwen3-30B-A3B-Instruct-2507")
    large_model = os.getenv("NEBIUS_CHAT_MODEL",       "meta-llama/Llama-3.3-70B-Instruct")
    return [
        {
            "name":     f"Nebius ({'Qwen3-32B' if prefer_small else 'Llama-70B'})",
            "base_url": os.getenv("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1/"),
            "api_key":  nebius_key or os.getenv("NEBIUS_API_KEY", ""),
            "model":    small_model if prefer_small else large_model,
            "extra":    {"enable_thinking": False} if prefer_small else {},
        },
        {
            "name":     "Google Gemini Flash",
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "api_key":  os.getenv("GOOGLE_API_KEY", ""),
            "model":    "gemini-2.0-flash",
            "extra":    {},
        },
        {
            "name":     "Ollama (local)",
            "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1/"),
            "api_key":  "ollama",
            "model":    os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
            "extra":    {},
        },
    ]


def _chat(messages: list[dict], max_tokens: int, prefer_small: bool = False, nebius_key: str = "") -> str:
    last_error = None
    for p in _providers(prefer_small=prefer_small, nebius_key=nebius_key):
        if not p["api_key"] or p["api_key"] == "ollama":
            # For Ollama, always try (no key needed); skip others with empty key
            if p["name"] != "Ollama (local)" and not p["api_key"]:
                continue
        try:
            client = OpenAI(api_key=p["api_key"], base_url=p["base_url"])
            kwargs = dict(
                model=p["model"],
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.2,
            )
            if p["extra"]:
                kwargs["extra_body"] = p["extra"]
            resp = client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content
        except Exception as e:
            last_error = e
            continue
    raise RuntimeError(
        f"All LLM providers failed. Last error: {last_error}\n"
        "Check NEBIUS_API_KEY, GOOGLE_API_KEY, or that Ollama is running."
    )


# ── LLM answer disk cache ─────────────────────────────────────────────────────

def _llm_cache_path(query: str) -> pathlib.Path:
    key = hashlib.md5(query.strip().lower().encode()).hexdigest()
    return LLM_CACHE_DIR / f"{key}.txt"


def _load_llm_cache(query: str) -> str | None:
    path = _llm_cache_path(query)
    if not path.exists():
        return None
    if (time.time() - path.stat().st_mtime) > LLM_CACHE_TTL:
        return None
    return path.read_text(encoding="utf-8")


def _save_llm_cache(query: str, answer: str) -> None:
    _llm_cache_path(query).write_text(answer, encoding="utf-8")


# ── Public API ────────────────────────────────────────────────────────────────

def get_llm_answer(query: str, nebius_key: str = "") -> str:
    """Get the LLM's training-data answer. Disk-cached for 7 days (training data is fixed)."""
    cached = _load_llm_cache(query)
    if cached is not None:
        return cached

    messages = [{"role": "user", "content": LLM_ANSWER_PROMPT.format(query=query)}]
    answer = _chat(messages, max_tokens=512, prefer_small=True, nebius_key=nebius_key)
    _save_llm_cache(query, answer)
    return answer


def compute_delta(query: str, llm_answer: str, live_data: dict, nebius_key: str = "") -> dict:
    """Compare LLM answer vs live web data. Uses the larger model for structured JSON output."""
    prompt = DELTA_PROMPT.format(
        query=query,
        llm_answer=llm_answer,
        snippets=live_data["snippets"],
        headlines=live_data["headlines"],
        paa=live_data["paa"],
    )
    messages = [{"role": "user", "content": prompt}]
    raw = _chat(messages, max_tokens=1024, prefer_small=False, nebius_key=nebius_key).strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)
