using System;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;

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
        private const string BackendUrl = "http://localhost:5000";

        public MainWindow()
        {
            InitializeComponent();
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(30);
        }

        /// <summary>
        /// Clear placeholder text when the question textbox gets focus.
        /// </summary>
        private void QuestionTextBox_GotFocus(object sender, RoutedEventArgs e)
        {
            if (QuestionTextBox.Text == "Enter your question here...")
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
            string question = QuestionTextBox.Text.Trim();

            if (string.IsNullOrEmpty(question) || question == "Enter your question here...")
            {
                MessageBox.Show("Please enter a question.", "Input Required", 
                    MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // Disable UI while processing
            AskButton.IsEnabled = false;
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
