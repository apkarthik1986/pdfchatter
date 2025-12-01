using System;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;
using Microsoft.Win32;

namespace PdfChatter
{
    /// <summary>
    /// Interaction logic for MainWindow.xaml
    /// This WPF application connects to a Python Flask backend
    /// to answer questions based on PDF content.
    /// </summary>
    public partial class MainWindow : Window
    {
        private readonly HttpClient _httpClient;
        private const string BackendUrl = "http://127.0.0.1:5000";
        private const string PlaceholderText = "Enter your question here...";
        private const string DisabledPlaceholderText = "Select a PDF folder first...";
        private bool _pdfsLoaded = false;

        public MainWindow()
        {
            InitializeComponent();
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(30);
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
        /// </summary>
        private async Task LoadPdfsFromFolderAsync(string folderPath)
        {
            // Disable UI while loading
            SelectFolderButton.IsEnabled = false;
            AskButton.IsEnabled = false;
            QuestionTextBox.IsEnabled = false;
            StatusText.Text = "Loading PDFs from folder...";
            FolderPathTextBox.Text = folderPath;
            PdfCountText.Text = "";
            AnswerTextBox.Text = "Loading PDFs...";

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
                    PdfCountText.Text = $"({pdfCount} PDF{(pdfCount != 1 ? "s" : "")} loaded)";
                    AnswerTextBox.Text = $"Ready! {pdfCount} PDF file(s) loaded.\n\nAsk a question about your PDFs.";
                    StatusText.Text = "PDFs loaded successfully. Ready to answer questions.";
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
                AnswerTextBox.Text = "Error: Could not connect to the backend server.\n\n" +
                    "Please make sure the Python backend is running:\n" +
                    "1. Navigate to the backend directory\n" +
                    "2. Run: python pdf_qa_server.py\n\n" +
                    $"Technical details: {ex.Message}";
                StatusText.Text = "Connection error";
                QuestionTextBox.IsEnabled = false;
                AskButton.IsEnabled = false;
            }
            catch (Exception ex)
            {
                _pdfsLoaded = false;
                AnswerTextBox.Text = $"Error loading PDFs: {ex.Message}";
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
        /// Sends the question to the backend and displays the answer.
        /// </summary>
        private async void AskButton_Click(object sender, RoutedEventArgs e)
        {
            if (!_pdfsLoaded)
            {
                MessageBox.Show("Please select a PDF folder first.", "PDFs Not Loaded", 
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
            StatusText.Text = "Sending question to backend...";
            AnswerTextBox.Text = "Processing...";

            try
            {
                string answer = await AskQuestionAsync(question);
                AnswerTextBox.Text = answer;
                StatusText.Text = "Answer received";
            }
            catch (HttpRequestException ex)
            {
                AnswerTextBox.Text = "Error: Could not connect to the backend server.\n\n" +
                    "Please make sure the Python backend is running:\n" +
                    "1. Navigate to the backend directory\n" +
                    "2. Run: python pdf_qa_server.py\n\n" +
                    $"Technical details: {ex.Message}";
                StatusText.Text = "Connection error";
            }
            catch (Exception ex)
            {
                AnswerTextBox.Text = $"Error: {ex.Message}";
                StatusText.Text = "Error occurred";
            }
            finally
            {
                AskButton.IsEnabled = true;
                SelectFolderButton.IsEnabled = true;
            }
        }

        /// <summary>
        /// Send a question to the backend API and return the answer.
        /// </summary>
        private async Task<string> AskQuestionAsync(string question)
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
                        return $"Server error ({(int)response.StatusCode}): {errorAnswer.GetString()}";
                    }
                }
                catch
                {
                    // If parsing fails, return generic error
                }
                return $"Server returned error status: {(int)response.StatusCode} {response.ReasonPhrase}";
            }

            using JsonDocument doc = JsonDocument.Parse(responseBody);
            JsonElement root = doc.RootElement;

            if (root.TryGetProperty("answer", out JsonElement answerElement))
            {
                return answerElement.GetString() ?? "No answer received.";
            }

            return "Unexpected response format from the server.";
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
