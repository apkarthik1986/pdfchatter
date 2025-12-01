"""
Flask server for PDF Question Answering.

This server extracts text from PDF files in the backend/pdfs/ directory,
receives questions via HTTP POST requests, and returns matching content.
"""

import os
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


def load_all_pdfs(force_reload=False):
    """Load and extract text from all PDFs in the pdfs directory.
    
    Uses caching to avoid reloading PDFs on every request.
    Set force_reload=True to reload PDFs from disk.
    """
    global _pdf_cache, _pdf_cache_loaded
    
    if _pdf_cache_loaded and not force_reload:
        return _pdf_cache
    
    all_text = {}
    
    if not os.path.exists(PDF_DIRECTORY):
        os.makedirs(PDF_DIRECTORY)
        _pdf_cache = all_text
        _pdf_cache_loaded = True
        return all_text
    
    for filename in os.listdir(PDF_DIRECTORY):
        if filename.lower().endswith('.pdf'):
            pdf_path = os.path.join(PDF_DIRECTORY, filename)
            all_text[filename] = extract_text_from_pdf(pdf_path)
    
    _pdf_cache = all_text
    _pdf_cache_loaded = True
    return all_text


def extract_keywords(text):
    """Extract meaningful keywords from text, filtering stop words and punctuation."""
    import re
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
                results.append({
                    'filename': filename,
                    'content': '. '.join(matching_sentences[:3]) + '.',
                    'match_score': len(matching_keywords) / len(keywords) if keywords else 0
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
                'success': True,
                'answer': 'No PDF files found in the pdfs directory. Please add PDF files to backend/pdfs/ and try again.',
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


if __name__ == '__main__':
    print("Starting PDF QA Server...")
    print(f"PDF directory: {PDF_DIRECTORY}")
    print(f"PDF support available: {PDF_SUPPORT}")
    
    if not PDF_SUPPORT:
        print("Warning: PyPDF2 not installed. Install it with: pip install PyPDF2")
    
    # Pre-load PDFs at startup
    loaded_pdfs = load_all_pdfs()
    print(f"Loaded {len(loaded_pdfs)} PDF file(s) at startup")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
