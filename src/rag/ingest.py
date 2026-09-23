"""CLI Ingestion script: Parse Spectrum PDF, generate embeddings, and index into ChromaDB + BM25."""

import argparse
import sys
import time
from pathlib import Path
from typing import Optional, Tuple
from tqdm import tqdm

from src.config import (
    ensure_directories,
    SPECTRUM_PDF_PATH,
    BATCH_SIZE,
    EMBEDDING_MODEL,
)
from src.rag.pdf_loader import SpectrumPDFLoader
from src.rag.chunker import SpectrumChunker
from src.rag.embeddings import EmbeddingClient
from src.rag.store import ChromaVectorStore
from src.rag.retriever import BM25Store


def parse_page_range(range_str: Optional[str]) -> Optional[Tuple[int, int]]:
    """Parse '1-50' string into (1, 50) tuple."""
    if not range_str or range_str.lower() == "all":
        return None
    try:
        parts = range_str.split("-")
        if len(parts) == 1:
            val = int(parts[0])
            return (val, val)
        return (int(parts[0]), int(parts[1]))
    except Exception:
        raise ValueError(f"Invalid page range format: '{range_str}'. Expected format like '1-50' or 'all'.")


def run_ingestion(
    source_pdf: Path = SPECTRUM_PDF_PATH,
    page_range_str: Optional[str] = None,
    batch_size: int = BATCH_SIZE,
    clear_existing: bool = False,
):
    """Run full ingestion pipeline."""
    ensure_directories()
    page_range = parse_page_range(page_range_str)

    print("=" * 70)
    print(" 📚 UPSC GS-1 Modern History RAG Ingestion Pipeline")
    print("=" * 70)
    print(f" Source PDF     : {source_pdf}")
    print(f" Page Range     : {page_range_str or 'All Pages'}")
    print(f" Embedding Model: {EMBEDDING_MODEL}")
    print(f" Batch Size     : {batch_size}")
    print("=" * 70)

    start_time = time.time()

    # 1. Load PDF pages
    print("\n[Step 1/5] Extracting and cleaning PDF pages...")
    loader = SpectrumPDFLoader(pdf_path=source_pdf)
    pages = loader.load_pages(page_range=page_range)
    print(f"  ✓ Loaded {len(pages)} valid pages.")

    if not pages:
        print("  ✗ No pages extracted. Exiting.")
        return

    # 2. Chunk pages
    print("\n[Step 2/5] Structuring chunks with Context Prefix Injection...")
    chunker = SpectrumChunker()
    chunks = chunker.chunk_pages(pages)
    total_tokens = sum(c.metadata.token_count for c in chunks)
    print(f"  ✓ Created {len(chunks)} chunks (Total tokens: ~{total_tokens:,}).")

    # 3. Generate OpenAI Embeddings
    print("\n[Step 3/5] Generating OpenAI vector embeddings...")
    embedding_client = EmbeddingClient()
    prefixed_texts = [c.prefixed_content for c in chunks]

    all_embeddings = []
    with tqdm(total=len(chunks), desc="  Embedding", unit="chunk") as pbar:
        for i in range(0, len(prefixed_texts), batch_size):
            batch = prefixed_texts[i : i + batch_size]
            batch_vectors = embedding_client.embed_texts(batch, batch_size=batch_size)
            all_embeddings.extend(batch_vectors)
            pbar.update(len(batch))

    for chunk, emb in zip(chunks, all_embeddings):
        chunk.embedding = emb

    # 4. Upsert into ChromaDB
    print("\n[Step 4/5] Upserting into ChromaDB persistent store...")
    store = ChromaVectorStore()
    if clear_existing:
        print("  • Clearing existing collection...")
        store.clear()

    upserted_count = store.upsert(chunks)
    print(f"  ✓ Upserted {upserted_count} chunks. Total in collection: {store.count()}.")

    # 5. Build and Save BM25 Keyword Index
    print("\n[Step 5/5] Building BM25 keyword index...")
    bm25_store = BM25Store()
    bm25_store.build_and_save(chunks)
    print(f"  ✓ Saved BM25 index to {bm25_store.persist_path}.")

    elapsed = round(time.time() - start_time, 2)
    # text-embedding-3-small is $0.02 per 1M tokens
    estimated_cost = (total_tokens / 1_000_000) * 0.02

    print("\n" + "=" * 70)
    print(" 🎉 Ingestion Completed Successfully!")
    print("=" * 70)
    print(f" Total Pages Processed : {len(pages)}")
    print(f" Total Chunks Indexed  : {len(chunks)}")
    print(f" Approximate Tokens    : ~{total_tokens:,}")
    print(f" Estimated OpenAI Cost : ~${estimated_cost:.5f} (₹{estimated_cost * 83:.3f})")
    print(f" Time Elapsed          : {elapsed} seconds")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Ingest Spectrum Modern History PDF into ChromaDB and BM25.")
    parser.add_argument(
        "--source",
        type=Path,
        default=SPECTRUM_PDF_PATH,
        help="Path to the PDF file (default: gs1_modern_history_spectrum.pdf)",
    )
    parser.add_argument(
        "--pages",
        type=str,
        default=None,
        help="Page range to ingest, e.g. '1-50' or 'all' (default: all)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ingest all pages in the PDF",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help="Batch size for OpenAI API embedding calls (default: 100)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing collection before ingesting",
    )

    args = parser.parse_args()
    page_range_str = "all" if args.all else args.pages

    try:
        run_ingestion(
            source_pdf=args.source,
            page_range_str=page_range_str,
            batch_size=args.batch_size,
            clear_existing=args.clear,
        )
    except Exception as e:
        print(f"\n[Error] Ingestion failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
