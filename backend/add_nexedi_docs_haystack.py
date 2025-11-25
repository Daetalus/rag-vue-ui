import os
import sys
import hashlib
import json
import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from haystack import Pipeline
from haystack.components.preprocessors import DocumentCleaner, DocumentSplitter
from haystack.components.writers import DocumentWriter
from haystack_integrations.document_stores.chroma import ChromaDocumentStore
from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder
from haystack.dataclasses import Document
from haystack.document_stores.types import DuplicatePolicy

from haystack.core.component import component
from haystack.core.serialization import default_to_dict, default_from_dict

# Add backend to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def calculate_file_hash(file_path: str) -> str:
    """Calculates the SHA256 hash of a file's content."""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

@component
class DebugPrinter:
    """
    A simple Haystack component to print documents for debugging.
    It passes the documents through unchanged.
    """
    def __init__(self, name: str = "DebugPrinter"):
        self.name = name

    def to_dict(self):
        # Required for serialization if needed
        return default_to_dict(self, name=self.name)

    @classmethod
    def from_dict(cls, data):
        # Required for deserialization if needed
        return default_from_dict(cls, data)

    @component.output_types(documents=list)
    def run(self, documents):
        print(f"--- {self.name} Output ---")
        for i, doc in enumerate(documents):
            print(f"Document {i+1} Content Preview (first 200 chars):\n{repr(doc.content[:200])}\n---")
            # Optional: Print full content or meta if needed for debugging
            # print(f"Document {i+1} Full Content:\n{doc.content}\n---")
            # print(f"Document {i+1} Meta: {doc.meta}\n---")
        return {"documents": documents}

