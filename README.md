# PDF to Word Converter using Google Cloud Vision API

This project is a Flask web application that converts PDF files to editable Word (.docx) or plain text (.txt) files using OCR powered by Google Cloud Vision API.

## Features
- Upload PDF files and convert them to DOCX or TXT.
- Uses Google Cloud Vision API for accurate OCR (supports many languages).
- Parallel processing for fast conversion.
- Clean, modern web interface.

## Setup Instructions

### 1. Clone the Repository
```
git clone <https://github.com/smrafy20/PDF-to-Word-Converter-using-GenAI.git>
cd PDF-to-Word-Converter-using-GenAI
```

### 2. Install Dependencies
Upgrade pip, setuptools, and wheel first:
```
python -m pip install --upgrade pip setuptools wheel
```
Then install requirements:
```
pip install -r requirements.txt
```

### 3. Set Up Google Cloud Vision API
- Create a Google Cloud project at https://console.cloud.google.com/
- Enable the Vision API for your project.
- Create a service account and download the JSON key file.
- Place the JSON key somewhere safe (e.g., in your project folder, but do NOT commit it to git).
- Set the environment variable in your `app.py` (already present):
  ```python
  os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"path\\to\\your\\service-account.json"
  ```
  Replace with your actual path.

### 4. Install Poppler for Windows
- Download Poppler for Windows: https://github.com/oschwartz10612/poppler-windows/releases/
- Extract and add the `bin` folder to your system PATH.
- This is required for PDF to image conversion.

### 5. Run the App
```
python app.py
```
- Open your browser and go to http://127.0.0.1:5000/

## Usage
1. Upload a PDF file.
2. Choose output format (Word or Text).
3. Click "Convert Now".
4. Wait for processing and download your converted file.

## Notes
- Only PDF files are supported for upload.
- The app uses your Google Cloud Vision API quota and may incur costs for large usage.
- For best results, use clear, high-quality PDFs.

## License
MIT License
