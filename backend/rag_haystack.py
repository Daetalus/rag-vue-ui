from haystack import Pipeline
from haystack.components.builders.prompt_builder import PromptBuilder
from haystack.core.component import component, Component
from haystack.dataclasses import Document
import time
import re
from typing import List, Optional, Dict, Any

# Chroma
from haystack_integrations.document_stores.chroma import ChromaDocumentStore
from haystack_integrations.components.retrievers.chroma import ChromaEmbeddingRetriever

# Ollama
from haystack_integrations.components.generators.ollama import OllamaGenerator
from haystack_integrations.components.embedders.ollama.text_embedder import OllamaTextEmbedder

# BM25 for keyword search
try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    print("Warning: rank-bm25 not installed. Using semantic search only.")
    print("Install with: pip install rank-bm25")
    BM25_AVAILABLE = False

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import asyncio
import queue
import threading

# Global synchronous queue for tokens
_sync_token_queue = queue.Queue()

def collect_and_print(chunk):
    text = chunk.content
    print(text, end="", flush=True)
    _sync_token_queue.put(text)

@component
class TitleRetriever:
    """
    Title Retriever: Query the document titles and return title-URL pairs
    """
    def __init__(self, title_store: ChromaDocumentStore, top_k: int = 3):
        self.title_store = title_store
        self.top_k = top_k

        self.title_embedder = OllamaTextEmbedder(
            url="http://localhost",
            model="bge-m3"
        )

        self.title_embedding_retriever = ChromaEmbeddingRetriever(
            document_store=title_store,
            top_k=top_k,
        )

    @component.output_types(document_title_and_url=List[Dict])
    def run(self, query: str) -> Dict[str, List[Dict]]:
        """Execute title retrieval and return title-URL pairs"""

        rag_pipeline = Pipeline()
        rag_pipeline.add_component("embedder", self.title_embedder)
        rag_pipeline.add_component("embedding_retriever", self.title_embedding_retriever)

        # Connect components
        rag_pipeline.connect("embedder.embedding", "embedding_retriever.query_embedding")
        results = rag_pipeline.run(
            {
                "embedder": {"text": query},
            },
        )

        print(f"Query: {query}")
        print("Title Retrieval Results:")
        print(results)
        title_and_url = []
        if results['embedding_retriever']['documents']:
            docs = results['embedding_retriever']['documents'][:self.top_k]
            for doc in docs:
                print(f"Query title debug: - {doc.content} (URL: {doc.meta['url']}) Score: {doc.score}")
                title_and_url.append({"Title": doc.content, "URL": doc.meta['url']})

        return {"document_title_and_url": title_and_url}