@component
class TechnicalDocumentSplitter:
    """
    Advanced document splitter designed for technical documentation.
    Preserves context by keeping titles with their content and handling code blocks specially.
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 50,
        preserve_code_blocks: bool = True,
        preserve_lists: bool = True,
        title_context_window: int = 3
    ):
        """
        Initialize the technical document splitter.
        
        Args:
            chunk_size: Target size for each chunk (in characters)
            chunk_overlap: Number of characters to overlap between chunks
            min_chunk_size: Minimum chunk size to avoid very small fragments
            preserve_code_blocks: Keep code blocks intact when possible
            preserve_lists: Keep numbered/bulleted lists together
            title_context_window: Number of sections to include after a title
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.preserve_code_blocks = preserve_code_blocks
        self.preserve_lists = preserve_lists
        self.title_context_window = title_context_window

    def to_dict(self):
        return default_to_dict(
            self,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            min_chunk_size=self.min_chunk_size,
            preserve_code_blocks=self.preserve_code_blocks,
            preserve_lists=self.preserve_lists,
            title_context_window=self.title_context_window
        )

    @classmethod
    def from_dict(cls, data):
        return default_from_dict(cls, data)

    @component.output_types(documents=List[Document])
    def run(self, documents: List[Document]) -> Dict[str, List[Document]]:
        """Split documents using technical documentation-aware logic."""
        split_documents = []
        
        for doc in documents:
            split_docs = self._split_document(doc)
            split_documents.extend(split_docs)
        
        return {"documents": split_documents}

    def _split_document(self, document: Document) -> List[Document]:
        """Split a single document into multiple chunks."""
        content = document.content
        
        # First, identify and extract special blocks (code, lists)
        special_blocks = self._extract_special_blocks(content)
        
        # Split content by sections (headers)
        sections = self._split_by_headers(content)
        
        # Process each section
        chunks = []
        for section in sections:
            section_chunks = self._process_section(section, special_blocks)
            chunks.extend(section_chunks)
        
        # Create Document objects for each chunk
        result_documents = []
        for i, chunk_content in enumerate(chunks):
            if len(chunk_content.strip()) < self.min_chunk_size:
                continue
                
            # Create new document with chunk content
            chunk_doc = Document(
                content=chunk_content,
                meta={
                    **document.meta,
                    "chunk_id": i,
                    "total_chunks": len(chunks),
                    "chunk_type": self._determine_chunk_type(chunk_content)
                }
            )
            result_documents.append(chunk_doc)
        
        return result_documents

    def _extract_special_blocks(self, content: str) -> Dict[str, List[Dict]]:
        """Extract code blocks and other special content that should be preserved."""
        special_blocks = {
            "code_blocks": [],
            "lists": [],
            "tables": []
        }
        
        if self.preserve_code_blocks:
            # Find code blocks (```...``` or indented blocks)
            code_pattern = r'```[\s\S]*?```'
            for match in re.finditer(code_pattern, content):
                special_blocks["code_blocks"].append({
                    "content": match.group(),
                    "start": match.start(),
                    "end": match.end()
                })
        
        if self.preserve_lists:
            # Find structured lists (numbered or bulleted)
            list_pattern = r'(\n(?:\s*(?:\d+\.|[-*+])\s+.+(?:\n\s*.+)*)+)'
            for match in re.finditer(list_pattern, content):
                special_blocks["lists"].append({
                    "content": match.group(),
                    "start": match.start(),
                    "end": match.end()
                })
        
        return special_blocks

    def _split_by_headers(self, content: str) -> List[Dict]:
        """Split content by markdown headers while preserving hierarchy."""
        sections = []
        
        # Pattern to match markdown headers
        header_pattern = r'^(#{1,6})\s+(.+)$'
        lines = content.split('\n')
        
        current_section = {
            "title": "",
            "level": 0,
            "content": "",
            "start_line": 0
        }
        
        for i, line in enumerate(lines):
            header_match = re.match(header_pattern, line)
            
            if header_match:
                # Save previous section if it has content
                if current_section["content"].strip():
                    sections.append(current_section.copy())
                
                # Start new section
                level = len(header_match.group(1))
                title = header_match.group(2)
                
                current_section = {
                    "title": title,
                    "level": level,
                    "content": line + '\n',
                    "start_line": i
                }
            else:
                current_section["content"] += line + '\n'
        
        # Don't forget the last section
        if current_section["content"].strip():
            sections.append(current_section)
        
        # If no headers found, treat entire content as one section
        if not sections:
            sections = [{
                "title": "Document Content",
                "level": 1,
                "content": content,
                "start_line": 0
            }]
        
        return sections

    def _process_section(self, section: Dict, special_blocks: Dict) -> List[str]:
        """Process a section and split it appropriately."""
        content = section["content"]
        title = section["title"]
        
        # If section is small enough, keep it as one chunk
        if len(content) <= self.chunk_size:
            return [content]
        
        chunks = []
        
        # For large sections, split more intelligently
        paragraphs = self._split_into_paragraphs(content)
        
        current_chunk = ""
        title_included = False
        
        for para in paragraphs:
            # Always include the title in the first chunk of a section
            if not title_included and title:
                title_header = f"# {title}\n\n" if not para.startswith('#') else ""
                test_chunk = title_header + para
                title_included = True
            else:
                test_chunk = current_chunk + "\n\n" + para if current_chunk else para
            
            # Check if adding this paragraph exceeds chunk size
            if len(test_chunk) > self.chunk_size and current_chunk:
                # Save current chunk with overlap
                chunks.append(current_chunk)
                
                # Start new chunk with overlap from previous
                overlap_text = self._get_overlap_text(current_chunk)
                current_chunk = overlap_text + para
            else:
                current_chunk = test_chunk
        
        # Add the final chunk
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks

    def _split_into_paragraphs(self, content: str) -> List[str]:
        """Split content into logical paragraphs while preserving structure."""
        # Split by double newlines first
        parts = re.split(r'\n\s*\n', content)
        
        paragraphs = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            # Check if this part contains a code block or list that should be preserved
            if self._contains_special_content(part):
                paragraphs.append(part)
            else:
                # For regular text, we can split further if needed
                if len(part) > self.chunk_size * 0.8:  # 80% of chunk size
                    # Split by sentences for very long paragraphs
                    sentences = re.split(r'(?<=[.!?])\s+', part)
                    current_para = ""
                    
                    for sentence in sentences:
                        test_para = current_para + " " + sentence if current_para else sentence
                        if len(test_para) > self.chunk_size * 0.6:  # 60% of chunk size
                            if current_para:
                                paragraphs.append(current_para)
                                current_para = sentence
                            else:
                                paragraphs.append(sentence)
                        else:
                            current_para = test_para
                    
                    if current_para:
                        paragraphs.append(current_para)
                else:
                    paragraphs.append(part)
        
        return paragraphs

    def _contains_special_content(self, text: str) -> bool:
        """Check if text contains code blocks, lists, or other special content."""
        # Check for code blocks
        if '```' in text or re.search(r'\n    \w', text):  # Indented code
            return True
        
        # Check for lists
        if re.search(r'^\s*(\d+\.|[-*+])\s+', text, re.MULTILINE):
            return True
        
        # Check for tables
        if '|' in text and re.search(r'\|.*\|', text):
            return True
        
        return False

    def _get_overlap_text(self, chunk: str) -> str:
        """Get overlap text from the end of a chunk."""
        if len(chunk) <= self.chunk_overlap:
            return chunk
        
        # Try to find a good breaking point for overlap
        overlap_text = chunk[-self.chunk_overlap:]
        
        # Try to break at sentence boundary
        sentence_break = overlap_text.rfind('.')
        if sentence_break > self.chunk_overlap * 0.5:  # At least half the overlap
            overlap_text = overlap_text[sentence_break + 1:].strip()
        
        return overlap_text

    def _determine_chunk_type(self, content: str) -> str:
        """Determine the type of content in a chunk for better retrieval."""
        content_lower = content.lower()
        
        if '```' in content or re.search(r'\n    \w', content):
            return "code"
        elif any(word in content_lower for word in ['install', 'setup', 'configure', 'step']):
            return "instructions"
        elif re.search(r'^\s*(\d+\.|[-*+])\s+', content, re.MULTILINE):
            return "list"
        elif any(word in content_lower for word in ['error', 'troubleshoot', 'problem', 'issue']):
            return "troubleshooting"
        elif content.count('#') > 0:  # Has headers
            return "section"
        else:
            return "content"


