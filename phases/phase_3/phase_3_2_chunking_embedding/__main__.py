"""
Entry point for: python -m phases.phase_3_2_chunking_embedding
Runs the chunk-and-embed step (Step 5 of the ingestion pipeline).
To run only the upsert step: python -m phases.phase_3_2_chunking_embedding.upsert
"""
import sys

from .chunk_and_embed import main

if __name__ == "__main__":
    sys.exit(main())
