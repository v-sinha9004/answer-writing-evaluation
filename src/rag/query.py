"""Interactive Query CLI: Send any text/claim and inspect retrieved passages with citations."""

import argparse
import sys
from typing import Optional
from src.rag.retriever import get_retriever, HybridRetriever
from src.rag.schema import RetrievalResult


def format_result(rank: int, result: RetrievalResult) -> str:
    """Format a single RetrievalResult into a clean terminal card."""
    chunk = result.chunk
    meta = chunk.metadata

    dense_str = f"Rank {int(result.dense_score)}" if result.dense_score else "N/A"
    sparse_str = f"{result.sparse_score:.2f}" if result.sparse_score is not None else "N/A"

    border = "─" * 76
    header = (
        f"┌{border}┐\n"
        f"│ [Rank {rank}] Combined RRF Score: {result.combined_score:<8} "
        f"(Dense: {dense_str} | BM25: {sparse_str})\n"
        f"│ 📖 Resource: {meta.source_file} | Page: {meta.page_number} | Tokens: {meta.token_count}\n"
        f"│ 🔖 Chapter : {meta.chapter_title}\n"
        f"├{border}┤"
    )

    # Indent content slightly
    content_lines = chunk.content.strip().split("\n")
    formatted_content = "\n".join(f"│  {line}" for line in content_lines[:12])
    if len(content_lines) > 12:
        formatted_content += "\n│  [... content truncated for terminal preview ...]"

    footer = f"└{border}┘"
    return f"{header}\n{formatted_content}\n{footer}"


def display_results(query: str, results: list[RetrievalResult]):
    """Pretty print query and top retrieved results."""
    print("\n" + "=" * 78)
    print(f" 🔍 Query: \"{query}\"")
    print(f" 📊 Retrieved {len(results)} Passages from Modern History Store:")
    print("=" * 78 + "\n")

    if not results:
        print("  [No matching passages found. Have you ingested the PDF into ChromaDB?]")
        print("  Run: python -m src.rag.ingest --all\n")
        return

    for idx, res in enumerate(results, start=1):
        print(format_result(idx, res))
        print()


def interactive_mode(retriever: HybridRetriever, default_top_k: int = 3):
    """Run an interactive REPL query session."""
    print("=" * 78)
    print(" 🏛️  UPSC GS-1 Modern History RAG Query Interface (Interactive Mode)")
    print(" Type any question, candidate answer excerpt, or factual assertion to test.")
    print(" Commands: 'topk <N>' to adjust results count | 'exit' or 'quit' to end.")
    print("=" * 78 + "\n")

    top_k = default_top_k

    while True:
        try:
            query = input("\n📝 Enter query > ").strip()
            if not query:
                continue

            if query.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break

            if query.lower().startswith("topk "):
                try:
                    top_k = int(query.split()[1])
                    print(f"Top-K set to {top_k}")
                except Exception:
                    print("Invalid topk command. Usage: topk 3")
                continue

            results = retriever.search(query=query, top_k=top_k)
            display_results(query, results)

        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break
        except Exception as e:
            print(f"\n[Error executing search]: {e}")


def main():
    parser = argparse.ArgumentParser(description="Query the UPSC RAG Knowledge Base with optional paper/subject filters.")
    parser.add_argument("query", nargs="?", default=None, help="The query or claim text to search.")
    parser.add_argument("-k", "--top-k", type=int, default=3, help="Number of results to retrieve (default: 3).")
    parser.add_argument("--paper", type=str, default=None, help="Filter by GS Paper (e.g. 'GS-1', 'GS-2').")
    parser.add_argument("--subject", type=str, default=None, help="Filter by Subject (e.g. 'Modern History', 'Polity').")
    parser.add_argument("-i", "--interactive", action="store_true", help="Launch interactive query prompt.")

    args = parser.parse_args()

    try:
        retriever = get_retriever()
    except Exception as e:
        print(f"[Error initializing retriever]: {e}")
        sys.exit(1)

    where_filter = {}
    if args.paper:
        where_filter["paper"] = args.paper
    if args.subject:
        where_filter["subject"] = args.subject
    effective_filter = where_filter or None

    if args.interactive or not args.query:
        interactive_mode(retriever, default_top_k=args.top_k)
    else:
        results = retriever.search(query=args.query, top_k=args.top_k, where_filter=effective_filter)
        display_results(args.query, results)



if __name__ == "__main__":
    main()
