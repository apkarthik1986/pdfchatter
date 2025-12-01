using System;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Media;
using Microsoft.Win32;

namespace PdfChatter
{
    /// <summary>
    /// Interaction logic for MainWindow.xaml
    /// This WPF application connects to a Python Flask backend
    /// that uses semantic search to answer questions based on PDF content.
    /// </summary>
    public partial class MainWindow : Window
    {
        private readonly HttpClient _httpClient;
        private const string BackendUrl = "http://127.0.0.1:5000";
        private const string PlaceholderText = "Enter your question here...";
        private const string DisabledPlaceholderText = "Load PDFs first to ask questions...";
        
        // Confidence thresholds for color coding (percentage)
        private const double HighConfidenceThreshold = 70.0;
        private const double MediumConfidenceThreshold = 40.0;
        
        private bool _pdfsLoaded = false;

        public MainWindow()
        {
            InitializeComponent();
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(60); // Increased timeout for semantic search
        }

        /// <summary>
        /// Handle the Select Folder button click event.
        /// Opens a folder dialog and sends the selected folder to the backend.
        /// </summary>
        private async void SelectFolderButton_Click(object sender, RoutedEventArgs e)
        {
            // Use OpenFolderDialog for folder selection (available in .NET 8)
            var dialog = new OpenFolderDialog
            {
                Title = "Select PDF Folder",
                Multiselect = false
            };

            if (dialog.ShowDialog() == true)
            {
                string folderPath = dialog.FolderName;
                await LoadPdfsFromFolderAsync(folderPath);
            }
        }

        /// <summary>
        /// Send the folder path to the backend and load PDFs.
        /// Creates semantic embeddings for all PDF content.
        /// </summary>
        private async Task LoadPdfsFromFolderAsync(string folderPath)
        {
            // Disable UI while loading
            SelectFolderButton.IsEnabled = false;
            AskButton.IsEnabled = false;
            QuestionTextBox.IsEnabled = false;
            StatusText.Text = "Loading PDFs and creating semantic index...";
            FolderPathTextBox.Text = folderPath;
            PdfCountText.Text = "";
            ConfidenceText.Text = "";
            AnswerTextBox.Text = "Loading PDFs and building semantic search index...\nThis may take a moment for large documents.";

            try
            {
                var requestBody = new { folder_path = folderPath };
                string jsonContent = JsonSerializer.Serialize(requestBody);
                var content = new StringContent(jsonContent, Encoding.UTF8, "application/json");

                HttpResponseMessage response = await _httpClient.PostAsync(
                    $"{BackendUrl}/load_pdfs", content);

                string responseBody = await response.Content.ReadAsStringAsync();

                using JsonDocument doc = JsonDocument.Parse(responseBody);
                JsonElement root = doc.RootElement;

                bool success = root.TryGetProperty("success", out JsonElement successElement) && 
                               successElement.GetBoolean();
                string message = root.TryGetProperty("message", out JsonElement messageElement) 
                    ? messageElement.GetString() ?? "" : "";
                
                int pdfCount = 0;
                if (root.TryGetProperty("pdfs", out JsonElement pdfsElement) && 
                    pdfsElement.ValueKind == JsonValueKind.Array)
                {
                    pdfCount = pdfsElement.GetArrayLength();
                }

                if (success && pdfCount > 0)
                {
                    _pdfsLoaded = true;
                    QuestionTextBox.IsEnabled = true;
                    AskButton.IsEnabled = true;
                    QuestionTextBox.Text = PlaceholderText;
                    PdfCountText.Text = $"({pdfCount} PDF{(pdfCount != 1 ? "s" : "")} indexed)";
                    AnswerTextBox.Text = $"✓ {pdfCount} PDF file(s) loaded and indexed for semantic search.\n\n" +
                        "Ask any question about your documents. The AI will find the most relevant passages " +
                        "and show a confidence score indicating how well the answer matches your question.";
                    StatusText.Text = "Ready - PDFs indexed. Ask a question to search.";
                }
                else
                {
                    _pdfsLoaded = false;
                    QuestionTextBox.IsEnabled = false;
                    AskButton.IsEnabled = false;
                    QuestionTextBox.Text = DisabledPlaceholderText;
                    PdfCountText.Text = "(0 PDFs)";
                    AnswerTextBox.Text = message.Length > 0 ? message : "No PDF files found in the selected folder.";
                    StatusText.Text = "No PDFs found. Please select a different folder.";
                }
            }
            catch (HttpRequestException ex)
            {
                _pdfsLoaded = false;
                AnswerTextBox.Text = "⚠ Error: Could not connect to the backend server.\n\n" +
                    "Please make sure the Python backend is running:\n" +
                    "1. Navigate to the backend directory\n" +
                    "2. Run: pip install flask flask-cors PyPDF2 sentence-transformers\n" +
                    "3. Run: python pdf_qa_server.py\n\n" +
                    $"Technical details: {ex.Message}";
                StatusText.Text = "Connection error - Is the backend running?";
                QuestionTextBox.IsEnabled = false;
                AskButton.IsEnabled = false;
            }
            catch (TaskCanceledException)
            {
                _pdfsLoaded = false;
                AnswerTextBox.Text = "⚠ Request timed out.\n\n" +
                    "Loading and indexing PDFs can take time for large documents.\n" +
                    "Please try again or check if the backend server is responding.";
                StatusText.Text = "Timeout - Please try again";
                QuestionTextBox.IsEnabled = false;
                AskButton.IsEnabled = false;
            }
            catch (Exception ex)
            {
                _pdfsLoaded = false;
                AnswerTextBox.Text = $"⚠ Error loading PDFs: {ex.Message}";
                StatusText.Text = "Error occurred";
                QuestionTextBox.IsEnabled = false;
                AskButton.IsEnabled = false;
            }
            finally
            {
                SelectFolderButton.IsEnabled = true;
            }
        }

