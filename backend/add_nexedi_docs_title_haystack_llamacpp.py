
import os
import sys
from bs4 import BeautifulSoup
from haystack import Pipeline
from haystack.components.writers import DocumentWriter
from haystack_integrations.document_stores.chroma import ChromaDocumentStore
from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder
from haystack.dataclasses import Document
from haystack.document_stores.types import DuplicatePolicy

# Add backend to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def extract_title_from_html(file_path: str) -> tuple:
    """Extracts the title from an HTML file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    soup = BeautifulSoup(html_content, 'html.parser')
    title_tag = soup.find('title')
    title = title_tag.get_text() if title_tag else ''
    base_tag = soup.find('base')
    url = ''
    if base_tag and base_tag.get('href'):
        url = base_tag['href']
    return title, url

class NexediTitleIndexer:
    def __init__(self, source_dir, db_path, collection_name):
        self.source_dir = source_dir
        self.db_path = db_path
        self.collection_name = collection_name
        self.document_store = ChromaDocumentStore(
            persist_path=self.db_path,
            collection_name=self.collection_name
        )
        self.doc_embedder = OllamaDocumentEmbedder(
            url="http://localhost:11434/api/embeddings",
            model="bge-m3"
        )

    def build_indexing_pipeline(self):
        """Builds a simple pipeline for embedding and writing documents."""
        writer = DocumentWriter(self.document_store, policy=DuplicatePolicy.SKIP)
        pipeline = Pipeline()
        pipeline.add_component("embedder", self.doc_embedder)
        pipeline.add_component("writer", writer)
        pipeline.connect("embedder.documents", "writer.documents")
        return pipeline

    def load_and_index_titles(self):
        """Loads HTML files, extracts titles, and indexes them in batches."""
        html_files = [f for f in os.listdir(self.source_dir) if f.endswith('.html')]
        documents_to_index = []
        indexing_pipeline = self.build_indexing_pipeline()

        print(f"Found {len(html_files)} HTML files in {self.source_dir}.")

        for file_name in html_files:
            file_path = os.path.join(self.source_dir, file_name)
            title, url = extract_title_from_html(file_path)
            if title:
                documents_to_index.append(Document(
                    content=title,
                    meta={"url": url}
                ))
                print(f"Extracted title from {file_name}: '{title}'")

        if not documents_to_index:
            print("No titles found to index.")
            return

        # Process in batches
        batch_size = 20
        total_batches = (len(documents_to_index) + batch_size - 1) // batch_size
        for i in range(0, len(documents_to_index), batch_size):
            batch = documents_to_index[i:i + batch_size]
            batch_num = i // batch_size + 1
            print(f"Indexing batch {batch_num}/{total_batches} ({len(batch)} documents)...")
            indexing_pipeline.run({"embedder": {"documents": batch}})
            print(f"Batch {batch_num} indexed.")

        print(f"Successfully processed {len(documents_to_index)} titles.")
        self.verify_indexing()

    def verify_indexing(self):
        """Verifies that documents have been indexed."""
        count = self.document_store.count_documents()
        print(f"\nVerification: Found {count} documents in the '{self.collection_name}' collection.")
        if count > 0:
            print("Sample document:")
            sample_docs = self.document_store.filter_documents()
            if sample_docs:
                print(sample_docs[0])

def main():
    indexer = NexediTitleIndexer(
        source_dir="./handbook_rapid_space",
        db_path="./nexed_doc_title_vec_haystack",
        collection_name="nexedi_doc_titles"
    )
    indexer.load_and_index_titles()

if __name__ == "__main__":
    main()