class NexediDocIndexerHaystack:
    def __init__(self, source_dir, db_path, collection_name, log_file_dir=None, debug_cleaner=False):
        self.source_dir = source_dir
        self.db_path = db_path
        self.collection_name = collection_name
        self.log_file_dir = log_file_dir if log_file_dir else self.source_dir
        self.debug_cleaner = debug_cleaner
        os.makedirs(self.log_file_dir, exist_ok=True)
        self.document_store = ChromaDocumentStore(
            persist_path=self.db_path,
            collection_name=self.collection_name
        )

        # Note: Ensure the Ollama URL is correct (extra spaces removed here)
        # IMPORTANT: The URL seems to have trailing spaces in the original. Please verify the correct URL.
        self.doc_embedder = OllamaDocumentEmbedder(
            url="http://localhost",  # Ensure this URL is correct
            model="bge-m3"
            # model="hf.co/Qwen/Qwen3-Embedding-4B-GGUF:Q4_K_M"
        )

    def build_indexing_pipeline(self):
        # Initialize components
        cleaner = DocumentCleaner(
            remove_empty_lines=True,
            remove_extra_whitespaces=True,
            remove_repeated_substrings=False,
            remove_substrings=None,
            remove_regex=None,
            keep_id=False
        )
        debug_cleaner_printer = DebugPrinter(name="After DocumentCleaner")
        
        # Use the new technical document splitter instead of the basic one
        splitter = TechnicalDocumentSplitter(
            chunk_size=1200,  # Larger chunks for technical content
            chunk_overlap=300,  # More overlap to preserve context
            min_chunk_size=100,  # Minimum viable chunk size
            preserve_code_blocks=True,
            preserve_lists=True,
            title_context_window=3
        )
        
        writer = DocumentWriter(self.document_store, policy=DuplicatePolicy.SKIP) # Consider OVERWRITE if file_hash check is sufficient

        # Create the pipeline
        pipeline = Pipeline()

        # Add components to the pipeline
        pipeline.add_component('cleaner', cleaner)
        if self.debug_cleaner:
            pipeline.add_component('debug_cleaner_printer', debug_cleaner_printer)
        pipeline.add_component("splitter", splitter)
        pipeline.add_component("embedder", self.doc_embedder)
        pipeline.add_component("writer", writer)

        # Connect components in the pipeline
        if self.debug_cleaner:
            # cleaner -> debug_cleaner_printer -> splitter
            pipeline.connect('cleaner.documents', 'debug_cleaner_printer.documents')
            pipeline.connect('debug_cleaner_printer.documents', 'splitter.documents')
        else:
            # cleaner -> splitter
            pipeline.connect('cleaner.documents', 'splitter.documents')
        pipeline.connect("splitter.documents", "embedder.documents")
        pipeline.connect("embedder.documents", "writer.documents")

        # When you connect components in a pipeline, calling Pipeline.run() invokes the run() method for each component sequentially
        return pipeline

    def parse_html_content(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        # Attempt to find the base URL
        url = ''
        base_tag = soup.find('base')
        if base_tag and base_tag.get('href'):
            url = base_tag['href']
        # Remove unwanted tags
        for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
            script.decompose()
        # Convert to Markdown, stripping images and scripts
        markdown_content = md(str(soup), strip=["img", "script", "style", "footer", "nav"])
        return markdown_content, url

    def _save_indexed_files_list(self, indexed_files: list, run_type: str = "indexing"):
        """Saves the list of indexed files to a text file."""
        if not indexed_files:
            print("No files to save to the list.")
            return

        list_file_path = os.path.join(self.log_file_dir, f"{run_type}_files_list.txt")
        try:
            with open(list_file_path, 'w', encoding='utf-8') as f:
                for filename in indexed_files:
                    f.write(f"{filename}\n")
            print(f"\nList of {run_type} files saved to: {list_file_path}")
        except Exception as e:
            print(f"Warning: Could not save the list of {run_type} files to {list_file_path}: {e}")

    def load_and_index_docs(self):
        html_files = [f for f in os.listdir(self.source_dir) if f.endswith('.html')]
        new_documents_to_index = []
        indexing_pipeline = self.build_indexing_pipeline() # Get the built pipeline
        indexed_files = [] # List to track newly indexed files

        print(f"Found {len(html_files)} HTML files in {self.source_dir}.")

        for file_name in html_files:
            file_path = os.path.join(self.source_dir, file_name)
            file_hash = calculate_file_hash(file_path)

            # --- Check for duplicates using file_hash ---
            # Use filter_documents to check if a document with this hash already exists
            try:
                # Ensure correct filter format for Chroma/Haystack
                existing_docs = self.document_store.filter_documents(
                    {
                        "field": "meta.file_hash",
                        "operator": "==",
                        "value": file_hash,
                    },
                )
                if existing_docs:
                    print(f"Skipping {file_name} (hash {file_hash[:8]}...): Already exists in the index.")
                    continue # Skip to the next file
            except Exception as e: # Catch potential filter errors
                print(f"Warning: Could not check for duplicates for {file_name} due to filter error: {e}")
                raise
                # Optionally, you could choose to skip or proceed here
                # For now, we'll proceed assuming it's new
            # --- End of duplicate check ---

            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            markdown_content, url = self.parse_html_content(html_content)
            doc_name = os.path.splitext(file_name)[0]

            # Add file_hash (and other metadata) to the document
            new_documents_to_index.append(Document(
                content=markdown_content,
                meta={"doc_name": doc_name, "url": url, "source": file_path, "file_hash": file_hash}
            ))
            print(f"Prepared {file_name} for indexing.")
            indexed_files.append(file_name) # Track this file for reporting

        if not new_documents_to_index:
            print("No new documents to index.")
            # Reporting indexed files list is not needed here as it should be empty
            print("\nNo new files were added to the index.") # Adjusted message
            return

        # Process in batches
        batch_size = 20
        total_batches = (len(new_documents_to_index) + batch_size - 1) // batch_size
        for i in range(0, len(new_documents_to_index), batch_size):
            batch = new_documents_to_index[i:i + batch_size]
            batch_num = i // batch_size + 1
            print(f"Indexing batch {batch_num}/{total_batches} ({len(batch)} documents)...")

            # Run the entire pipeline for this batch
            # Pass the batch to the first component ('cleaner') of the pipeline
            indexing_pipeline.run({"cleaner": {"documents": batch}})

            print(f"Batch {batch_num} indexed.")

        print(f"Successfully processed {len(new_documents_to_index)} new documents.")
        # --- Print the list of added files ---
        if indexed_files:
            print("\nFiles newly added to the index in this run:")
            for fname in indexed_files:
                print(f"  - {fname}")
        else:
            print("\nNo new files were added to the index.")

        self._save_indexed_files_list(indexed_files, run_type="indexing")

    def verify_indexing(self):
        count = self.document_store.count_documents()
        print(f"\nVerification: Found {count} documents in the '{self.collection_name}' collection.")
        file_name = "ors_rapidspace-HowTo.ORS.Shipping.Process.html"
        doc_name = os.path.splitext(file_name)[0]
        print(doc_name)
        if count > 0:
            print("Sample document:")
            # Get one document, e.g., the first one
            sample_docs = self.document_store.filter_documents(
                {
                    "field": "meta.doc_name",
                    "operator": "==",
                    "value": doc_name,
                },
            )
            if sample_docs:
                original_document = sample_docs[0]
                print(len(sample_docs))
                test_cleaner = DocumentCleaner(remove_empty_lines=True, remove_extra_whitespaces=True)
                cleaned_test_docs = test_cleaner.run([original_document])
                print(f"--- Manually Cleaned Content for {file_name} ---")
                print(cleaned_test_docs['documents'][0].content)
                print("--- End Manually Cleaned Content ---")
                print(sample_docs[0])
                print("*****************************")
                print(sample_docs[0].content)

    def analyze_chunks(self):
        """Analyze how documents were chunked - useful for debugging the new splitter"""
        docs = self.document_store.filter_documents({})
        
        chunk_types = {}
        chunk_sizes = []
        for doc in docs:
            chunk_type = doc.meta.get('chunk_type', 'unknown')
            chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
            chunk_sizes.append(len(doc.content))
        
        print("\n=== Chunk Analysis ===")
        print("Chunk type distribution:", chunk_types)
        print(f"Average chunk size: {sum(chunk_sizes)/len(chunk_sizes):.0f} characters")
        print(f"Min chunk size: {min(chunk_sizes)} characters")
        print(f"Max chunk size: {max(chunk_sizes)} characters")
        
        # Show sample chunks for manual review
        for chunk_type in ['instructions', 'code', 'troubleshooting', 'section']:
            type_docs = [d for d in docs if d.meta.get('chunk_type') == chunk_type]
            if type_docs:
                print(f"\n--- Sample {chunk_type} chunk ---")
                sample_content = type_docs[0].content
                print(sample_content[:400] + ("..." if len(sample_content) > 400 else ""))
                print(f"Chunk size: {len(sample_content)} characters")

def main():
    log_dir = "./indexing_logs_v3"
    indexer = NexediDocIndexerHaystack(
        source_dir="./handbook_rapid_space",
        db_path="./nexedi_doc_vec_haystack_v3",
        collection_name="nexedi_doc_haystack_v3",
        log_file_dir=log_dir,
        debug_cleaner=False
    )
    indexer.load_and_index_docs()
    indexer.verify_indexing()
    indexer.analyze_chunks()  # New method to analyze chunking results

if __name__ == "__main__":
    main()
