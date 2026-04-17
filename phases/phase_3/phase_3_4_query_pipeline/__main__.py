"""
phases/phase_3_4_query_pipeline/__main__.py
-------------------------------------------
Entry point for running the FastAPI server directly.

Usage:
    python -m phases.phase_3_4_query_pipeline

Required environment variables:
    ANTHROPIC_API_KEY  : Anthropic Claude API key
    CHROMA_API_KEY     : Chroma Cloud authentication key
    CHROMA_TENANT      : Chroma Cloud tenant identifier
    CHROMA_DATABASE    : Chroma Cloud database name
"""

import uvicorn

from .app import app

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
