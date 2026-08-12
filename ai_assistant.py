"""Piece 32.0: Solbiz AI assistant — provider layer.

A tiny, dependency-free client for the two chat providers ECC has access to:
Anthropic (Claude) and Google (Gemini). Kept in pure stdlib on purpose — Solbiz
ships as a frozen PyInstaller exe, so adding SDKs would bloat the bundle and
complicate packaging. Both providers are reduced to the same shape:

    ask(provider, api_key, model, system, user_message) -> answer text

The request/response *builders* and *parsers* are separated from the network
call so they can be unit-tested without hitting the internet (the app is
offline-capable; the assistant is the one online-only feature).
"""

import json
import urllib.request
import urllib.error

# Selectable Claude models (label -> id). Sonnet is the sensible default for
# internal Q&A — cheaper than Opus, plenty capable for "what's the status of…".
CLAUDE_MODELS = [
    ("Claude Sonnet (balanced, recommended)", "claude-sonnet-5"),
    ("Claude Opus (most capable, pricier)", "claude-opus-5"),
    ("Claude Haiku (fastest, cheapest)", "claude-haiku-4-5"),
]
CLAUDE_MODEL_IDS = [m for _label, m in CLAUDE_MODELS]
CLAUDE_DEFAULT_MODEL = "claude-sonnet-5"

# Gemini model IDs move around as Google ships new versions, so this is a plain
# editable setting rather than a fixed list — default to a widely-available one.
GEMINI_DEFAULT_MODEL = "gemini-2.0-flash"

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
GEMINI_URL_TMPL = ("https://generativelanguage.googleapis.com/v1beta/models/"
                   "{model}:generateContent")

REQUEST_TIMEOUT = 45  # seconds — a single interactive question


class AssistantError(Exception):
    """A user-facing failure from the assistant (bad key, network, provider)."""


# ----------------------------------------------------------------------------
# Claude (Anthropic Messages API)
# ----------------------------------------------------------------------------
def build_claude_request(api_key, model, system, user_message, max_tokens=1024):
    """Return (url, headers, body_dict) for one Claude Messages API call."""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    body = {
        "model": model or CLAUDE_DEFAULT_MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user_message}],
    }
    return ANTHROPIC_URL, headers, body


def parse_claude_response(data):
    """Pull the assistant's text out of a Claude Messages API response."""
    if data.get("type") == "error":
        raise AssistantError(_provider_error_text(data))
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    text = "".join(parts).strip()
    if not text:
        raise AssistantError("Claude returned an empty response.")
    return text


# ----------------------------------------------------------------------------
# Gemini (Google Generative Language API)
# ----------------------------------------------------------------------------
def build_gemini_request(api_key, model, system, user_message):
    """Return (url, headers, body_dict) for one Gemini generateContent call."""
    url = GEMINI_URL_TMPL.format(model=model or GEMINI_DEFAULT_MODEL)
    # The key rides as a header (x-goog-api-key) rather than a query string so it
    # never lands in logs or the URL.
    headers = {"content-type": "application/json", "x-goog-api-key": api_key}
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
    }
    return url, headers, body


def parse_gemini_response(data):
    """Pull the assistant's text out of a Gemini generateContent response."""
    if "error" in data:
        raise AssistantError(_provider_error_text(data["error"]))
    candidates = data.get("candidates") or []
    if not candidates:
        # Often a safety block — surface the reason if present.
        fb = (data.get("promptFeedback") or {}).get("blockReason")
        raise AssistantError(
            f"Gemini declined to answer{f' ({fb})' if fb else ''}.")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise AssistantError("Gemini returned an empty response.")
    return text


# ----------------------------------------------------------------------------
# Shared plumbing
# ----------------------------------------------------------------------------
def _provider_error_text(err):
    if isinstance(err, dict):
        msg = err.get("message") or (err.get("error") or {}).get("message")
        if msg:
            return str(msg)
    return "The AI provider returned an error."


def _post_json(url, headers, body, timeout=REQUEST_TIMEOUT):
    """POST a JSON body and return the decoded JSON response. Raises
    AssistantError with a friendly message on any transport/HTTP failure."""
    raw = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=raw, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = _provider_error_text(json.loads(e.read().decode("utf-8")))
        except Exception:
            detail = e.reason or ""
        if e.code in (401, 403):
            raise AssistantError(
                "The AI provider rejected the API key — check it in AI settings.")
        if e.code == 429:
            raise AssistantError(
                "The AI provider is rate-limiting requests — try again shortly.")
        raise AssistantError(f"AI provider error ({e.code}): {detail}".strip())
    except urllib.error.URLError as e:
        raise AssistantError(
            "Couldn't reach the AI provider — check the internet connection. "
            f"({getattr(e, 'reason', e)})")
    except Exception as e:  # JSON decode, ssl, etc.
        raise AssistantError(f"Unexpected error talking to the AI provider: {e}")


def ask(provider, api_key, model, system, user_message):
    """Ask one question of the chosen provider and return the answer text.
    `provider` is 'claude' or 'gemini'. Raises AssistantError on any problem."""
    if not (api_key or "").strip():
        raise AssistantError(
            "No API key is set for this provider — add one in AI settings.")
    if provider == "gemini":
        url, headers, body = build_gemini_request(api_key, model, system, user_message)
        return parse_gemini_response(_post_json(url, headers, body))
    # default: claude
    url, headers, body = build_claude_request(api_key, model, system, user_message)
    return parse_claude_response(_post_json(url, headers, body))