@component
class HybridRetriever:
    """
    Hybrid Retriever: Semantic search + Keyword search + Title weighting
    Adapted to work with the new technical document splitter structure
    """

    def __init__(self, document_store, title_store: ChromaDocumentStore, top_k: int = 10, title_weight: float = 3.0):
        self.document_store = document_store
        self.title_store = title_store
        self.top_k = top_k
        self.title_weight = title_weight

        # Semantic search retriever - retrieve more candidate documents
        self.embedding_retriever = ChromaEmbeddingRetriever(
            document_store=document_store,
            top_k=min(top_k * 3, 80)  # Increased to 80 for better coverage with chunked documents
        )

        # Prepare all documents for keyword search
        self._prepare_document_corpus()



    def _prepare_document_corpus(self):
        """Prepare document corpus and BM25 index - adapted for chunked documents"""
        print("🔄 Preparing document corpus for hybrid search...")

        try:
            # Get all documents
            all_docs = self.document_store.filter_documents()
            print(f"📚 Loading {len(all_docs)} document chunks...")

            self.all_documents = all_docs
            self.bm25_index = None

            if BM25_AVAILABLE and all_docs:
                # Prepare BM25 corpus with enhanced handling for chunked documents
                corpus = []

                for doc in all_docs:
                    # Get title from doc_name (from original file name)
                    doc_name = doc.meta.get('doc_name', '')
                    title = doc.meta.get('title', '') or doc_name
                    content = doc.content or ''
                    # Get chunk type for better weighting
                    chunk_type = doc.meta.get('chunk_type', 'content')

                    # Build enhanced text, ensure doc_name is always included and weighted
                    # Use doc_name as main title for weighting
                    effective_title = doc_name  # Use doc_name as primary identifier
                    if title and title != doc_name:
                        effective_title = f"{effective_title} {title}"  # If there's also metadata title, add it

                    # Build enhanced_text based on chunk_type
                    if chunk_type == 'instructions':
                        # Instructions are highly relevant - boost title and content
                        enhanced_text = f"{effective_title} " * int(self.title_weight * 2) + f"{content} {content}"  # Content also repeated once for increased weight
                    elif chunk_type == 'code':
                        # Code chunks - moderate boost to title
                        enhanced_text = f"{effective_title} " * int(self.title_weight * 1.5) + content
                    elif chunk_type == 'section' and any(header in content for header in ['#', '##', '###']):
                        # Section headers - very high boost to title
                        enhanced_text = f"{effective_title} " * int(self.title_weight * 3) + content
                    else:
                        # Regular content - boost title
                        enhanced_text = f"{effective_title} " * int(self.title_weight * 1.5) + content  # Slightly increase regular content title weight

                    # Simple tokenization (lowercase, split by space and punctuation)
                    tokens = re.findall(r'\b\w+\b', enhanced_text.lower())
                    corpus.append(tokens)

                # Create BM25 index
                if corpus and any(tokens for tokens in corpus):
                    self.bm25_index = BM25Okapi(corpus)
                    print(f"✅ BM25 index created successfully with enhanced chunked document support")
                else:
                    print("❌ Empty corpus, BM25 disabled")

        except Exception as e:
            print(f"❌ Error preparing document corpus: {e}")
            self.all_documents = []
            self.bm25_index = None

    def _keyword_search(self, query: str, top_k: int) -> List[Document]:
        """Keyword search adapted for chunked documents"""
        if not self.all_documents:
            return []

        if self.bm25_index and BM25_AVAILABLE:
            return self._bm25_search(query, top_k)
        else:
            return self._simple_keyword_search(query, top_k)

    def _bm25_search(self, query: str, top_k: int) -> List[Document]:
        """BM25 search with enhanced scoring for chunked documents"""
        try:
            query_tokens = re.findall(r'\b\w+\b', query.lower())
            if not query_tokens:
                return []

            scores = self.bm25_index.get_scores(query_tokens)

            # Get top-k results with enhanced scoring
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k * 2]  # Get more candidates

            bm25_docs = []
            doc_name_scores = {}  # Track best score per document name

            for idx in top_indices:
                if idx < len(self.all_documents):
                    doc = self.all_documents[idx]
                    doc_name = doc.meta.get('doc_name', f'unknown_{idx}')
                    base_score = float(scores[idx])

                    # Apply chunk type boost
                    chunk_type = doc.meta.get('chunk_type', 'content')
                    if chunk_type == 'instructions':
                        base_score *= 1.3
                    elif chunk_type == 'section':
                        base_score *= 1.2
                    elif chunk_type == 'troubleshooting':
                        base_score *= 1.1

                    # Keep track of best score per document
                    if doc_name not in doc_name_scores or base_score > doc_name_scores[doc_name]:
                        doc_name_scores[doc_name] = base_score

                    # Create document copy and add enhanced BM25 score
                    doc_copy = Document(
                        content=doc.content,
                        meta=doc.meta.copy(),
                        id=doc.id
                    )
                    doc_copy.score = base_score
                    bm25_docs.append(doc_copy)

            # Sort and return top results
            bm25_docs.sort(key=lambda x: x.score, reverse=True)
            return bm25_docs[:top_k]

        except Exception as e:
            print(f"❌ BM25 search error: {e}")
            return []

    def _simple_keyword_search(self, query: str, top_k: int) -> List[Document]:
        """Simple keyword matching adapted for chunked documents"""
        query_terms = set(re.findall(r'\b\w+\b', query.lower()))
        if not query_terms:
            return []

        scored_docs = []
        doc_name_groups = {}  # Group chunks by original document

        for doc in self.all_documents:
            doc_name = doc.meta.get('doc_name', 'unknown')
            title = doc_name.lower()  # Use doc_name as title
            content = (doc.content or '').lower()
            chunk_type = doc.meta.get('chunk_type', 'content')

            # Calculate match score
            title_matches = sum(1 for term in query_terms if term in title)
            content_matches = sum(1 for term in query_terms if term in content)

            # Apply chunk type weighting
            chunk_weight = 1.0
            if chunk_type == 'instructions':
                chunk_weight = 1.3
            elif chunk_type == 'section':
                chunk_weight = 1.2
            elif chunk_type == 'troubleshooting':
                chunk_weight = 1.1

            # Title matches have higher weight, adjusted for chunked structure
            total_score = (title_matches * self.title_weight + content_matches) * chunk_weight

            if total_score > 0:
                doc_copy = Document(
                    content=doc.content,
                    meta=doc.meta.copy(),
                    id=doc.id
                )
                doc_copy.score = total_score
                scored_docs.append(doc_copy)

        # Sort by score and return top-k
        scored_docs.sort(key=lambda x: x.score, reverse=True)
        return scored_docs[:top_k]

    def _calculate_title_relevance_bonus(self, query: str, doc: Document) -> float:
        """Calculate title relevance bonus adapted for chunked documents"""
        # Use doc_name (original file name) as the primary title source
        doc_name = doc.meta.get('doc_name', '')
        title = (doc.meta.get('title', '') or doc_name).lower()
        query_lower = query.lower()
        chunk_type = doc.meta.get('chunk_type', 'content')

        # Extract query terms
        query_terms = set(re.findall(r'\b\w+\b', query_lower))
        # Calculate doc_name and title matching separately
        doc_name_terms = set(re.findall(r'\b\w+\b', doc_name.lower()))
        title_terms = set(re.findall(r'\b\w+\b', title))

        # Calculate doc_name exact matches and Jaccard similarity (given higher weight)
        doc_name_exact_matches = sum(1 for term in query_terms if term in doc_name_terms and len(term) > 2)  # Reduced minimum length requirement
        doc_name_jaccard_bonus = 0
        if doc_name_terms and query_terms:
            dn_intersection = len(query_terms.intersection(doc_name_terms))
            dn_union = len(query_terms.union(doc_name_terms))
            # doc_name Jaccard similarity given higher weight
            doc_name_jaccard_bonus = (dn_intersection / dn_union) * 5.0  # Increased multiplier

        # Calculate title exact matches and Jaccard similarity (keep original logic or adjust slightly)
        title_exact_matches = sum(1 for term in query_terms if term in title_terms and len(term) > 2)
        title_jaccard_bonus = 0
        if title_terms and query_terms:
            t_intersection = len(query_terms.intersection(title_terms))
            t_union = len(query_terms.union(title_terms))
            title_jaccard_bonus = (t_intersection / t_union) * 2.0

        # Check for phrase matches
        phrase_bonus = 0
        query_words = query_lower.split()
        for i in range(len(query_words) - 1):
            bigram = f"{query_words[i]} {query_words[i+1]}"
            if bigram in title:
                phrase_bonus += 3.0

        # Chunk type bonus - sections with headers get extra boost
        chunk_bonus = 0
        if chunk_type == 'section' and any(h in doc.content for h in ['#', '##', '###']):
            chunk_bonus = 2.0
        elif chunk_type == 'instructions':
            chunk_bonus = 1.5

        # If it's the first chunk (chunk_id is 0 or doesn't exist), give extra reward, as it usually contains the title
        if doc.meta.get('chunk_id', 0) == 0:
            chunk_bonus += 1.0

        total_bonus = (
            (doc_name_exact_matches * self.title_weight * 2) +  # doc_name exact match weight doubled
            (doc_name_jaccard_bonus * 2) +  # doc_name Jaccard weight doubled
            (title_exact_matches * self.title_weight) +
            (title_jaccard_bonus) +
            (phrase_bonus * 1.5) +  # Slightly increase phrase matching weight
            (chunk_bonus * 2)  # Slightly increase chunk type and position weight
        ) * 10  # Keep original amplification factor

        # Debug output for significant bonuses
        if total_bonus > 5.0:
            print(f"🎯 Title relevance bonus for '{doc_name}' ({chunk_type}, chunk_id={doc.meta.get('chunk_id', '?')}): {total_bonus:.2f}")
            print(f"   - DN Exact: {doc_name_exact_matches}, DN Jaccard: {doc_name_jaccard_bonus:.2f}")
            print(f"   - Title Exact: {title_exact_matches}, Title Jaccard: {title_jaccard_bonus:.2f}")
            print(f"   - Phrase: {phrase_bonus}, Chunk: {chunk_bonus}")

        return total_bonus

    def _merge_and_rerank(self, query: str, semantic_docs: List[Document], keyword_docs: List[Document], title_url_list: List[str]) -> List[Document]:
        """Enhanced merge and rerank for chunked documents with document-level grouping"""

        # Create mapping from document ID to document
        doc_map = {}
        doc_name_best_chunks = {}  # Track best chunks per original document

        # Add semantic search results
        for doc in semantic_docs:
            doc_id = doc.id or hash(doc.content[:100])
            doc_name = doc.meta.get('doc_name', 'unknown')

            if doc_id not in doc_map:
                if not hasattr(doc, 'score'):
                    doc.score = 0.0
                doc_map[doc_id] = doc

                # Track best chunk per document name for diversity
                if doc_name not in doc_name_best_chunks or doc.score > doc_name_best_chunks[doc_name].score:
                    doc_name_best_chunks[doc_name] = doc

        # Add keyword search results, merge scores
        for doc in keyword_docs:
            doc_id = doc.id or hash(doc.content[:100])
            doc_name = doc.meta.get('doc_name', 'unknown')

            if doc_id in doc_map:
                doc_map[doc_id].score += doc.score
            else:
                doc_map[doc_id] = doc

            # Update best chunk tracking
            if doc_name not in doc_name_best_chunks or doc.score > doc_name_best_chunks[doc_name].score:
                doc_name_best_chunks[doc_name] = doc

        # Convert to list and perform final ranking
        merged_docs = list(doc_map.values())

        # Greatly boost scores for documents matching top titles
        for doc in merged_docs:
            if doc.meta.get('url') in title_url_list:
                doc.score *= 40  # Boost score significantly, empirical value by Boxiang

        print("********************* Merged docs ***********")
        for doc in merged_docs:
            print(doc.meta.get('doc_name'), doc.score)

        # Final sorting
        merged_docs.sort(key=lambda x: x.score, reverse=True)

        return merged_docs[:self.top_k]

    @component.output_types(documents=List[Document])
    def run(self, query_embedding: List[float], query: str, document_title_and_url: Optional[List[Dict]] = None) -> Dict[str, List[Document]]:
        """Execute hybrid retrieval adapted for chunked documents with TitleRetriever integration"""
        print(f"🔍 Hybrid retrieval for: '{query}' (chunked document mode)")

        # 1. Extract URLs from TitleRetriever results (if provided)
        title_url_list = []
        if document_title_and_url:
            title_url_list = [doc.get("URL", "") for doc in document_title_and_url if doc.get("URL")]
            print(f"📋 Using {len(title_url_list)} title URLs for boosting")

        # 2. Semantic search with a larger pool
        semantic_results = self.embedding_retriever.run(query_embedding=query_embedding, top_k=50)
        semantic_docs = semantic_results.get("documents", [])
        print(f"📊 Semantic search: {len(semantic_docs)} document chunks")

        # 3. Keyword search
        keyword_docs = self._keyword_search(query, 50)
        print(f"📊 Keyword search: {len(keyword_docs)} document chunks")

        # 4. Merge and rerank with title boosting
        final_docs = self._merge_and_rerank(query, semantic_docs, keyword_docs, title_url_list)
        print(f"📊 Final results: {len(final_docs)} document chunks")

        # 5. Display top results with chunk information
        print("🏆 Top retrieval results:")
        doc_names_seen = set()
        for i, doc in enumerate(final_docs[:10]):
            doc_name = doc.meta.get('doc_name', 'unknown')
            chunk_type = doc.meta.get('chunk_type', 'content')
            chunk_id = doc.meta.get('chunk_id', '?')
            score = getattr(doc, 'score', 0.0)

            is_new_doc = doc_name not in doc_names_seen
            doc_names_seen.add(doc_name)

            marker = "🆕" if is_new_doc else "  "
            boost_marker = "🚀" if doc.meta.get('url') in title_url_list else "  "
            print(f"  {i+1:2d}. {marker}{boost_marker} [Score: {score:6.2f}] {doc_name} (chunk {chunk_id}, {chunk_type})")
            print(f"       Content: {doc.content[:80]}...")

        return {"documents": final_docs}


