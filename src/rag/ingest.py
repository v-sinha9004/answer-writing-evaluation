"""CLI Ingestion script: Auto-discover or parse UPSC textbooks, generate embeddings, and index into ChromaDB + BM25."""

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from tqdm import tqdm

from src.config import (
    ensure_directories,
    get_resource_search_paths,
    BATCH_SIZE,
    EMBEDDING_MODEL,
    VECTOR_STORE_BACKEND,
)
from src.rag.pdf_loader import PDFLoader
from src.rag.chunker import TextbookChunker
from src.rag.embeddings import EmbeddingClient
from src.rag.store import ChromaVectorStore, SupabaseVectorStore, get_vector_store
from src.rag.retriever import BM25Store
from src.rag.schema import FactChunk


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


def detect_metadata_from_path(pdf_path: Path) -> Dict[str, str]:
    """Auto-detect UPSC paper (GS-1..4), subject name, and ID prefix from directory hierarchy.
    
    Convention:
        data/resources/<paper>/<subject_name>/<filename>.pdf
        e.g. data/resources/gs1/modern_history/spectrum.pdf
             -> paper="GS-1", subject="Modern History", id_prefix="modern_history"
    """
    pdf_path = pdf_path.resolve()
    parts = list(pdf_path.parts)
    filename = pdf_path.stem

    paper = "GS-1"
    subject = filename.replace("_", " ").title()

    # Search directory parts for GS paper code (e.g. gs1, gs2, gs3, gs4, gs-1, gs_1)
    gs_part_idx = -1
    for idx, part in enumerate(parts[:-1]):
        m = re.search(r"\bgs[_-]?([1-4])\b", part, re.IGNORECASE)
        if m:
            paper = f"GS-{m.group(1)}"
            gs_part_idx = idx
            break

    # If GS folder is found, the subfolder immediately below it is the subject
    if gs_part_idx != -1 and gs_part_idx < len(parts) - 2:
        subject_folder = parts[gs_part_idx + 1]
        subject = subject_folder.replace("_", " ").replace("-", " ").title()
    elif gs_part_idx != -1 and gs_part_idx == len(parts) - 2:
        # Fallback if folder itself is named gs1_subject
        folder_name = parts[gs_part_idx]
        cleaned = re.sub(r"gs[_-]?[1-4][_-]?", "", folder_name, flags=re.IGNORECASE).strip("_-")
        if cleaned:
            subject = cleaned.replace("_", " ").replace("-", " ").title()

    id_prefix = re.sub(r"[^a-zA-Z0-9]+", "_", subject.lower()).strip("_")
    resource_name = f"{subject} ({filename.replace('_', ' ').title()})"

    return {
        "paper": paper,
        "subject": subject,
        "resource_name": resource_name,
        "id_prefix": id_prefix[:20] if id_prefix else "chunk",
    }


def discover_resource_pdfs() -> List[Path]:
    """Find all resource PDFs in search directories."""
    discovered: List[Path] = []
    seen = set()
    for search_dir in get_resource_search_paths():
        if not search_dir.exists():
            continue
        for pdf_path in sorted(search_dir.rglob("*.pdf")):
            resolved = pdf_path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                discovered.append(pdf_path)
    return discovered


