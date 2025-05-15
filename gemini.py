# Import necessary libraries
import os
import tempfile
import shutil
import io
import sys

import fitz  # PyMuPDF
import pdf2image
from PIL import Image
import google.generativeai as genai
from docx import Document  # For creating .docx files

# Set your Google API key directly in the code
API_KEY = "AIzaSyB0yZWHCh_GsBuzlgeSrwFa84DMztRNUxQ"  # Replace with your actual API key

# Input PDF file (in the same directory as this script)
INPUT_PDF = "bmcq.pdf"  # Replace with your actual PDF filename

# Set up Gemini model
def setup_gemini(api_key):
    if not api_key:
        print("API Key is missing. Cannot initialize Gemini model.")
        return None
    genai.configure(api_key=api_key)
    model_name = 'gemini-1.5-flash'
    print(f"Initializing Gemini model: {model_name}")
    try:
        model = genai.GenerativeModel(model_name)
        print("Model initialized successfully.")
        return model
    except Exception as e:
        print(f"\n------------------- ERROR -------------------")
        print(f"Error initializing model '{model_name}': {e}")
        return None

# Extract text directly from PDF page using PyMuPDF
def extract_text_directly_from_pdf_page(page):
    """Extracts text from a single PyMuPDF page object."""
    try:
        text = page.get_text("text")
        return text.strip() if text else ""
    except Exception as e:
        print(f"Error extracting text directly from page: {e}")
        return ""

def is_page_likely_scanned(text_from_direct_extraction, char_threshold=50):
    """
    Heuristic to determine if a page is likely scanned or has minimal text.
    If direct text extraction yields less than char_threshold characters,
    it might be an image-based page or a page with very sparse text.
    """
    return len(text_from_direct_extraction) < char_threshold

# Convert PDF page to image
def convert_pdf_page_to_image(pdf_path, page_number, temp_dir, dpi=150):
    """Converts a single page of a PDF to a JPEG image."""
    try:
        # pdf2image expects 0-indexed page numbers if passed as a list for first_page/last_page
        # but convert_from_path with single_file=True for a specific page might need 1-indexed.
        # For safety, let's use first_page and last_page with 0-indexed numbers.
        # pdf2image page numbers are 1-based. So page_number needs to be passed as is.
        images = pdf2image.convert_from_path(
            pdf_path,
            dpi=dpi,
            output_folder=temp_dir,
            first_page=page_number + 1, # pdf2image is 1-indexed for first_page
            last_page=page_number + 1,  # and last_page
            fmt='jpeg',
            thread_count=1, # Only one page
            paths_only=True,
            output_file=f"page_{page_number}" # Ensure unique filename
        )
        if images:
            return images[0]
        return None
    except Exception as e:
        print(f"Error converting PDF page {page_number} to image: {e}")
        return None

# Extract text from image using Gemini
def extract_text_from_image_using_gemini(image_path, model, page_num_for_error="Unknown"):
    if not model:
        print("Gemini model not initialized, cannot extract text from image.")
        return f"--- ERROR: Gemini model not initialized for page {page_num_for_error} ---"
    if not os.path.exists(image_path):
        print(f"Error: Image file not found at {image_path}")
        return f"--- ERROR: Image file missing for page {page_num_for_error} ({os.path.basename(image_path)}) ---"

    try:
        img = Image.open(image_path)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        img_byte_arr = img_byte_arr.getvalue()

        prompt = ("""
        Please perform OCR on this image.
        Extract all the text visible.
        Preserve the original structure, line breaks, and paragraph formatting as accurately as possible.
        If the image contains Bangla text, ensure it is extracted correctly.
        Do not add any commentary, explanations, or text other than the extracted content from the image.
        Output *only* the extracted text.
        """)
        
        image_part = {"mime_type": "image/jpeg", "data": img_byte_arr}
        
        # Check if the model supports system instructions or specific roles
        # For gemini-1.5-flash, direct content is fine.
        response = model.generate_content([prompt, image_part])
        
        extracted_text = ""
        if hasattr(response, 'text') and response.text:
            extracted_text = response.text
        elif response.parts:
            extracted_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
        
        if not extracted_text.strip(): # If Gemini returns empty or only whitespace
             print(f"Warning: Gemini returned no text for page {page_num_for_error} ({os.path.basename(image_path)}). Image might be blank or unreadable.")
             return f"--- NOTICE: No text found by OCR on page {page_num_for_error} ({os.path.basename(image_path)}) ---" # Less alarming than ERROR

        return extracted_text

    except Exception as e:
        print(f"An error occurred during Gemini text extraction for {os.path.basename(image_path)} (Page {page_num_for_error}): {e}")
        return f"--- ERROR: Exception during Gemini OCR for page {page_num_for_error} ({os.path.basename(image_path)}): {str(e)} ---"