class CleanHybridRAGSystem:
    def __init__(self, base_url: str, general_model: str, embed_model: str,
                 chroma_path: str = "./nexedi_doc_vec_haystack",  # UPDATED default path
                 collection_name: str = "nexedi_doc_haystack"):   # UPDATED default collection
        """
        Clean Hybrid RAG System adapted for new indexing script
        """
        self.base_url = base_url
        self.general_model = general_model
        self.embed_model = embed_model
        self.chroma_path = chroma_path
        self.collection_name = collection_name

        # Initialize Chroma document store
        self.document_store = ChromaDocumentStore(
            persist_path=self.chroma_path,
            collection_name=self.collection_name
        )
        self.title_store = ChromaDocumentStore(
            persist_path="./nexedi_doc_title_vec_haystack",
            collection_name="nexedi_doc_titles"
        )

        # Create components
        self.text_embedder = OllamaTextEmbedder(
            url=self.base_url,
            model=self.embed_model,
            timeout=60,
        )

        # Initialize TitleRetriever
        self.title_retriever = TitleRetriever(
            title_store=self.title_store,
            top_k=3
        )

        # Hybrid retriever adapted for chunked documents
        self.hybrid_retriever = HybridRetriever(
            document_store=self.document_store,
            title_store=self.title_store,
            top_k=8,  # Increased for chunked documents
            title_weight=6.0  # Increased title weight for better relevance
        )

        # Generator
        self.generator = OllamaGenerator(
            url=self.base_url,
            model=self.general_model,
            streaming_callback=collect_and_print,
            timeout=120,
            generation_kwargs={
                "temperature": 0.2,
                "top_p": 0.9,
                "max_tokens": 2048
            }
        )

        # Enhanced prompt template optimized for chunked technical documents
        prompt_template = """You are a helpful AI assistant specialized in technical documentation analysis.

DOCUMENT CHUNKS AVAILABLE:
{% for doc in documents %}
=== Chunk {{ loop.index }} ===
Original Document: {{ doc.meta.doc_name or "Unknown Document" }}
Chunk Type: {{ doc.meta.chunk_type or "content" }}
Chunk ID: {{ doc.meta.chunk_id or "?" }}
Relevance Score: {{ doc.score if doc.score is defined else "N/A" }}
Content: {{ doc.content }}

{% endfor %}

CRITICAL INSTRUCTIONS FOR CHUNKED DOCUMENT ANALYSIS:

1. **DOCUMENT RECONSTRUCTION**: The information is split into chunks from original technical documents. Piece the chunks back together mentally to understand the full context.

2. **CHUNK TYPE AWARENESS**:
   - "instructions" chunks: Step-by-step procedures, installation guides
   - "code" chunks: Code snippets, configuration examples
   - "section" chunks: Headers and structured content
   - "troubleshooting" chunks: Error resolution, problem-solving
   - "list" chunks: Numbered lists, bullet points

3. **CROSS-CHUNK ANALYSIS**:
   - Look for chunks from the same original document (same doc_name)
   - Combine information from related chunks to provide complete answers
   - Pay special attention to instruction sequences that may be split across chunks

4. **PRIORITIZATION**:
   - Higher scored chunks are more relevant to the query
   - "instructions" and "troubleshooting" chunks often contain the most actionable information
   - "section" chunks with headers provide important context

5. **COMPREHENSIVE ANSWERS**:
   - Use multiple chunks to build complete, step-by-step answers
   - Reference the original document names when citing information
   - Include all relevant technical details found across chunks

REFERENCE SECTION:
{% for doc in document_title_and_url %}
=== Reference {{ loop.index }} ===
Title: {{ doc.Title }}
URL: {{ doc.URL }}
{% endfor %}

6. **REFERENCE DOCUMENTS**:
   - Use the title and URL above to form a "See more" section at the end of answer
   - The "See more" section should have the name and URL
   - Only one "See more" section is enough

USER QUESTION: {{ query }}

ANSWER (provide a comprehensive response using the chunked information):"""

        self.prompt_builder = PromptBuilder(
            template=prompt_template,
            variables=["documents", "query", "document_title_and_url"],
            required_variables=["documents", "query"]
        )

        # Build Pipeline
        self.rag_pipeline = Pipeline()
        self.rag_pipeline.add_component("text_embedder", self.text_embedder)
        self.rag_pipeline.add_component("title_retriever", self.title_retriever)
        self.rag_pipeline.add_component("hybrid_retriever", self.hybrid_retriever)
        self.rag_pipeline.add_component("prompt_builder", self.prompt_builder)
        self.rag_pipeline.add_component("generator", self.generator)

        # Connect components
        self.rag_pipeline.connect("text_embedder.embedding", "hybrid_retriever.query_embedding")
        self.rag_pipeline.connect("title_retriever.document_title_and_url", "hybrid_retriever.document_title_and_url")
        self.rag_pipeline.connect("title_retriever.document_title_and_url", "prompt_builder.document_title_and_url")
        self.rag_pipeline.connect("hybrid_retriever.documents", "prompt_builder.documents")
        self.rag_pipeline.connect("prompt_builder", "generator")

        print("✅ Clean Hybrid RAG Pipeline initialized for chunked documents with TitleRetriever!")

    def _print_debug_prompt(self, prompt: str, documents: List[Document], query: str):
        """Print complete prompt for debugging chunked documents"""
        print("\n" + "="*100)
        print("🐛 DEBUG: COMPLETE PROMPT (CHUNKED DOCUMENTS)")
        print("="*100)

        print(f"Query: {query}")
        print(f"Retrieved Document Chunks: {len(documents)}")

        # Group chunks by original document
        doc_groups = {}
        for doc in documents:
            doc_name = doc.meta.get('doc_name', 'unknown')
            if doc_name not in doc_groups:
                doc_groups[doc_name] = []
            doc_groups[doc_name].append(doc)

        print(f"Chunks from {len(doc_groups)} different original documents:")
        for doc_name, chunks in doc_groups.items():
            chunk_types = [chunk.meta.get('chunk_type', 'unknown') for chunk in chunks]
            print(f"  📄 {doc_name}: {len(chunks)} chunks ({', '.join(set(chunk_types))})")

        for i, doc in enumerate(documents):
            doc_name = doc.meta.get('doc_name', 'unknown')
            chunk_type = doc.meta.get('chunk_type', 'content')
            chunk_id = doc.meta.get('chunk_id', '?')
            score = getattr(doc, 'score', 'N/A')
            print(f"\nChunk {i+1}: {doc_name} (chunk {chunk_id}, {chunk_type}, score: {score})")
            print(f"Content preview: {doc.content[:200]}...")

        print(f"\n{'='*50} FULL PROMPT {'='*50}")
        print(prompt)
        print("="*100)

    async def query(self, question: str):
        """Query method adapted for chunked documents with TitleRetriever integration"""
        # Clear the queue
        while not _sync_token_queue.empty():
            _sync_token_queue.get_nowait()

        pipeline_results = []
        debug_prompt = []

        def run_pipeline_sync():
            try:
                print(f"🔍 Processing query: '{question}' (chunked document mode with TitleRetriever)")

                results = self.rag_pipeline.run(
                    {
                        "text_embedder": {"text": question},
                        "title_retriever": {"query": question},
                        "hybrid_retriever": {"query": question},
                        "prompt_builder": {"query": question}
                    },
                    include_outputs_from=["title_retriever", "hybrid_retriever", "prompt_builder"]
                )

                print("==============================")

                # Capture and print the complete prompt for debugging
                if "prompt_builder" in results:
                    prompt_result = results["prompt_builder"]
                    if hasattr(prompt_result, 'prompt') or isinstance(prompt_result, str):
                        prompt_text = prompt_result.prompt if hasattr(prompt_result, 'prompt') else str(prompt_result)
                        debug_prompt.append(prompt_text)
                        self._print_debug_prompt(
                            prompt_text,
                            results["hybrid_retriever"].get("documents", []),
                            question
                        )

                pipeline_results.append(results)

            except Exception as e:
                print(f"❌ Pipeline error: {e}")
                import traceback
                traceback.print_exc()
            finally:
                _sync_token_queue.put(None)

        pipeline_thread = threading.Thread(target=run_pipeline_sync)
        pipeline_thread.start()

        full_response = ""
        print(f"\n🤖 Generating response for chunked documents with TitleRetriever...")

        while True:
            token = await asyncio.to_thread(_sync_token_queue.get)
            if token is None:
                break
            full_response += token
            yield {"type": "token", "data": token}

        pipeline_thread.join()
        results = pipeline_results[0] if pipeline_results else {}

        source_documents_for_frontend = []
        title_documents_for_frontend = []

        # Process title retrieval results
        # if "title_retriever" in results and results["title_retriever"]["document_title_and_url"]:
        #     title_docs = results["title_retriever"]["document_title_and_url"]
        #     print(f"\n📋 Title retrieval results: {len(title_docs)} documents")
        #     for title_doc in title_docs:
        #         title_documents_for_frontend.append({
        #             "title": title_doc.get("Title", "Unknown Title"),
        #             "url": title_doc.get("URL", "")
        #         })
        #         print(f"  📄 {title_doc.get('Title', 'Unknown Title')}: {title_doc.get('URL', '')}")

        if "hybrid_retriever" in results and results["hybrid_retriever"]["documents"]:
            docs = results["hybrid_retriever"]["documents"]

            # Group chunks by original document for better presentation
            doc_groups = {}
            for doc in docs:
                doc_name = doc.meta.get('doc_name', 'Unknown Document')
                if doc_name not in doc_groups:
                    doc_groups[doc_name] = []
                doc_groups[doc_name].append(doc)

            # Create source documents grouped by original document
            for doc_name, chunks in doc_groups.items():
                # Get best chunk for snippet
                best_chunk = max(chunks, key=lambda x: getattr(x, 'score', 0.0))
                avg_score = sum(getattr(chunk, 'score', 0.0) for chunk in chunks) / len(chunks)

                source_documents_for_frontend.append({
                    "doc_name": doc_name,
                    "source": best_chunk.meta.get("source", ""),
                    "url": best_chunk.meta.get("url", ""),
                    "content_snippet": best_chunk.content[:200],
                    "score": avg_score,
                    "chunk_count": len(chunks),
                    "chunk_types": list(set(chunk.meta.get('chunk_type', 'content') for chunk in chunks))
                })

        # Print final debug summary
        if debug_prompt:
            print(f"   - Prompt length: {len(debug_prompt[0])} characters")

        yield {
            "type": "final",
            "data": {
                "answer": full_response,
                "source_documents": source_documents_for_frontend,
                "title_documents": title_documents_for_frontend,
                "confidence": "high"
            }
        }