def run_ingestion(
    source_pdf: Optional[Path] = None,
    page_range_str: Optional[str] = None,
    batch_size: int = BATCH_SIZE,
    clear_existing: bool = False,
    override_paper: Optional[str] = None,
    override_subject: Optional[str] = None,
    dry_run: bool = False,
    backend: Optional[str] = None,
):
    """Run full ingestion pipeline for one or all discovered syllabus PDFs."""
    ensure_directories()
    page_range = parse_page_range(page_range_str)

    effective_backend = (backend or VECTOR_STORE_BACKEND or "supabase").strip().lower()

    # Determine files to process
    if source_pdf:
        target_pdfs = [Path(source_pdf)]
    else:
        target_pdfs = discover_resource_pdfs()

    if not target_pdfs:
        print("❌ No PDF files found to ingest. Place PDFs in data/resources/gs<1-4>/<subject_name>/")
        return

    print("=" * 76)
    print(" 📚 UPSC Multi-Subject Knowledge Base Ingestion Pipeline")
    print("=" * 76)
    print(f" Target Vector Backend    : {effective_backend}")
    print(f" Total PDF Resources Found: {len(target_pdfs)}")
    print(f" Embedding Model          : {EMBEDDING_MODEL}")
    print(f" Batch Size               : {batch_size}")
    print(f" Clear Existing Collection: {clear_existing}")
    print("=" * 76)

    # Display detected metadata for each target PDF
    print("\n🔍 Resource Discovery & Metadata Mapping:")
    pdf_metas: List[Tuple[Path, Dict[str, str]]] = []
    for p in target_pdfs:
        meta = detect_metadata_from_path(p)
        if override_paper:
            meta["paper"] = override_paper
        if override_subject:
            meta["subject"] = override_subject
            meta["id_prefix"] = re.sub(r"[^a-zA-Z0-9]+", "_", override_subject.lower()).strip("_")
        pdf_metas.append((p, meta))
        print(f"  • {p.name}")
        print(f"    └── Paper: {meta['paper']} | Subject: {meta['subject']} | Prefix: {meta['id_prefix']}")

    if dry_run:
        print("\n[Dry Run Completed] No documents were parsed or embedded.")
        return

    start_time = time.time()
    all_chunks: List[FactChunk] = []

    # 1. Process each PDF
    chunker = TextbookChunker()
    for idx, (pdf_file, meta) in enumerate(pdf_metas, start=1):
        print(f"\n[Resource {idx}/{len(pdf_metas)}] Processing '{pdf_file.name}'...")
        loader = PDFLoader(pdf_path=pdf_file, subject_name=meta["subject"])
        pages = loader.load_pages(page_range=page_range)
        print(f"  ✓ Extracted {len(pages)} valid pages.")
        if not pages:
            continue

        chunks = chunker.chunk_pages(
            pages=pages,
            paper=meta["paper"],
            subject=meta["subject"],
            resource_name=meta["resource_name"],
            id_prefix=meta["id_prefix"],
        )
        print(f"  ✓ Created {len(chunks)} chunks for {meta['paper']} {meta['subject']}.")
        all_chunks.extend(chunks)


    if not all_chunks:
        print("\n❌ No chunks produced from any PDF. Exiting.")
        return

    total_tokens = sum(c.metadata.token_count for c in all_chunks)
    print(f"\n[Summary] Total chunks across all books: {len(all_chunks)} (Tokens: ~{total_tokens:,})")

    # 2. Generate OpenAI Embeddings
    print("\n[Step 2/4] Generating OpenAI vector embeddings...")
    embedding_client = EmbeddingClient()
    prefixed_texts = [c.prefixed_content for c in all_chunks]

    all_embeddings = []
    with tqdm(total=len(all_chunks), desc="  Embedding", unit="chunk") as pbar:
        for i in range(0, len(prefixed_texts), batch_size):
            batch = prefixed_texts[i : i + batch_size]
            batch_vectors = embedding_client.embed_texts(batch, batch_size=batch_size)
            all_embeddings.extend(batch_vectors)
            pbar.update(len(batch))

    for chunk, emb in zip(all_chunks, all_embeddings):
        chunk.embedding = emb

    # 3. Upsert into Vector Store
    store = get_vector_store(backend=backend)
    backend_label = "Supabase pgvector" if isinstance(store, SupabaseVectorStore) else "ChromaDB (SQLite)"
    print(f"\n[Step 3/4] Upserting into {backend_label} store...")
    if clear_existing:
        print("  • Clearing existing collection...")
        store.clear()

    upserted_count = store.upsert(all_chunks)
    print(f"  ✓ Upserted {upserted_count} chunks. Total in collection: {store.count()}.")

    # 4. Build and Save BM25 Keyword Index
    print("\n[Step 4/4] Building BM25 keyword index...")
    bm25_store = BM25Store()
    bm25_store.build_and_save(all_chunks)
    print(f"  ✓ Saved BM25 index to {bm25_store.persist_path}.")

    elapsed = round(time.time() - start_time, 2)
    estimated_cost = (total_tokens / 1_000_000) * 0.02

    print("\n" + "=" * 76)
    print(" 🎉 Multi-Subject Ingestion Completed Successfully!")
    print("=" * 76)
    print(f" Total Books Processed : {len(pdf_metas)}")
    print(f" Total Chunks Indexed  : {len(all_chunks)}")
    print(f" Approximate Tokens    : ~{total_tokens:,}")
    print(f" Estimated OpenAI Cost : ~${estimated_cost:.5f} (₹{estimated_cost * 83:.3f})")
    print(f" Time Elapsed          : {elapsed} seconds")
    print("=" * 76)


def main():
    parser = argparse.ArgumentParser(
        description="Ingest UPSC textbook PDFs into ChromaDB and BM25 with automatic GS/Subject detection."
    )
    parser.add_argument(
        "--source",
        "--pdf",
        type=Path,
        default=None,
        dest="source",
        help="Path to a specific PDF file. If omitted, all PDFs in resources/ will be discovered and ingested.",
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
        "--paper",
        type=str,
        default=None,
        help="Explicitly override GS Paper (e.g. 'GS-2'). Defaults to auto-detection from directory path.",
    )
    parser.add_argument(
        "--subject",
        type=str,
        default=None,
        help="Explicitly override Subject (e.g. 'Indian Polity'). Defaults to auto-detection from directory path.",
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
    parser.add_argument(
        "--backend",
        type=str,
        default=None,
        choices=["supabase", "sqlite", "chroma"],
        help=f"Target vector store backend (default: from .env, currently '{VECTOR_STORE_BACKEND}')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and display discovered PDFs and detected metadata without running embeddings",
    )

    args = parser.parse_args()
    page_range_str = "all" if args.all else args.pages

    try:
        run_ingestion(
            source_pdf=args.source,
            page_range_str=page_range_str,
            batch_size=args.batch_size,
            clear_existing=args.clear,
            override_paper=args.paper,
            override_subject=args.subject,
            dry_run=args.dry_run,
            backend=args.backend,
        )
    except Exception as e:
        print(f"\n[Error] Ingestion failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

