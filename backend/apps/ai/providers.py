import json
import logging
import os
import urllib.error
import urllib.request

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool

logger = logging.getLogger("apps.ai")

DEFAULT_BASIX_BASE_URL = "https://llm.c.singularitynet.io/v1"
DEFAULT_BASIX_MODEL = "qwen/qwen3.8-27b"
DEFAULT_BASIX_EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"


class ProviderNotConfigured(Exception):
    pass


class ProviderError(Exception):
    """The language provider failed. This is not an ISP tool failure."""


def basix_settings():
    return {
        "api_key": os.getenv("BASIX_API_KEY", "").strip(),
        "base_url": (os.getenv("BASIX_BASE_URL", "").strip() or DEFAULT_BASIX_BASE_URL).rstrip("/"),
        "model": os.getenv("BASIX_MODEL", "").strip() or DEFAULT_BASIX_MODEL,
        "embedding_model": os.getenv("BASIX_EMBEDDING_MODEL", "").strip() or DEFAULT_BASIX_EMBEDDING_MODEL,
        "timeout": _timeout(),
    }


def groq_settings():
    return {
        "api_key": os.getenv("GROQ_API_KEY", "").strip(),
        "model": os.getenv("GROQ_MODEL", "").strip(),
    }


def _timeout():
    raw = os.getenv("BASIX_TIMEOUT", "").strip() or "25"
    try:
        return max(int(raw), 1)
    except ValueError:
        return 25


class BasixChatModel:
    """OpenAI-compatible chat client for the BASIX endpoint."""

    def __init__(self, model, api_key, base_url, timeout, tools=None):
        self.model_name = model
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.tools = list(tools or [])

    def __repr__(self):
        return f"BasixChatModel(model={self.model_name!r})"

    def bind_tools(self, tools, **kwargs):
        return BasixChatModel(self.model_name, self.api_key, self.base_url, self.timeout, tools)

    def invoke(self, messages, **kwargs):
        payload = {
            "model": self.model_name,
            "temperature": 0,
            "messages": [_openai_message(message) for message in messages],
        }
        if self.tools:
            payload["tools"] = [convert_to_openai_tool(tool) for tool in self.tools]
            payload["tool_choice"] = "auto"
        data = _post_json(f"{self.base_url}/chat/completions", payload, self.api_key, self.timeout)
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("BASIX returned an unexpected response.") from exc
        return _ai_message(message)


class GroqChatModel:
    """Existing Groq chat model. Kept as the fallback provider."""

    def __init__(self, model, api_key, tools=None):
        self.model_name = model
        self.api_key = api_key
        self.tools = list(tools or [])
        self._model = None

    def __repr__(self):
        return f"GroqChatModel(model={self.model_name!r})"

    def bind_tools(self, tools, **kwargs):
        return GroqChatModel(self.model_name, self.api_key, tools)

    def invoke(self, messages, **kwargs):
        if self._model is None:
            from langchain_groq import ChatGroq

            model = ChatGroq(model=self.model_name, api_key=self.api_key, temperature=0)
            if self.tools:
                model = model.bind_tools(self.tools)
            self._model = model
        return self._model.invoke(messages, **kwargs)


class FallbackChatModel:
    """Try BASIX, then the existing Groq model, for each model call."""

    def __init__(self, primary=None, fallback=None, state=None):
        self.primary = primary
        self.fallback = fallback
        self.state = state if state is not None else {"last_provider": "", "used_fallback": False}

    @property
    def last_provider(self):
        return self.state["last_provider"]

    @property
    def used_fallback(self):
        return self.state["used_fallback"]

    def bind_tools(self, tools, **kwargs):
        return FallbackChatModel(
            primary=self.primary.bind_tools(tools, **kwargs) if self.primary is not None else None,
            fallback=self.fallback.bind_tools(tools, **kwargs) if self.fallback is not None else None,
            state=self.state,
        )

    def invoke(self, messages, **kwargs):
        if self.primary is not None:
            try:
                message = self.primary.invoke(messages, **kwargs)
            except Exception as exc:
                logger.warning("ai.provider fallback from=basix to=groq error_type=%s", type(exc).__name__)
                if self.fallback is None:
                    raise ProviderError("The language provider is unavailable.") from None
            else:
                self.state["last_provider"] = "basix"
                self.state["used_fallback"] = False
                return message
        if self.fallback is not None:
            try:
                message = self.fallback.invoke(messages, **kwargs)
            except Exception as exc:
                logger.warning("ai.provider groq_failed error_type=%s", type(exc).__name__)
                raise ProviderError("The language provider is unavailable.") from None
            self.state["last_provider"] = "groq"
            self.state["used_fallback"] = self.primary is not None
            return message
        raise ProviderNotConfigured("No language provider is configured.")


def build_chat_model():
    basix = basix_settings()
    groq = groq_settings()
    primary = None
    fallback = None
    if basix["api_key"]:
        primary = BasixChatModel(basix["model"], basix["api_key"], basix["base_url"], basix["timeout"])
    if groq["api_key"] and groq["model"]:
        fallback = GroqChatModel(groq["model"], groq["api_key"])
    if primary is None and fallback is None:
        raise ProviderNotConfigured("No language provider is configured.")
    return FallbackChatModel(primary=primary, fallback=fallback)


def embed_text(text):
    settings = basix_settings()
    if not settings["api_key"]:
        raise ProviderNotConfigured("BASIX embeddings are not configured.")
    data = _post_json(
        f"{settings['base_url']}/embeddings",
        {"model": settings["embedding_model"], "input": text},
        settings["api_key"],
        settings["timeout"],
    )
    try:
        vector = data["data"][0]["embedding"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("BASIX returned an unexpected embedding response.") from exc
    if not isinstance(vector, list):
        raise ProviderError("BASIX returned an unexpected embedding response.")
    return vector


def _post_json(url, payload, api_key, timeout):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise ProviderError(f"BASIX HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderError("BASIX request failed") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderError("BASIX returned invalid JSON.") from exc
    if isinstance(data, dict) and data.get("error") and "choices" not in data and "data" not in data:
        raise ProviderError("BASIX returned an error response.")
    return data


def _openai_message(message):
    if isinstance(message, SystemMessage):
        role = "system"
    elif isinstance(message, HumanMessage):
        role = "user"
    elif isinstance(message, ToolMessage):
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": message.content if isinstance(message.content, str) else json.dumps(message.content),
        }
    else:
        role = "assistant"
    content = _content_text(getattr(message, "content", ""))
    payload = {"role": role, "content": content}
    tool_calls = getattr(message, "tool_calls", None) or []
    if role == "assistant" and tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.get("id") or call.get("name") or "call",
                "type": "function",
                "function": {
                    "name": call.get("name"),
                    "arguments": json.dumps(call.get("args") or {}),
                },
            }
            for call in tool_calls
        ]
    return payload


def _content_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(item["text"])
        return "\n".join(parts)
    return "" if content is None else str(content)


def _ai_message(message):
    content = _content_text(message.get("content"))
    tool_calls = []
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        name = function.get("name") or call.get("name") or ""
        arguments = function.get("arguments", call.get("arguments", "{}"))
        if isinstance(arguments, str):
            try:
                args = json.loads(arguments) if arguments else {}
            except json.JSONDecodeError:
                args = {}
        elif isinstance(arguments, dict):
            args = arguments
        else:
            args = {}
        if not isinstance(args, dict):
            args = {}
        tool_calls.append(
            {
                "name": name,
                "args": args,
                "id": call.get("id") or name or "call",
                "type": "tool_call",
            }
        )
    return AIMessage(content=content, tool_calls=tool_calls)
