"""
phases/phase_6/phase_6_1_groq_pipeline/__main__.py
---------------------------------------------------
Entry point for the Phase 6 FastAPI server (Groq / configurable LLM).

Usage:
    # Default (Groq, port 8001)
    python -m phases.phase_6.phase_6_1_groq_pipeline

    # Switch to Claude
    LLM_PROVIDER=claude python -m phases.phase_6.phase_6_1_groq_pipeline

    # Custom port
    API_PORT=9000 python -m phases.phase_6.phase_6_1_groq_pipeline

Required environment variables:
    GROQ_API_KEY          Groq API key (get free key at console.groq.com)
    CHROMA_API_KEY        Chroma Cloud authentication key
    CHROMA_TENANT         Chroma Cloud tenant identifier
    CHROMA_DATABASE       Chroma Cloud database name

Optional:
    LLM_PROVIDER          "groq" (default) or "claude"
    GROQ_MODEL            Groq model ID (default: llama-3.3-70b-versatile)
    LLM_MAX_TOKENS        max output tokens (default: 512)
    API_PORT              port to bind (default: 8001)
    ANTHROPIC_API_KEY     required only when LLM_PROVIDER=claude
"""

import os

import uvicorn
from dotenv import load_dotenv

from .app import app

if __name__ == "__main__":
    load_dotenv()  # Load environment variables from .env
    port = int(os.environ.get("API_PORT", 8001))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
