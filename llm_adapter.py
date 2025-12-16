# llm_adapter.py
"""
SentIQ — LLM adapter upgraded to a Router/Gateway pattern.

Behavior:
 - Keeps TokenBucket, shelve cache, and Simulation mode from the original adapter.
 - Tries cache first.
 - Primary: Google Gemini (via detected google.generativeai / genai SDKs).
 - Failover: Groq (Llama 3 family) via `groq` library.
 - Final fallback: Simulation mode or a safe "System overloaded" message.
 - Exported public function: call_llm(...) for backward compatibility (web_app.py uses this).
 
Notes:
 - This file is based on your previous adapter implementation; see original for more context. :contentReference[oaicite:1]{index=1}
"""

import os
import time
import shelve
import hashlib
import threading
import importlib
import pkgutil
import logging
from typing import Optional, Any, Dict

# External SDK imports (may raise ImportError; handled defensively)
try:
    import groq
except Exception:
    groq = None

# Attempt to load generative AI SDKs like google.generativeai / genai
GENAI_MODULE = None
GENAI_CLIENT_FACTORY = None
GENAI_NAME = None

# load .env if available (preserves original behaviour)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ---------- Configuration ----------
PROJECT_ROOT = os.path.dirname(__file__)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-70b-8192")

CACHE_FILE = os.getenv("SENTIQ_CACHE_FILE", os.path.join(PROJECT_ROOT, "sentiq_cache.db"))
DEFAULT_RPM = int(os.getenv("SENTIQ_RPM", "120"))

logger = logging.getLogger("sentiq.llm_adapter")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)

# Defensive detection of GenAI SDK name
_try_names = ["google.generativeai", "google.genai", "genai", "google.generativeai_v1"]
for name in _try_names:
    try:
        spec = importlib.util.find_spec(name)
        if spec:
            GENAI_MODULE = importlib.import_module(name)
            GENAI_NAME = name
            break
    except Exception:
        GENAI_MODULE = None

if GENAI_MODULE is None:
    # not fatal — keep going; Gemini calls will raise a clear error later
    logger.info("No Google GenAI SDK detected; GEMINI calls will fail until installed.")
else:
    logger.info("Detected GenAI module: %s", GENAI_NAME)

# Try to discover a client factory if present
if GENAI_MODULE is not None:
    if hasattr(GENAI_MODULE, "Client"):
        GENAI_CLIENT_FACTORY = getattr(GENAI_MODULE, "Client")
    elif hasattr(GENAI_MODULE, "client") and hasattr(GENAI_MODULE.client, "Client"):
        GENAI_CLIENT_FACTORY = getattr(GENAI_MODULE.client, "Client")
    else:
        GENAI_CLIENT_FACTORY = None

# ---------- Token bucket (unchanged) ----------
class TokenBucket:
    def __init__(self, rate_per_minute: int = 60, capacity: int = 60):
        self.rate = rate_per_minute / 60.0
        self.capacity = capacity
        self.tokens = capacity
        self.last = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens: float = 1.0) -> bool:
        with self.lock:
            now = time.time()
            elapsed = now - self.last
            self.last = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

bucket = TokenBucket(rate_per_minute=DEFAULT_RPM, capacity=DEFAULT_RPM)

# ---------- Simulation ----------
def simulated_response(prompt: str, category: str) -> str:
    # Keep exactly your previous simulation responses; small helpful variations allowed
    if category == "summarize":
        return "SIMULATED SUMMARY: " + (prompt[:200] + "." if len(prompt) > 200 else prompt)
    if category == "code_help":
        return "SIMULATED CODE HELP: Check variable initialization or off-by-one errors."
    if category == "grammar":
        return "SIMULATED GRAMMAR: Suggested correction: 'Your sentence corrected.'"
    if category == "small_talk":
        return "SIMULATED CHAT: Nice! How can I help you further?"
    return "SIMULATED ANSWER: I would search documentation or ask a clarifying question."

# ---------- Cache key ----------
def _cache_key(prompt: str, category: str, model: str) -> str:
    h = hashlib.sha256()
    h.update(f"{model}|{category}|{prompt}".encode("utf-8"))
    return h.hexdigest()

