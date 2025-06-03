# Import necessary libraries
import os
import tempfile
import pdf2image
from PIL import Image
import google.generativeai as genai
import io
import sys  # For exiting gracefully
import shutil  # For cleanup
from docx import Document  # For creating .docx files

# Input PDF file (in the same directory as this script)
INPUT_PDF = "bmcq.pdf"  # Replace with your actual PDF filename

# Set up Gemini model
def setup_gemini(api_key):
    genai.configure(api_key=api_key)
    model_name = 'gemini-1.5-flash'  # Changed from gemini-2.5-flash-preview-04-17
    
    print(f"Initializing Gemini model: {model_name}")
    try:
        model = genai.GenerativeModel(model_name)
        print("Model initialized successfully.")
        return model
    except Exception as e:
        print(f"\n------------------- ERROR -------------------")
        print(f"Error initializing model '{model_name}': {e}")
        return None  # Return None if model initialization fails

# PDF to images conversion
def convert_pdf_to_images(pdf_path):
    print("Converting PDF to images...")
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return [], None

    temp_dir = tempfile.mkdtemp()
    print(f"Created temporary directory for images: {temp_dir}")

    try:
        images = pdf2image.convert_from_path(
            pdf_path,
            dpi=100,  # Changed from 300, experiment with values like 200 or 150
            output_folder=temp_dir,
            fmt='jpeg',
            thread_count=4,
            paths_only=True
        )
        image_paths = images
        print(f"Converted {len(image_paths)} pages to images.")
        return image_paths, temp_dir
    except Exception as e:
        print(f"An error occurred during PDF to image conversion: {e}")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return [], None

# Extract text from image using Gemini
def extract_text_from_image(image_path, model):
    if not model:
        print("Model not initialized, cannot extract text.")
        return None

    if not os.path.exists(image_path):
        print(f"Error: Image file not found at {image_path}")
        return None

    try:
        img = Image.open(image_path)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        img_byte_arr = img_byte_arr.getvalue()

        prompt = """
        Please perform OCR on this image containing Bangla text.
        Extract all the Bangla text visible.
        Preserve the original structure, line breaks, and paragraph formatting as accurately as possible based on the visual layout.
        Do not add any commentary, explanations, or text other than the extracted content from the image.
        Output *only* the extracted text.
        """

        image_part = {"mime_type": "image/jpeg", "data": img_byte_arr}
        prompt_part = prompt

        response = model.generate_content([prompt_part, image_part])

        extracted_text = ""
        if hasattr(response, 'text'):
            extracted_text = response.text
        elif response.parts:
            extracted_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
        else:
            print(f"Warning: Could not extract text from response structure for {os.path.basename(image_path)}.")
            extracted_text = f"--- ERROR: Could not parse response for page {os.path.basename(image_path)} ---"

        return extracted_text

    except Exception as e:
        print(f"An error occurred during text extraction for {os.path.basename(image_path)}: {e}")
        return f"--- ERROR: Exception during extraction for page {os.path.basename(image_path)}: {e} ---"

# Main function
def main():
    # Get API key from environment variable or user input
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        api_key = input("Please enter your Gemini API key: ").strip()
        if not api_key:
            print("API key is required to run this script.")
            sys.exit(1)

    model = setup_gemini(api_key)
    if not model:
        print("Failed to initialize model. Please check your API key.")
        sys.exit(1)

    # Use the input PDF defined at the top of the file
    pdf_path = INPUT_PDF
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file '{pdf_path}' not found in the current directory.")
        print(f"Current directory: {os.getcwd()}")
        print(f"Files in directory: {os.listdir('.')}")
        sys.exit(1)

    image_paths, temp_dir = convert_pdf_to_images(pdf_path)
    if temp_dir is None:
        temp_dir = ""

    if not image_paths:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        sys.exit(1)

    print("\nExtracting text from images...")
    all_extracted_text = []
    has_errors = False

    for i, image_path in enumerate(image_paths):
        if not image_path or not os.path.exists(image_path):
            print(f"Skipping page {i+1} - Image path invalid or file missing: {image_path}")
            all_extracted_text.append(f"--- ERROR: Image file missing for page {i+1} ---")
            has_errors = True
            continue

        print(f"Processing page {i+1}/{len(image_paths)} ({os.path.basename(image_path)})...")
        extracted_text = extract_text_from_image(image_path, model)

        if extracted_text is None or "--- ERROR:" in extracted_text:
            all_extracted_text.append(extracted_text or f"--- ERROR EXTRACTING PAGE {i+1} ---")
            has_errors = True
        else:
            all_extracted_text.append(extracted_text)
            print(f"Completed page {i+1}")

    full_text = "\n\n--- Page Break ---\n\n".join(all_extracted_text)

    if temp_dir and os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Warning: Could not remove temporary directory {temp_dir}: {e}")

    # Save extracted text to .docx file
    output_filename = os.path.splitext(pdf_path)[0] + "_extracted.docx"
    try:
        document = Document()
        for page_text in all_extracted_text:
            document.add_paragraph(page_text)
            document.add_page_break()
        document.save(output_filename)
        print(f"\nText extraction complete! Saved to {output_filename}")
    except Exception as e:
        print(f"Error saving extracted text to file {output_filename}: {e}")
        has_errors = True

    if full_text:
        print("\nPreview of extracted text:")
        print(full_text[:1000] + ("..." if len(full_text) > 1000 else ""))
        if has_errors:
            print("\nNOTE: Errors occurred during processing. Check the output file for details.")
    elif has_errors:
        print("\nNo text extracted or an error occurred before preview.")

if __name__ == "__main__":
    main()