"""
llm_client — Unified LLM client via OpenRouter.
Used by: developer, monitor, manager, autopilot.
Each service sets its own LLM_MODEL and LLM_SYSTEM_PROMPT via .env.
"""
import os
import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def get_config():
    """Load LLM config from environment."""
    return {
        "api_key": os.environ.get("OPENROUTER_API_KEY", ""),
        "model": os.environ.get("LLM_MODEL", "openai/gpt-3.5-turbo"),
        "system_prompt": os.environ.get("LLM_SYSTEM_PROMPT", "You are a helpful assistant."),
        "max_tokens": int(os.environ.get("LLM_MAX_TOKENS", "2048")),
        "temperature": float(os.environ.get("LLM_TEMPERATURE", "0.7")),
    }


def chat(user_message, system_prompt=None, model=None, history=None):
    """Send a message to the LLM and return the response text."""
    cfg = get_config()
    api_key = cfg["api_key"]

    if not api_key:
        return "[LLM] Error: OPENROUTER_API_KEY not set. Configure in service .env file."

    messages = []
    sp = system_prompt or cfg["system_prompt"]
    if sp:
        messages.append({"role": "system", "content": sp})

    if history:
        messages.extend(history)

    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": model or cfg["model"],
        "messages": messages,
        "max_tokens": cfg["max_tokens"],
        "temperature": cfg["temperature"],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://infra-deploy.local",
        "X-Title": f"infra-deploy-{os.environ.get('SERVICE_ROLE', 'unknown')}",
    }

    try:
        req = urllib.request.Request(
            OPENROUTER_URL,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        logger.error(f"LLM HTTP {e.code}: {body}")
        return f"[LLM] HTTP Error {e.code}: {body[:200]}"
    except Exception as e:
        logger.error(f"LLM error: {e}")
        return f"[LLM] Error: {e}"


def chat_stream(user_message, system_prompt=None, model=None):
    """Non-streaming wrapper that prints response progressively."""
    response = chat(user_message, system_prompt, model)
    print(response)
    return response


def list_models():
    """List popular OpenRouter models."""
    return [
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "anthropic/claude-sonnet-4",
        "anthropic/claude-haiku-4",
        "google/gemini-2.0-flash-001",
        "meta-llama/llama-3.1-70b-instruct",
        "mistralai/mistral-large-latest",
        "deepseek/deepseek-chat-v3-0324",
    ]


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        msg = " ".join(sys.argv[1:])
        print(chat(msg))
    else:
        print("Usage: python3 llm_client.py <message>")
        print(f"Model: {get_config()['model']}")
        print(f"API Key set: {bool(get_config()['api_key'])}")
