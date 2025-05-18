# Import necessary libraries
import os
import tempfile
from PyPDF2 import PdfReader
import pdf2image
from PIL import Image
import google.generativeai as genai
import io
import sys  # For exiting gracefully
import shutil  # For cleanup
from docx import Document  # For creating .docx files
import concurrent.futures  # For parallel processing
import time  # For timing operations

# Set your Google API key directly in the code
API_KEY = "AIzaSyB0yZWHCh_GsBuzlgeSrwFa84DMztRNUxQ"  # Replace with your actual API key

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
            dpi=100,  # Lower DPI for faster processing
            output_folder=temp_dir,
            fmt='jpeg',
            thread_count=os.cpu_count() or 4,  # Use all available CPU cores
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

# Optimize image before sending to API
def optimize_image(image_path, max_size=(1500, 1500), quality=85):
    """Resize and optimize image to reduce API request size and processing time"""
    try:
        img = Image.open(image_path)
        
        # Only resize if image is larger than max_size
        if img.width > max_size[0] or img.height > max_size[1]:
            img.thumbnail(max_size, Image.LANCZOS)
        
        # Optimize to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG', quality=quality, optimize=True)
        return img_byte_arr.getvalue()
    except Exception as e:
        print(f"Error optimizing image {image_path}: {e}")
        return None

# Extract text from image using Gemini
def extract_text_from_image(image_path, model):
    if not model:
        print("Model not initialized, cannot extract text.")
        return None

    if not os.path.exists(image_path):
        print(f"Error: Image file not found at {image_path}")
        return None

    try:
        # Optimize image before sending to API
        img_byte_arr = optimize_image(image_path)
        if not img_byte_arr:
            return f"--- ERROR: Failed to optimize image for {os.path.basename(image_path)} ---"

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

# Process a batch of images in parallel
def process_images_in_parallel(image_paths, model, max_workers=None):
    """
    Process multiple images in parallel using a thread pool
    Returns a list of extracted text in the same order as image_paths
    """
    if not max_workers:
        # Use a reasonable number of workers based on CPU cores, but not too many
        max_workers = min(os.cpu_count() or 4, 8)  # Max 8 concurrent requests
    
    results = [None] * len(image_paths)
    
    print(f"Processing {len(image_paths)} images with {max_workers} parallel workers")
    
    # Define a worker function that updates the results list
    def process_image(idx_and_path):
        idx, path = idx_and_path
        try:
            if not path or not os.path.exists(path):
                results[idx] = f"--- ERROR: Image file missing for page {idx+1} ---"
                return False
            
            print(f"Processing page {idx+1}/{len(image_paths)} ({os.path.basename(path)})...")
            start_time = time.time()
            text = extract_text_from_image(path, model)
            end_time = time.time()
            
            results[idx] = text or f"--- ERROR EXTRACTING PAGE {idx+1} ---"
            
            print(f"Completed page {idx+1} in {end_time - start_time:.2f} seconds")
            return True
        except Exception as e:
            print(f"Error in worker processing image {idx+1}: {e}")
            results[idx] = f"--- ERROR: Worker exception for page {idx+1}: {str(e)} ---"
            return False
    
    # Create index-path pairs
    indexed_paths = list(enumerate(image_paths))
    
    # Process images in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(process_image, indexed_paths)
    
    return results

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

    image_paths, temp_dir = convert_pdf_to_images(pdf_path)
    if temp_dir is None:
        temp_dir = ""

    if not image_paths:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        sys.exit(1)

    print("\nExtracting text from images...")
    start_time = time.time()
    
    # Use parallel processing instead of sequential processing
    all_extracted_text = process_images_in_parallel(image_paths, model)
    
    end_time = time.time()
    print(f"\nText extraction completed in {end_time - start_time:.2f} seconds")
    
    has_errors = any("--- ERROR:" in text if text else True for text in all_extracted_text)

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

    full_text = "\n\n--- Page Break ---\n\n".join(all_extracted_text)
    if full_text:
        print("\nPreview of extracted text:")
        print(full_text[:1000] + ("..." if len(full_text) > 1000 else ""))
        if has_errors:
            print("\nNOTE: Errors occurred during processing. Check the output file for details.")
    elif has_errors:
        print("\nNo text extracted or an error occurred before preview.")

if __name__ == "__main__":
    main()