        /// <summary>
        /// Clear placeholder text when the question textbox gets focus.
        /// </summary>
        private void QuestionTextBox_GotFocus(object sender, RoutedEventArgs e)
        {
            if (QuestionTextBox.Text == PlaceholderText || 
                QuestionTextBox.Text == DisabledPlaceholderText)
            {
                QuestionTextBox.Text = "";
            }
        }

        /// <summary>
        /// Handle the Ask button click event.
        /// Sends the question to the backend and displays the answer with confidence.
        /// </summary>
        private async void AskButton_Click(object sender, RoutedEventArgs e)
        {
            if (!_pdfsLoaded)
            {
                MessageBox.Show("Please select a PDF folder first to load documents.", 
                    "No PDFs Loaded", 
                    MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            string question = QuestionTextBox.Text.Trim();

            if (string.IsNullOrEmpty(question) || question == PlaceholderText || 
                question == DisabledPlaceholderText)
            {
                MessageBox.Show("Please enter a question.", "Input Required", 
                    MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // Disable UI while processing
            AskButton.IsEnabled = false;
            SelectFolderButton.IsEnabled = false;
            StatusText.Text = "Searching for relevant passages...";
            AnswerTextBox.Text = "🔍 Performing semantic search...";
            ConfidenceText.Text = "";

            try
            {
                var result = await AskQuestionAsync(question);
                AnswerTextBox.Text = result.Answer;
                UpdateConfidenceDisplay(result.Confidence);
                StatusText.Text = result.Confidence > 0 
                    ? $"Found relevant content with {result.Confidence}% confidence" 
                    : "Search complete";
            }
            catch (HttpRequestException ex)
            {
                ConfidenceText.Text = "";
                AnswerTextBox.Text = "⚠ Error: Could not connect to the backend server.\n\n" +
                    "Please make sure the Python backend is running:\n" +
                    "1. Navigate to the backend directory\n" +
                    "2. Run: python pdf_qa_server.py\n\n" +
                    $"Technical details: {ex.Message}";
                StatusText.Text = "Connection error";
            }
            catch (TaskCanceledException)
            {
                ConfidenceText.Text = "";
                AnswerTextBox.Text = "⚠ Request timed out.\n\nThe semantic search took too long. Please try again.";
                StatusText.Text = "Timeout - Please try again";
            }
            catch (Exception ex)
            {
                ConfidenceText.Text = "";
                AnswerTextBox.Text = $"⚠ Error: {ex.Message}";
                StatusText.Text = "Error occurred";
            }
            finally
            {
                AskButton.IsEnabled = true;
                SelectFolderButton.IsEnabled = true;
            }
        }

        /// <summary>
        /// Update the confidence display with appropriate color coding.
        /// </summary>
        private void UpdateConfidenceDisplay(double confidence)
        {
            if (confidence <= 0)
            {
                ConfidenceText.Text = "";
                return;
            }

            ConfidenceText.Text = $"[{confidence}% confidence]";
            
            // Color code based on confidence level
            if (confidence >= HighConfidenceThreshold)
            {
                ConfidenceText.Foreground = new SolidColorBrush(Colors.Green);
            }
            else if (confidence >= MediumConfidenceThreshold)
            {
                ConfidenceText.Foreground = new SolidColorBrush(Colors.Orange);
            }
            else
            {
                ConfidenceText.Foreground = new SolidColorBrush(Colors.Gray);
            }
        }

        /// <summary>
        /// Result from asking a question, including answer and confidence.
        /// </summary>
        private record QuestionResult(string Answer, double Confidence);

        /// <summary>
        /// Send a question to the backend API and return the answer with confidence.
        /// </summary>
        private async Task<QuestionResult> AskQuestionAsync(string question)
        {
            var requestBody = new { question = question };
            string jsonContent = JsonSerializer.Serialize(requestBody);
            var content = new StringContent(jsonContent, Encoding.UTF8, "application/json");

            HttpResponseMessage response = await _httpClient.PostAsync(
                $"{BackendUrl}/ask", content);

            string responseBody = await response.Content.ReadAsStringAsync();

            // Check if the request was successful
            if (!response.IsSuccessStatusCode)
            {
                // Try to extract error message from response
                try
                {
                    using JsonDocument errorDoc = JsonDocument.Parse(responseBody);
                    if (errorDoc.RootElement.TryGetProperty("answer", out JsonElement errorAnswer))
                    {
                        return new QuestionResult(
                            $"Server error ({(int)response.StatusCode}): {errorAnswer.GetString()}", 
                            0);
                    }
                }
                catch
                {
                    // If parsing fails, return generic error
                }
                return new QuestionResult(
                    $"Server returned error status: {(int)response.StatusCode} {response.ReasonPhrase}", 
                    0);
            }

            using JsonDocument doc = JsonDocument.Parse(responseBody);
            JsonElement root = doc.RootElement;

            string answer = "No answer received.";
            double confidence = 0;

            if (root.TryGetProperty("answer", out JsonElement answerElement))
            {
                answer = answerElement.GetString() ?? "No answer received.";
            }

            if (root.TryGetProperty("top_confidence", out JsonElement confidenceElement))
            {
                confidence = confidenceElement.GetDouble();
            }

            return new QuestionResult(answer, confidence);
        }

        /// <summary>
        /// Clean up resources when the window is closed.
        /// </summary>
        protected override void OnClosed(EventArgs e)
        {
            _httpClient.Dispose();
            base.OnClosed(e);
        }
    }
}
