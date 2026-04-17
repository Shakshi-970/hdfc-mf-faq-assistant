"""
Entry point for: python -m phases.phase_3_3_scraping_service
"""
import asyncio
import sys

from .run import main

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
