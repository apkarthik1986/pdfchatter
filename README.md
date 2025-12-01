# PDF Chatter

A C# GUI frontend with a Python backend for answering questions based on PDF files using AI-powered semantic search.

## Overview

PDF Chatter allows you to ask questions about the content of your PDF files. The system uses **sentence-transformers** to create vector embeddings of your PDF content, enabling semantic search that understands the meaning of your questions—not just keywords.

- **Backend (Python/Flask)**: Extracts text from PDFs, creates semantic embeddings, and finds the most relevant passages based on your questions
- **Frontend (C#/WPF)**: Provides a user-friendly interface with confidence scores for answers

## Features

- 🔍 **Semantic Search**: Uses AI embeddings to understand question meaning, not just keyword matching
- 📊 **Confidence Scores**: Shows how relevant each answer is to your question
- 📁 **Folder Selection**: Choose any folder containing PDF files
- ⚡ **Fast In-Memory Caching**: PDFs and embeddings are cached for quick responses
- 🖥️ **Local Processing**: No API keys or external services required—everything runs locally

## Project Structure

```
pdfchatter/
├── backend/
│   ├── pdf_qa_server.py    # Flask server with semantic search
│   └── pdfs/               # Default PDF directory (optional)
├── frontend/
│   ├── MainWindow.xaml     # WPF UI layout
│   └── MainWindow.xaml.cs  # WPF C# code-behind
└── README.md
```

## Prerequisites

### For the Backend (Python)
- Python 3.8 or higher
- pip (Python package installer)
- ~500MB disk space for the sentence-transformer model (downloaded on first run)

### For the Frontend (C#)
- .NET 8.0 or higher
- Windows OS (WPF application)

## Installation & Setup

### Step 1: Set Up the Python Backend

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Install required Python packages:
   ```bash
   pip install flask flask-cors PyPDF2 sentence-transformers
   ```

3. Start the Flask server:
   ```bash
   python pdf_qa_server.py
   ```

   The server will start on `http://localhost:5000`.
   
   On first run, the sentence-transformer model (~90MB) will be downloaded automatically.

   **Note**: Debug mode is disabled by default for security. To enable debug mode during development, run:
   ```bash
   FLASK_DEBUG=1 python pdf_qa_server.py
   ```

### Step 2: Set Up the C# Frontend

1. Open Visual Studio and open the `frontend/PdfQAGui.csproj` project.

2. Build and run the application.

   Or from command line:
   ```bash
   cd frontend
   dotnet run
   ```

## Usage

1. **Start the backend**: Make sure the Python Flask server is running (`python pdf_qa_server.py`).

2. **Launch the frontend**: Run the C# WPF application.

3. **Select PDF folder**: Click "Select PDF Folder" to choose a directory containing your PDFs. The backend will index all PDFs for semantic search.

4. **Ask questions**: Type your question in the text box and click "Ask". The AI will find the most relevant passages.

5. **View answers**: The answer section shows matching content with confidence scores. Higher confidence (green) indicates better matches.

## API Endpoints

The backend provides the following REST API endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check endpoint (includes semantic search status) |
| `/ask` | POST | Submit a question and get semantically matched answers with confidence |
| `/pdfs` | GET | List all PDF files in the default pdfs directory |
| `/reload` | POST | Reload PDFs from disk and rebuild semantic index |
| `/load_pdfs` | POST | Load PDFs from a user-specified folder path |

### Example API Requests

```bash
# Ask a question (returns answer with confidence score)
curl -X POST http://localhost:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the main topic?"}'

# Response includes confidence scores:
# {
#   "success": true,
#   "answer": "From document.pdf [85.2% confidence]:\nThe main topic is...",
#   "sources": [{"filename": "document.pdf", "content": "...", "confidence": 85.2}],
#   "top_confidence": 85.2
# }

# Load PDFs from a specific folder
curl -X POST http://localhost:5000/load_pdfs \
  -H "Content-Type: application/json" \
  -d '{"folder_path": "C:/Users/Documents/MyPDFs"}'
```

## How Semantic Search Works

1. **Indexing**: When you load PDFs, the backend:
   - Extracts text from each PDF
   - Splits text into passages (~500 characters each)
   - Creates vector embeddings using the `all-MiniLM-L6-v2` model

2. **Searching**: When you ask a question:
   - Your question is converted to a vector embedding
   - Cosine similarity finds the most relevant passages
   - Results are returned with confidence scores (0-100%)

## Troubleshooting

### Backend Issues

- **sentence-transformers not installed**: Run `pip install sentence-transformers`
- **PyPDF2 not installed**: Run `pip install PyPDF2`
- **Port 5000 in use**: Modify the port in `pdf_qa_server.py`
- **Model download fails**: Ensure internet connectivity on first run
- **Slow first query**: The model loads on first use; subsequent queries are fast

### Frontend Issues

- **Cannot connect to backend**: Ensure the Flask server is running on port 5000
- **Connection timeout**: Check firewall settings
- **"Load PDFs first"**: Select a PDF folder before asking questions

## License

This project is open source and available under the MIT License.