# ---------- Existing Gemini invocation helpers (kept largely as-is) ----------
def _extract_text_from_response(resp: Any) -> str:
    """
    Heuristic extraction — preserved from your original file.
    """
    if resp is None:
        return ""
    if isinstance(resp, str):
        return resp
    # common attributes used by SDKs
    for attr in ("text", "content", "output"):
        if hasattr(resp, attr):
            try:
                val = getattr(resp, attr)
                # if `.output` tends to be list/dict, try safer extraction
                if isinstance(val, (list, tuple)) and len(val) > 0:
                    first = val[0]
                    if isinstance(first, dict):
                        for k in ("content", "text", "output_text"):
                            if k in first:
                                return first[k]
                        return str(first)
                    return str(first)
                return str(val)
            except Exception:
                continue
    # last resort
    return str(resp)

def _invoke_genai(prompt: str, model: Optional[str] = None) -> Any:
    """
    Flexible invoker that tries multiple patterns across genai SDK versions.
    Kept from the prior implementation to maximize compatibility.
    """
    chosen_model = model or GEMINI_MODEL

    if GENAI_MODULE is None:
        raise RuntimeError("No GenAI SDK installed (google-generativeai / genai).")

    # Respect rate limit
    if not bucket.consume():
        raise RuntimeError("Rate limit reached (TokenBucket).")

    # Pattern A: GenerativeModel API
    try:
        if hasattr(GENAI_MODULE, "configure"):
            try:
                GENAI_MODULE.configure(api_key=GEMINI_API_KEY)
            except Exception:
                # some variants accept different signature; ignore
                pass
        if hasattr(GENAI_MODULE, "GenerativeModel"):
            model_obj = GENAI_MODULE.GenerativeModel(chosen_model)
            resp = model_obj.generate_content(prompt)
            return resp
    except Exception as e:
        logger.debug("GenAI pattern A failed: %s", e)

    # Pattern B: client factory
    try:
        if GENAI_CLIENT_FACTORY is not None:
            try:
                client = GENAI_CLIENT_FACTORY(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else GENAI_CLIENT_FACTORY()
            except TypeError:
                client = GENAI_CLIENT_FACTORY()
            if hasattr(client, "models") and hasattr(client.models, "generate_content"):
                return client.models.generate_content(model=chosen_model, contents=prompt)
            if hasattr(client, "generate") and callable(client.generate):
                return client.generate(model=chosen_model, prompt=prompt)
    except Exception as e:
        logger.debug("GenAI pattern B failed: %s", e)

    # Pattern C: module-level generate functions
    for fn_name in ("generate_text", "generate", "text_generate", "text.generate"):
        try:
            if "." in fn_name:
                head, tail = fn_name.split(".", 1)
                attr = getattr(GENAI_MODULE, head, None)
                if attr and hasattr(attr, tail):
                    call = getattr(attr, tail)
                    if callable(call):
                        return call(model=chosen_model, prompt=prompt)
            else:
                if hasattr(GENAI_MODULE, fn_name):
                    call = getattr(GENAI_MODULE, fn_name)
                    if callable(call):
                        return call(model=chosen_model, prompt=prompt)
        except Exception as e:
            logger.debug("GenAI pattern %s failed: %s", fn_name, e)
            continue

    raise RuntimeError("Could not invoke GenAI SDK with known patterns. Update your SDK or check GEMINI_API_KEY.")

def _call_gemini_sdk(prompt: str, model: Optional[str] = None) -> str:
    """
    Call Gemini via the detected SDK and return text content.
    Raises on failures — the router will catch them and perform failover.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set in environment.")

    resp = _invoke_genai(prompt, model=model)
    return _extract_text_from_response(resp)

# ---------- New: Groq (Llama 3) invocation ----------
def _invoke_groq_llama(prompt: str, model: Optional[str] = None, max_tokens: int = 1024) -> str:
    """
    Groq invocation with STRICT JSON enforcement.
    """

    if groq is None:
        raise RuntimeError("groq SDK not installed")

    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set")

    if not bucket.consume():
        raise RuntimeError("Rate limit reached (TokenBucket)")

    try:
        client = groq.Groq(api_key=GROQ_API_KEY)

        completion = client.chat.completions.create(
            model=model or GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You must respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}  # 🔥 THIS IS THE KEY
        )

        return completion.choices[0].message.content.strip()

    except Exception as e:
        raise RuntimeError(f"Groq invocation failed: {e}")


# ---------- Router / Gateway logic ----------
def call_llm_router(prompt: str, category: str = "general", use_simulation: bool = True, model_override: Optional[str] = None, prefer: Optional[str] = None) -> str:
    """
    Router that implements the Failover Cascade:
      1) Cache
      2) Gemini (primary)
      3) Groq Llama3 (failover)
      4) Simulation or "System overload" message

    Parameters:
      - prompt: text to send
      - category: logical category (used by simulation / caching)
      - use_simulation: if True, short-circuit to simulation for testing
      - model_override: optional model id string to pass to provider
      - prefer: optional preference hint: "gemini" | "groq" | None
    """
    # 0) Simulation mode quick path
    if use_simulation:
        # keep simulation time-slight delay to resemble network
        time.sleep(0.08)
        return simulated_response(prompt, category)

    # Build consistent cache key (include model_override or provider hint)
    cache_model = model_override or (GEMINI_MODEL if prefer != "groq" else GROQ_MODEL)
    key = _cache_key(prompt, category, cache_model)

    # 1) Cache check
    try:
        with shelve.open(CACHE_FILE) as cache:
            if key in cache:
                logger.debug("Cache hit for key %s (model=%s)", key[:8], cache_model)
                return cache[key]
    except Exception as e:
        logger.debug("Cache check failed (non-fatal): %s", e)

    # 2) Attempt primary provider(s)
    # Choose order: if prefer == "groq", try groq first, else Gemini first
    providers_sequence = []
    if prefer == "groq":
        providers_sequence = ["groq", "gemini"]
    else:
        providers_sequence = ["gemini", "groq"]

    last_exc: Optional[Exception] = None
    result: Optional[str] = None

    for provider in providers_sequence:
        try:
            if provider == "gemini":
                logger.debug("Router: trying Gemini (model=%s)", model_override or GEMINI_MODEL)
                # Note: _call_gemini_sdk will raise RuntimeError on missing API key or other failures
                result = _call_gemini_sdk(prompt, model=model_override)
                logger.info("Router: Gemini succeeded")
                break
            elif provider == "groq":
                logger.debug("Router: trying Groq (model=%s)", model_override or GROQ_MODEL)
                result = _invoke_groq_llama(prompt, model=GROQ_MODEL)
                logger.info("Router: Groq succeeded")
                break
        except Exception as e:
            # Detect common throttling / capacity errors by heuristics in message
            msg = str(e).lower()
            logger.warning("Router: provider %s failed: %s", provider, msg)
            last_exc = e
            # If it's a throttling-style error, continue to next provider
            # If it's an authentication error / misconfiguration, continue to next provider too
            # We only bail out if it's something totally unexpected — but router should try both providers.
            continue

    # 3) If we obtained a result, cache and return
    if result is not None:
        try:
            with shelve.open(CACHE_FILE) as cache:
                cache[key] = result
        except Exception:
            logger.debug("Router: failed to write to cache (non-fatal).")
        return result

    # 4) Nothing worked — final fallback
    # If there was a last exception and simulation disabled, return safe overload message
    overload_msg = "SYSTEM OVERLOAD: All language model providers are currently unavailable. Please try again later or enable simulation mode."
    logger.error("Router: all providers failed. Last error: %s", last_exc)
    return overload_msg

# Backwards-compatible public function used elsewhere in the app
def call_llm(prompt: str, category: str = "general", use_simulation: bool = True, model_override: Optional[str] = None) -> str:
    """
    Public wrapper retained for backward compatibility.
    Delegates to call_llm_router with default provider preference.
    """
    return call_llm_router(prompt=prompt, category=category, use_simulation=use_simulation, model_override=model_override)

# Quick local test harness (non-blocking)
if __name__ == "__main__":
    print("SentIQ adapter (router mode) — simulation demo")
    print(call_llm("Explain gradient descent in one paragraph.", "summarize", use_simulation=True))

def call_llm_safe(*args, retries=1, **kwargs):
    last_err = None
    for _ in range(retries + 1):
        try:
            return call_llm_router(*args, **kwargs)
        except Exception as e:
            last_err = e
    return "SYSTEM: Temporary AI unavailability. Please retry later."

