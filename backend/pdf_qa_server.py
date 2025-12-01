"""
Flask server for PDF Question Answering with Semantic Search.

This server extracts text from PDF files, creates vector embeddings using
sentence-transformers for semantic search, and returns the most relevant
passages based on user questions.
"""

import os
import re
from flask import Flask, request, jsonify
from flask_cors import CORS

# Try to import PyPDF2 for PDF text extraction
try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# Try to import sentence-transformers for semantic search
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    SEMANTIC_SEARCH_SUPPORT = True
except ImportError:
    SEMANTIC_SEARCH_SUPPORT = False

app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests from the C# frontend

# Directory containing PDF files
PDF_DIRECTORY = os.path.join(os.path.dirname(__file__), 'pdfs')

# Sentence transformer model (loaded lazily)
_sentence_model = None

# Cache for loaded PDF texts and embeddings
_pdf_cache = {}
_pdf_cache_loaded = False
_pdf_folder_path = None  # Currently loaded folder path
_passage_embeddings = None  # Numpy array of passage embeddings
_passage_metadata = []  # List of (filename, passage_text) tuples


def extract_text_from_pdf(pdf_path):
    """Extract text content from a PDF file."""
    if not PDF_SUPPORT:
        return ""
    
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
    return text


def get_sentence_model():
    """Load the sentence transformer model (lazy loading)."""
    global _sentence_model
    if _sentence_model is None and SEMANTIC_SEARCH_SUPPORT:
        try:
            print("Loading sentence transformer model...")
            # Use a lightweight model for fast local inference
            _sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
            print("Sentence transformer model loaded.")
        except Exception as e:
            print(f"Warning: Could not load sentence transformer model: {e}")
            print("Semantic search will not be available until the model is downloaded.")
            _sentence_model = None
    return _sentence_model


def split_into_passages(text, max_length=500):
    """Split text into passages of approximately max_length characters.
    
    Tries to split at sentence boundaries for better context.
    """
    # Split by sentences (period followed by space or newline)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    passages = []
    current_passage = ""
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        # If adding this sentence would exceed max_length, start new passage
        if len(current_passage) + len(sentence) > max_length and current_passage:
            passages.append(current_passage.strip())
            current_passage = sentence
        else:
            current_passage += " " + sentence if current_passage else sentence
    
    # Don't forget the last passage
    if current_passage.strip():
        passages.append(current_passage.strip())
    
    return passages


def build_passage_index(pdf_texts):
    """Build a semantic index of all passages from PDFs.
    
    Creates embeddings for each passage and stores metadata.
    """
    global _passage_embeddings, _passage_metadata
    
    model = get_sentence_model()
    if model is None:
        _passage_embeddings = None
        _passage_metadata = []
        return
    
    all_passages = []
    _passage_metadata = []
    
    for filename, text in pdf_texts.items():
        if not text:
            continue
        passages = split_into_passages(text)
        for passage in passages:
            if len(passage) > 20:  # Skip very short passages
                all_passages.append(passage)
                _passage_metadata.append((filename, passage))
    
    if all_passages:
        print(f"Creating embeddings for {len(all_passages)} passages...")
        _passage_embeddings = model.encode(all_passages, convert_to_numpy=True)
        print(f"Embeddings created with shape: {_passage_embeddings.shape}")
    else:
        _passage_embeddings = None
        _passage_metadata = []


