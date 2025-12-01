# PDF Chatter

A C# GUI frontend with a Python backend for answering questions based on PDF files.

## Overview

PDF Chatter allows you to ask questions about the content of your PDF files. The system consists of:

- **Backend (Python/Flask)**: Extracts text from PDFs and finds matching content based on your questions
- **Frontend (C#/WPF)**: Provides a user-friendly interface to interact with the backend

## Project Structure

```
pdfchatter/
├── backend/
│   ├── pdf_qa_server.py    # Flask server for PDF processing
│   └── pdfs/               # Place your PDF files here
├── frontend/
│   ├── MainWindow.xaml     # WPF UI layout
│   └── MainWindow.xaml.cs  # WPF C# code-behind
└── README.md
```

## Prerequisites

### For the Backend (Python)
- Python 3.7 or higher
- pip (Python package installer)

### For the Frontend (C#)
- .NET Framework 4.7.2 or higher (or .NET 6+)
- Visual Studio 2019 or higher (recommended)

## Installation & Setup

### Step 1: Set Up the Python Backend

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Install required Python packages:
   ```bash
   pip install flask flask-cors PyPDF2
   ```

3. Add your PDF files to the `backend/pdfs/` directory.

4. Start the Flask server:
   ```bash
   python pdf_qa_server.py
   ```

   The server will start on `http://localhost:5000`.

   **Note**: Debug mode is disabled by default for security. To enable debug mode during development, run:
   ```bash
   FLASK_DEBUG=1 python pdf_qa_server.py
   ```

### Step 2: Set Up the C# Frontend

1. Open Visual Studio and create a new WPF Application project.

2. Copy the content from `frontend/MainWindow.xaml` to your project's `MainWindow.xaml`.

3. Copy the content from `frontend/MainWindow.xaml.cs` to your project's `MainWindow.xaml.cs`.

4. Make sure the namespace in the code matches your project's namespace.

5. Build and run the application.

## Usage

1. **Start the backend**: Make sure the Python Flask server is running (`python pdf_qa_server.py`).

2. **Launch the frontend**: Run the C# WPF application.

3. **Ask questions**: Type your question in the text box and click "Ask".

4. **View answers**: The answer will appear in the answer section, showing relevant content from your PDFs.

## API Endpoints

The backend provides the following REST API endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check endpoint |
| `/ask` | POST | Submit a question and get an answer |
| `/pdfs` | GET | List all PDF files in the pdfs directory |
| `/reload` | POST | Reload PDFs from disk (useful after adding new PDFs) |

### Example API Request

```bash
curl -X POST http://localhost:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the main topic?"}'
```

## Future Enhancements

This is a minimal foundation for further feature additions:

- **NLP/AI-powered reasoning**: Integrate language models for better question understanding
- **Semantic search**: Use embeddings for more accurate content matching
- **Multi-document support**: Better handling of multiple PDF sources
- **Chat history**: Remember previous questions and answers
- **PDF upload**: Allow uploading PDFs through the GUI

## Troubleshooting

### Backend Issues

- **PyPDF2 not installed**: Run `pip install PyPDF2`
- **Port 5000 in use**: Modify the port in `pdf_qa_server.py`
- **No PDF files found**: Add PDF files to `backend/pdfs/`

### Frontend Issues

- **Cannot connect to backend**: Ensure the Flask server is running on port 5000
- **Connection timeout**: Check firewall settings

## License

This project is open source and available under the MIT License.