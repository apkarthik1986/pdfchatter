"""
Flask server for PDF Question Answering.

This server extracts text from PDF files in the backend/pdfs/ directory,
receives questions via HTTP POST requests, and returns matching content.
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

app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests from the C# frontend

# Directory containing PDF files
PDF_DIRECTORY = os.path.join(os.path.dirname(__file__), 'pdfs')

# Common stop words to filter out for better keyword matching
STOP_WORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
    'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
    'it', 'its', 'this', 'that', 'these', 'those', 'i', 'you', 'he',
    'she', 'we', 'they', 'what', 'which', 'who', 'whom', 'how', 'when',
    'where', 'why', 'if', 'then', 'so', 'than', 'too', 'very', 'just',
    'about', 'into', 'through', 'during', 'before', 'after', 'above',
    'below', 'between', 'under', 'again', 'further', 'once', 'here',
    'there', 'all', 'each', 'few', 'more', 'most', 'other', 'some',
    'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'any', 'both'
}

# Cache for loaded PDF texts
_pdf_cache = {}
_pdf_cache_loaded = False
_pdf_folder_path = None  # Currently loaded folder path


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


def load_all_pdfs(force_reload=False, folder_path=None):
    """Load and extract text from all PDFs in the specified directory.
    
    Uses caching to avoid reloading PDFs on every request.
    Set force_reload=True to reload PDFs from disk.
    If folder_path is provided, loads from that folder instead of the default.
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
        return all_text
    
    for filename in os.listdir(target_directory):
        if filename.lower().endswith('.pdf'):
            pdf_path = os.path.join(target_directory, filename)
            all_text[filename] = extract_text_from_pdf(pdf_path)
    
    _pdf_cache = all_text
    _pdf_cache_loaded = True
    _pdf_folder_path = target_directory
    return all_text


def extract_keywords(text):
    """Extract meaningful keywords from text, filtering stop words and punctuation."""
    # Remove punctuation and convert to lowercase
    words = re.findall(r'\b[a-z]+\b', text.lower())
    # Filter out stop words and short words
    keywords = [w for w in words if w not in STOP_WORDS and len(w) > 2]
    return keywords


def find_matching_content(question, pdf_texts):
    """
    Find content in PDFs that matches the question.
    
    This is a basic keyword matching implementation with stop word filtering.
    NLP/AI-powered reasoning can be added later for better results.
    """
    keywords = extract_keywords(question)
    
    # Fall back to simple split if no keywords after filtering
    if not keywords:
        keywords = [w.lower() for w in question.split() if len(w) > 2]
    
    # Return empty results if still no keywords
    if not keywords:
        return []
    
    results = []
    
    for filename, text in pdf_texts.items():
        if not text:
            continue
            
        text_lower = text.lower()
        
        # Check if any keywords are in the text
        matching_keywords = [kw for kw in keywords if kw in text_lower]
        
        if matching_keywords:
            # Find sentences containing matching keywords
            sentences = text.replace('\n', ' ').split('.')
            matching_sentences = []
            
            for sentence in sentences:
                sentence_lower = sentence.lower()
                if any(kw in sentence_lower for kw in matching_keywords):
                    matching_sentences.append(sentence.strip())
            
            if matching_sentences:
                # Return up to 3 most relevant sentences
                joined_content = '. '.join(matching_sentences[:3])
                # Add period only if content doesn't already end with punctuation
                if joined_content and not joined_content[-1] in '.!?':
                    joined_content += '.'
                results.append({
                    'filename': filename,
                    'content': joined_content,
                    'match_score': len(matching_keywords) / len(keywords)
                })
    
    # Sort by match score descending
    results.sort(key=lambda x: x['match_score'], reverse=True)
    
    return results


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'pdf_support': PDF_SUPPORT
    })


@app.route('/ask', methods=['POST'])
def ask_question():
    """
    Receive a question and return matching content from PDFs.
    
    Expected JSON body:
    {
        "question": "Your question here"
    }
    
    Returns:
    {
        "success": true/false,
        "answer": "Matching content or message",
        "sources": [{"filename": "...", "content": "..."}]
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'question' not in data:
            return jsonify({
                'success': False,
                'answer': 'Please provide a question.',
                'sources': []
            }), 400
        
        question = data['question'].strip()
        
        if not question:
            return jsonify({
                'success': False,
                'answer': 'Question cannot be empty.',
                'sources': []
            }), 400
        
        # Load PDF texts
        pdf_texts = load_all_pdfs()
        
        if not pdf_texts:
            return jsonify({
                'success': False,
                'answer': 'No PDF files loaded. Please select a PDF folder first using the "Select PDF Folder" button.',
                'sources': []
            })
        
        # Find matching content
        results = find_matching_content(question, pdf_texts)
        
        if not results:
            return jsonify({
                'success': True,
                'answer': 'No matching content found for your question. Try rephrasing or asking a different question.',
                'sources': []
            })
        
        # Combine results into an answer
        answer_parts = []
        sources = []
        
        for result in results[:3]:  # Limit to top 3 results
            answer_parts.append(f"From {result['filename']}: {result['content']}")
            sources.append({
                'filename': result['filename'],
                'content': result['content']
            })
        
        return jsonify({
            'success': True,
            'answer': '\n\n'.join(answer_parts),
            'sources': sources
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'answer': f'An error occurred: {str(e)}',
            'sources': []
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
                'success': True,
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
    print("Starting PDF QA Server...")
    print(f"PDF directory: {PDF_DIRECTORY}")
    print(f"PDF support available: {PDF_SUPPORT}")
    
    if not PDF_SUPPORT:
        print("Warning: PyPDF2 not installed. Install it with: pip install PyPDF2")
    
    # Pre-load PDFs at startup
    loaded_pdfs = load_all_pdfs()
    print(f"Loaded {len(loaded_pdfs)} PDF file(s) at startup")
    
    # Debug mode is disabled by default for security
    # Set environment variable FLASK_DEBUG=1 to enable debug mode during development
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