# Hybrid PDF processing function
def process_pdf_hybrid(pdf_path, gemini_model, update_progress_callback=None):
    """
    Processes a PDF by first trying direct text extraction, then falling back to
    OCR via Gemini for pages that seem to be image-based or have little extractable text.

    Args:
        pdf_path (str): Path to the PDF file.
        gemini_model: Initialized Gemini model.
        update_progress_callback (function, optional): Callback to update progress. 
                                                     It should accept (current_page, total_pages, message).

    Returns:
        list: A list of strings, where each string is the extracted text from a page.
        str: Path to the temporary directory created for images (if any), or None.
        bool: True if any errors occurred during extraction, False otherwise.
    """
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        if update_progress_callback:
            update_progress_callback(-1, -1, f"Error: PDF file not found.")
        return [], None, True

    all_extracted_text = []
    temp_dir_for_images = None
    has_errors = False

    try:
        pdf_document = fitz.open(pdf_path)
        total_pages = len(pdf_document)

        if total_pages == 0:
            print(f"Warning: PDF file {pdf_path} has 0 pages.")
            if update_progress_callback:
                update_progress_callback(0, 0, "Warning: PDF has 0 pages.")
            return [], None, False # Not an error, but no content

        temp_dir_for_images = tempfile.mkdtemp() # Create if OCR needed
        print(f"Created temporary directory for images (if needed): {temp_dir_for_images}")

        for i in range(total_pages):
            page_num_display = i + 1
            if update_progress_callback:
                update_progress_callback(page_num_display, total_pages, f"Processing page {page_num_display}/{total_pages}...")

            page = pdf_document.load_page(i)
            directly_extracted_text = extract_text_directly_from_pdf_page(page)

            if is_page_likely_scanned(directly_extracted_text):
                print(f"Page {page_num_display}: Low direct text. Attempting OCR.")
                if update_progress_callback:
                     update_progress_callback(page_num_display, total_pages, f"Page {page_num_display}: Low direct text, attempting OCR...")
                
                image_path = convert_pdf_page_to_image(pdf_path, i, temp_dir_for_images) # i is 0-indexed here
                if image_path and os.path.exists(image_path):
                    page_text = extract_text_from_image_using_gemini(image_path, gemini_model, page_num_for_error=page_num_display)
                    if "--- ERROR:" in page_text:
                        has_errors = True
                    all_extracted_text.append(page_text)
                else:
                    print(f"Page {page_num_display}: Failed to convert to image for OCR.")
                    all_extracted_text.append(f"--- ERROR: Failed to convert page {page_num_display} to image for OCR ---")
                    has_errors = True
            else:
                # print(f"Page {page_num_display}: Successfully extracted text directly.")
                all_extracted_text.append(directly_extracted_text)
        
        pdf_document.close()

    except Exception as e:
        print(f"Critical error processing PDF {pdf_path} with hybrid approach: {e}")
        all_extracted_text.append(f"--- CRITICAL ERROR PROCESSING PDF: {str(e)} ---")
        has_errors = True
        # Ensure pdf_document is closed if it was opened
        if 'pdf_document' in locals() and pdf_document.is_closed == False:
            pdf_document.close()

    # If temp_dir was created but no images were actually made (e.g., all direct extraction)
    # or if it's empty, we can remove it.
    if temp_dir_for_images and os.path.exists(temp_dir_for_images) and not os.listdir(temp_dir_for_images):
        print(f"Cleaning up empty temp directory: {temp_dir_for_images}")
        shutil.rmtree(temp_dir_for_images)
        temp_dir_for_images = None # Set to None if removed
    elif temp_dir_for_images and not os.path.exists(temp_dir_for_images): # Should not happen if created
        temp_dir_for_images = None


    return all_extracted_text, temp_dir_for_images, has_errors

# Main function
def main():
    # Use the API key defined at the top of the file
    model = setup_gemini(API_KEY)
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

    print("\nExtracting text from PDF...")
    all_extracted_text, temp_dir_for_images, errors_occurred = process_pdf_hybrid(
        pdf_path, 
        model
    )

    if errors_occurred:
        print("\n--- Processing completed with errors. ---")
    else:
        print("\n--- Processing completed successfully. ---")

    # Output and save
    if all_extracted_text:
        output_filename_base = os.path.splitext(pdf_path)[0]
        
        # Save to TXT
        txt_output_filename = output_filename_base + "_hybrid_extracted.txt"
        txt_output_path = os.path.join(os.path.dirname(pdf_path), txt_output_filename)
        try:
            with open(txt_output_path, 'w', encoding='utf-8') as f:
                for i, page_text in enumerate(all_extracted_text):
                    f.write(f"--- PAGE {i+1} ---\n")
                    f.write(page_text if page_text else "[No text extracted for this page]")
                    f.write("\n\n")
            print(f"Text saved to: {txt_output_path}")
        except Exception as e:
            print(f"Error saving to TXT {txt_output_path}: {e}")

        # Save to DOCX
        docx_output_filename = output_filename_base + "_hybrid_extracted.docx"
        docx_output_path = os.path.join(os.path.dirname(pdf_path), docx_output_filename)
        try:
            document = Document()
            for i, page_text in enumerate(all_extracted_text):
                document.add_paragraph(f"--- PAGE {i+1} ---")
                document.add_paragraph(page_text if page_text else "[No text extracted for this page]")
                if i < len(all_extracted_text) - 1:
                    document.add_page_break()
            document.save(docx_output_path)
            print(f"Text saved to: {docx_output_path}")
        except Exception as e:
            print(f"Error saving to DOCX {docx_output_path}: {e}")
            
        # print("\nPreview of extracted text (first 1000 chars of page 1 if available):")
        # if all_extracted_text[0]:
        # print(all_extracted_text[0][:1000] + ("..." if len(all_extracted_text[0]) > 1000 else ""))
    else:
        print("No text was extracted from the PDF.")

    if temp_dir_for_images and os.path.exists(temp_dir_for_images):
        try:
            print(f"Cleaning up temporary image directory: {temp_dir_for_images}")
            shutil.rmtree(temp_dir_for_images)
        except Exception as e:
            print(f"Warning: Could not remove temporary directory {temp_dir_for_images}: {e}")

if __name__ == "__main__":
    main()