# FastAPI application
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Updated configuration to match your new setup
BASE_URL = "http://localhost"
GENERAL_MODEL = "hf.co/unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF:Q4_K_XL"
# EMBED_MODEL = "nomic-embed-text"  # Updated to match your new embedding model
EMBED_MODEL = "bge-m3"  # Updated to match your new embedding model

# Updated paths and collection name to match your new indexing script
rag_system = CleanHybridRAGSystem(
    base_url=BASE_URL,
    general_model=GENERAL_MODEL,
    embed_model=EMBED_MODEL,
    # chroma_path="./nexedi_doc_vec_haystack",      # Match your indexing script path
    # collection_name="nexedi_doc_haystack"        # Match your indexing script collection
    chroma_path="./nexedi_doc_vec_haystack_v3",      # Match your indexing script path
    collection_name="nexedi_doc_haystack_v3"        # Match your indexing script collection
)

class QuestionRequest(BaseModel):
    question: str

@app.post("/chat")
async def chat(request: QuestionRequest):
    from fastapi.responses import StreamingResponse
    import json

    async def generate_response():
        async for item in rag_system.query(request.question):
            if item["type"] == "token":
                yield f"data: {json.dumps({'type': 'token', 'data': item['data']})}\n\n"
            elif item["type"] == "final":
                yield f"data: {json.dumps({'type': 'final', 'data': item['data']})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate_response(), media_type="text/plain")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clean Hybrid RAG System - Chunked Documents with TitleRetriever")
    parser.add_argument("--question", type=str, required=True, help="Question to ask")
    args = parser.parse_args()

    async def run_test_query(question: str):
        print(f"Question: {question}")
        print("="*80)

        full_answer = ""
        source_documents = []
        title_documents = []

        async for item in rag_system.query(question):
            if item["type"] == "token":
                full_answer += item["data"]
            elif item["type"] == "final":
                result = item["data"]
                source_documents = result["source_documents"]
                title_documents = result.get("title_documents", [])

        # print("\n" + "="*80)

    asyncio.run(run_test_query(args.question))
