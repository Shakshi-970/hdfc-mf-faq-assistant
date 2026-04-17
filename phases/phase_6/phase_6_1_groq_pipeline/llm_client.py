"""
phases/phase_6/phase_6_1_groq_pipeline/llm_client.py
------------------------------------------------------
Abstract LLM client and concrete provider implementations.

Design
------
Both providers share the same interface: generate(system_prompt, messages).
The caller (pipeline.py) never needs to know which provider is active —
it just calls generate() and gets back a text string.

  LLMClient          — abstract base class
  GroqClient         — Groq inference API (llama-3.3-70b-versatile by default)
  ClaudeClient       — Anthropic Claude (claude-sonnet-4-6)
  get_llm_client()   — factory: selects provider from LLM_PROVIDER env var

Message format differences (handled internally):
  Groq  — OpenAI-compatible: system message is the first item in the messages list
  Claude — system is a separate API parameter; messages list contains only user/assistant turns

Environment variables:
  LLM_PROVIDER      "groq" (default) or "claude"
  GROQ_API_KEY      required for GroqClient
  GROQ_MODEL        Groq model ID (default: llama-3.3-70b-versatile)
  ANTHROPIC_API_KEY required for ClaudeClient
  CLAUDE_MODEL      Claude model ID (default: claude-sonnet-4-6)
  LLM_MAX_TOKENS    max output tokens for both providers (default: 512)
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
_DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-6"
_DEFAULT_MAX_TOKENS = 512


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class LLMClient(ABC):
    """
    Minimal interface for an LLM that takes a system prompt and a list of
    user/assistant messages, and returns a text response.
    """

    @abstractmethod
    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        """
        Generate a response.

        Parameters
        ----------
        system_prompt : Instructions for the model (facts-only rules, format, etc.)
        messages      : List of {"role": "user"|"assistant", "content": str} dicts.
                        Does NOT include the system message — that is handled by
                        each concrete implementation.

        Returns
        -------
        str — model response text, stripped of leading/trailing whitespace.
        """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider label for logging and health responses."""


# ---------------------------------------------------------------------------
# Groq
# ---------------------------------------------------------------------------

class GroqClient(LLMClient):
    """
    Groq inference API client.

    Groq hosts open-weight models (Llama 3, Mixtral, Gemma 2) on custom
    LPU hardware for ultra-low latency.  The API is OpenAI-compatible.

    Default model: llama-3.3-70b-versatile
    Other options: llama3-8b-8192, mixtral-8x7b-32768, gemma2-9b-it
    """

    def __init__(
        self,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY is not set. "
                "Get a free key at https://console.groq.com/keys"
            )

        self.model = model or os.environ.get("GROQ_MODEL", _DEFAULT_GROQ_MODEL)
        self.max_tokens = max_tokens or int(
            os.environ.get("LLM_MAX_TOKENS", _DEFAULT_MAX_TOKENS)
        )

        from groq import Groq  # lazy import — not installed in phase_3 env
        self._client = Groq(api_key=api_key)
        logger.info("GroqClient initialised — model=%s max_tokens=%d", self.model, self.max_tokens)

    @property
    def provider_name(self) -> str:
        return f"groq/{self.model}"

    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        """
        Call Groq chat completions.

        Groq is OpenAI-compatible: the system prompt is injected as the first
        message with role="system", followed by the user/assistant turn messages.
        """
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        response = self._client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            max_tokens=self.max_tokens,
            temperature=0.1,   # low temperature for factual, consistent answers
        )

        text = response.choices[0].message.content or ""
        return text.strip()


# ---------------------------------------------------------------------------
# Claude (kept as drop-in fallback)
# ---------------------------------------------------------------------------

class ClaudeClient(LLMClient):
    """
    Anthropic Claude client — same interface as GroqClient.

    Used as the fallback when LLM_PROVIDER=claude (or when Groq is unavailable).
    """

    def __init__(
        self,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY is not set.")

        self.model = model or os.environ.get("CLAUDE_MODEL", _DEFAULT_CLAUDE_MODEL)
        self.max_tokens = max_tokens or int(
            os.environ.get("LLM_MAX_TOKENS", _DEFAULT_MAX_TOKENS)
        )

        import anthropic  # lazy import
        self._client = anthropic.Anthropic(api_key=api_key)
        logger.info("ClaudeClient initialised — model=%s max_tokens=%d", self.model, self.max_tokens)

    @property
    def provider_name(self) -> str:
        return f"anthropic/{self.model}"

    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        """
        Call Anthropic Claude messages API.

        Claude takes the system prompt as a separate parameter, not as part of
        the messages list.
        """
        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_llm_client() -> LLMClient:
    """
    Instantiate the LLM client selected by the LLM_PROVIDER environment variable.

    LLM_PROVIDER=groq   (default) → GroqClient   (GROQ_API_KEY required)
    LLM_PROVIDER=claude           → ClaudeClient  (ANTHROPIC_API_KEY required)

    Raises
    ------
    EnvironmentError : if the required API key is missing.
    ValueError       : if LLM_PROVIDER has an unrecognised value.
    """
    provider = os.environ.get("LLM_PROVIDER", "groq").strip().lower()

    if provider == "groq":
        return GroqClient()
    if provider == "claude":
        return ClaudeClient()

    raise ValueError(
        f"Unknown LLM_PROVIDER={provider!r}. "
        "Set LLM_PROVIDER to 'groq' or 'claude'."
    )