def load_all_pdfs(force_reload=False, folder_path=None):
    """Load and extract text from all PDFs in the specified directory.
    
    Uses caching to avoid reloading PDFs on every request.
    Set force_reload=True to reload PDFs from disk.
    If folder_path is provided, loads from that folder instead of the default.
    Also builds the semantic search index when loading.
    """
    global _pdf_cache, _pdf_cache_loaded, _pdf_folder_path
    
    # Determine which directory to load from
    target_directory = folder_path if folder_path else PDF_DIRECTORY
    
    # If folder changed, force reload
    if folder_path and folder_path != _pdf_folder_path:
        force_reload = True
    
    if _pdf_cache_loaded and not force_reload:
        return _pdf_cache
    
    all_text = {}
    
    if not os.path.exists(target_directory):
        if not folder_path:
            os.makedirs(target_directory)
        _pdf_cache = all_text
        _pdf_cache_loaded = True
        _pdf_folder_path = target_directory
        # Clear the embeddings index
        build_passage_index({})
        return all_text
    
    for filename in os.listdir(target_directory):
        if filename.lower().endswith('.pdf'):
            pdf_path = os.path.join(target_directory, filename)
            all_text[filename] = extract_text_from_pdf(pdf_path)
    
    _pdf_cache = all_text
    _pdf_cache_loaded = True
    _pdf_folder_path = target_directory
    
    # Build the semantic search index
    build_passage_index(all_text)
    
    return all_text


def semantic_search(question, top_k=3):
    """Perform semantic search to find the most relevant passages.
    
    Returns a list of results with filename, content, and confidence score.
    """
    global _passage_embeddings, _passage_metadata
    
    model = get_sentence_model()
    if model is None or _passage_embeddings is None or len(_passage_metadata) == 0:
        return []
    
    # Encode the question
    question_embedding = model.encode([question], convert_to_numpy=True)
    
    # Calculate cosine similarity
    # Normalize embeddings for cosine similarity
    question_norm = question_embedding / np.linalg.norm(question_embedding)
    passage_norms = _passage_embeddings / np.linalg.norm(_passage_embeddings, axis=1, keepdims=True)
    
    similarities = np.dot(passage_norms, question_norm.T).flatten()
    
    # Get top-k results
    top_indices = np.argsort(similarities)[-top_k:][::-1]
    
    results = []
    for idx in top_indices:
        similarity = float(similarities[idx])
        # Only include results with reasonable similarity (above threshold)
        if similarity > 0.2:  # Threshold for relevance
            filename, passage = _passage_metadata[idx]
            results.append({
                'filename': filename,
                'content': passage,
                'confidence': round(similarity * 100, 1)  # Convert to percentage
            })
    
    return results


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'pdf_support': PDF_SUPPORT,
        'semantic_search_support': SEMANTIC_SEARCH_SUPPORT
    })


