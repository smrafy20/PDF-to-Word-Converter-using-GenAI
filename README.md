# PDF to Word Converter using Gemini AI

A professional web application that converts PDF documents to editable Word files using Google's Gemini AI. Features a clean, user-friendly interface with advanced AI model selection.

## Features

- **Multiple AI Models**: Choose from Gemini 2.0 Flash, Gemini 2.5 Flash Preview, or Gemini 1.5 Flash
- **Drag & Drop Upload**: Easy PDF file upload with progress tracking
- **Multiple Output Formats**: Export as Word (.docx) or Plain Text (.txt)
- **Real-time Processing**: Live progress updates with percentage tracking
- **Secure**: Your API key is never stored on our servers
- **Multilingual Support**: Excellent for various languages including Bangla text

## Prerequisites

Before running this application, you'll need:

1. Python 3.8 or higher
2. A Google Gemini API key (get one from [Google AI Studio](https://ai.google.dev/))
3. The dependencies listed in the requirements.txt file

## Installation

1. Clone or download this repository to your local machine

2. Install the required Python packages:
   ```
   pip install -r requirements.txt
   ```

3. For PDF to image conversion, you'll need Poppler installed:

   - **Windows users**:
     - Download Poppler for Windows from [here](https://github.com/oschwartz10612/poppler-windows/releases/)
     - Extract the downloaded file
     - Add the `bin` directory to your PATH environment variable:
       1. Right-click on "This PC" or "My Computer" and select "Properties"
       2. Click on "Advanced system settings"
       3. Click on "Environment Variables"
       4. Under "System variables", find the "Path" variable, select it and click "Edit"
       5. Click "New" and add the path to the bin folder (e.g., `C:\path\to\poppler-xx\bin`)
       6. Click "OK" to close all dialogs

   - **Mac users**:
     ```
     brew install poppler
     ```

   - **Linux users**:
     ```
     sudo apt-get install poppler-utils
     ```

## Usage

1. Start the application:
   ```
   python app.py
   ```

2. Open your web browser and go to:
   ```
   http://localhost:5000
   ```

3. Use the web interface to:
   - **Select AI Model**: Choose from 3 available Gemini models
   - **Enter API Key**: Provide your own Gemini API key
   - **Upload PDF**: Drag & drop or browse (max 64MB)
   - **Choose Format**: Word (.docx) or Text (.txt)
   - **Monitor Progress**: Real-time processing updates
   - **Download**: Get your converted file when complete

## Available AI Models

- **Gemini 2.0 Flash**: Latest multimodal model with next-gen features
- **Gemini 2.5 Flash Preview**: High-performance model with excellent accuracy
- **Gemini 1.5 Flash**: Fast and reliable (recommended for most users)

## Configuration

- Upload folder: `./uploads` (auto-created)
- Max file size: 64MB
- Supported formats: PDF input, DOCX/TXT output
- API key: User-provided (secure, not stored)

## Project Structure

```
├── app.py                 # Flask web application
├── gemini.py              # AI text extraction logic
├── requirements.txt       # Dependencies
├── templates/             # HTML templates
└── uploads/               # File storage
```

## Troubleshooting

- **Model initialization fails**: Verify your API key and model availability
- **PDF conversion issues**: Ensure Poppler is installed and in PATH
- **Slow processing**: Normal for large PDFs (each page processed individually)
- **Extraction accuracy**: Depends on PDF quality and text representation

## License

[MIT License](LICENSE)

## Acknowledgements

- This project uses Google's Gemini AI model for text extraction
- PDF to image conversion is handled by the pdf2image library

Choose model feature added.
![image](https://github.com/user-attachments/assets/58f1664f-9cd0-4e92-ad64-441204b030fd)