@app.route('/ask', methods=['POST'])
def ask_question():
    """
    Receive a question and return matching content from PDFs using semantic search.
    
    Expected JSON body:
    {
        "question": "Your question here"
    }
    
    Returns:
    {
        "success": true/false,
        "answer": "Matching content or message",
        "sources": [{"filename": "...", "content": "...", "confidence": 85.2}],
        "top_confidence": 85.2
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'question' not in data:
            return jsonify({
                'success': False,
                'answer': 'Please provide a question.',
                'sources': [],
                'top_confidence': 0
            }), 400
        
        question = data['question'].strip()
        
        if not question:
            return jsonify({
                'success': False,
                'answer': 'Question cannot be empty.',
                'sources': [],
                'top_confidence': 0
            }), 400
        
        # Load PDF texts (uses cached data if already loaded)
        pdf_texts = load_all_pdfs()
        
        if not pdf_texts:
            return jsonify({
                'success': False,
                'answer': 'No PDF files are currently loaded. Please load PDFs from a folder first.',
                'sources': [],
                'top_confidence': 0
            })
        
        # Use semantic search to find matching content
        results = semantic_search(question, top_k=3)
        
        if not results:
            return jsonify({
                'success': True,
                'answer': 'No matching content found for your question. Try rephrasing or asking a different question.',
                'sources': [],
                'top_confidence': 0
            })
        
        # Combine results into an answer
        answer_parts = []
        sources = []
        
        for result in results:
            confidence_str = f"[{result['confidence']}% confidence]"
            answer_parts.append(f"From {result['filename']} {confidence_str}:\n{result['content']}")
            sources.append({
                'filename': result['filename'],
                'content': result['content'],
                'confidence': result['confidence']
            })
        
        top_confidence = results[0]['confidence'] if results else 0
        
        return jsonify({
            'success': True,
            'answer': '\n\n'.join(answer_parts),
            'sources': sources,
            'top_confidence': top_confidence
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'answer': f'An error occurred: {str(e)}',
            'sources': [],
            'top_confidence': 0
        }), 500


@app.route('/pdfs', methods=['GET'])
def list_pdfs():
    """List all PDF files in the pdfs directory."""
    if not os.path.exists(PDF_DIRECTORY):
        return jsonify({'pdfs': []})
    
    pdfs = [f for f in os.listdir(PDF_DIRECTORY) if f.lower().endswith('.pdf')]
    return jsonify({'pdfs': pdfs})


@app.route('/reload', methods=['POST'])
def reload_pdfs():
    """Reload PDFs from disk. Useful when new PDFs are added."""
    pdf_texts = load_all_pdfs(force_reload=True)
    return jsonify({
        'success': True,
        'message': f'Reloaded {len(pdf_texts)} PDF file(s).',
        'pdfs': list(pdf_texts.keys())
    })


@app.route('/load_pdfs', methods=['POST'])
def load_pdfs_from_folder():
    """Load PDFs from a user-specified folder.
    
    Expected JSON body:
    {
        "folder_path": "C:/path/to/pdfs"
    }
    
    Returns:
    {
        "success": true/false,
        "message": "Status message",
        "pdfs": ["file1.pdf", "file2.pdf"]
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'folder_path' not in data:
            return jsonify({
                'success': False,
                'message': 'Please provide a folder_path.',
                'pdfs': []
            }), 400
        
        folder_path = data['folder_path'].strip()
        
        if not folder_path:
            return jsonify({
                'success': False,
                'message': 'Folder path cannot be empty.',
                'pdfs': []
            }), 400
        
        if not os.path.exists(folder_path):
            return jsonify({
                'success': False,
                'message': f'Folder does not exist: {folder_path}',
                'pdfs': []
            }), 400
        
        if not os.path.isdir(folder_path):
            return jsonify({
                'success': False,
                'message': f'Path is not a directory: {folder_path}',
                'pdfs': []
            }), 400
        
        # Load PDFs from the specified folder
        pdf_texts = load_all_pdfs(force_reload=True, folder_path=folder_path)
        
        if not pdf_texts:
            return jsonify({
                'success': False,
                'message': f'No PDF files found in: {folder_path}',
                'pdfs': []
            })
        
        return jsonify({
            'success': True,
            'message': f'Loaded {len(pdf_texts)} PDF file(s) from: {folder_path}',
            'pdfs': list(pdf_texts.keys())
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'An error occurred: {str(e)}',
            'pdfs': []
        }), 500


if __name__ == '__main__':
    print("Starting PDF QA Server with Semantic Search...")
    print(f"PDF directory: {PDF_DIRECTORY}")
    print(f"PDF support available: {PDF_SUPPORT}")
    print(f"Semantic search support available: {SEMANTIC_SEARCH_SUPPORT}")
    
    if not PDF_SUPPORT:
        print("Warning: PyPDF2 not installed. Install it with: pip install PyPDF2")
    
    if not SEMANTIC_SEARCH_SUPPORT:
        print("Warning: sentence-transformers not installed. Install it with: pip install sentence-transformers")
    else:
        # Pre-load the sentence transformer model
        print("Loading sentence transformer model (this may take a moment on first run)...")
        get_sentence_model()
    
    # Pre-load PDFs at startup
    loaded_pdfs = load_all_pdfs()
    print(f"Loaded {len(loaded_pdfs)} PDF file(s) at startup")
    
    # Debug mode is disabled by default for security
    # Set environment variable FLASK_DEBUG=1 to enable debug mode during development
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
