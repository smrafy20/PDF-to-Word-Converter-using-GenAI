from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
import os
import tempfile
import shutil
import time
import threading
import uuid
from werkzeug.utils import secure_filename
import gemini  # Import your existing module

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secret key for flashing messages
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64MB max upload size

# Create uploads folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf'}
DEFAULT_API_KEY = "AIzaSyADwq4wU7teSb-fpzgU10FWOA-vWE9UCVU"  # Replace with your actual API key

# Dictionary to store processing tasks
processing_tasks = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Check API key selection
        api_key_option = request.form.get('api_key_option', 'default')
        
        if api_key_option == 'default':
            api_key = DEFAULT_API_KEY
        else:
            api_key = request.form.get('api_key')
            if not api_key:
                flash('Please provide an API key')
                return redirect(request.url)
        
        # Get selected output format
        output_format = request.form.get('output_format')
        if not output_format:
            flash('Please select an output format')
            return redirect(request.url)
        
        # Check if file is included in the request
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Generate a unique task ID
            task_id = str(uuid.uuid4())
            session['current_task_id'] = task_id
            
            # Create a task record in the processing_tasks dictionary
            processing_tasks[task_id] = {
                'status': 'initializing',
                'percentage': 0,
                'current_page': 0,
                'total_pages': 0,
                'message': 'Initializing processing...',
                'result': None,
                'output_format': output_format,
                'filename': filename,
                'filepath': filepath
            }
            
            # Start processing in a background thread
            thread = threading.Thread(
                target=process_pdf_with_progress,
                args=(task_id, filepath, api_key, output_format)
            )
            thread.daemon = True
            thread.start()
            
            # Redirect to the processing page
            return render_template('processing.html')
        else:
            flash('File type not allowed. Please upload a PDF file.')
            return redirect(request.url)
    
    return render_template('index.html')

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        flash('The requested file does not exist.')
        return redirect(url_for('index'))
    
    return send_file(file_path, as_attachment=True)

@app.errorhandler(413)
def too_large(e):
    flash('File is too large (maximum size is 64MB).')
    return redirect(url_for('index'))

def process_pdf_with_progress(task_id, filepath, api_key, output_format):
    task = processing_tasks[task_id]
    original_filename_base = os.path.splitext(task['filename'])[0]
    temp_dir_for_images = None  # Initialize to None

    try:
        task['status'] = 'processing'
        task['message'] = 'Initializing AI model...'
        task['percentage'] = 5 # Small percentage for initialization
        processing_tasks[task_id] = task # Update task

        model = gemini.setup_gemini(api_key)
        if not model:
            task['status'] = 'error'
            task['message'] = 'Failed to initialize the Gemini model. Please check your API key.'
            task['percentage'] = 100 # Mark as done for progress bar
            processing_tasks[task_id] = task # Update task
            return

        task['message'] = 'Converting PDF to images...'
        task['percentage'] = 10 # Progress after init
        processing_tasks[task_id] = task # Update task

        image_paths, temp_dir_for_images = gemini.convert_pdf_to_images(filepath)
        if not image_paths or temp_dir_for_images is None:
            task['status'] = 'error'
            task['message'] = 'Failed to convert PDF to images.'
            task['percentage'] = 100 # Mark as done
            processing_tasks[task_id] = task # Update task
            return
        
        task['total_pages'] = len(image_paths)
        task['message'] = f"Converted to {len(image_paths)} pages. Extracting text..."
        task['percentage'] = 20 # Progress after conversion
        processing_tasks[task_id] = task # Update task

        all_extracted_text = []
        has_errors_during_extraction = False
        
        for i, image_path in enumerate(image_paths):
            task['current_page'] = i + 1
            task['message'] = f"Extracting text from page {i+1} of {task['total_pages']}..."
            # Calculate percentage: 20% for conversion, 70% for extraction (scaled), 10% for file generation
            base_percentage_after_conversion = 20
            extraction_percentage_span = 70
            task['percentage'] = base_percentage_after_conversion + int(((i + 1) / task['total_pages']) * extraction_percentage_span) 
            processing_tasks[task_id] = task # Update task

            if not image_path or not os.path.exists(image_path):
                all_extracted_text.append(f"--- ERROR: Image file missing for page {i+1} ---")
                has_errors_during_extraction = True
                continue
            
            extracted_text = gemini.extract_text_from_image(image_path, model)
            
            if extracted_text is None or "--- ERROR:" in extracted_text:
                all_extracted_text.append(extracted_text or f"--- ERROR EXTRACTING PAGE {i+1} ---")
                has_errors_during_extraction = True
            else:
                all_extracted_text.append(extracted_text)

        task['message'] = 'Generating output file...'
        task['percentage'] = 95 # Nearing completion, before final file saving
        processing_tasks[task_id] = task # Update task
        
        output_base = original_filename_base + "_extracted"
        generated_files_info = [] # Use list of dicts for JS compatibility
        
        if output_format == 'docx':
            from docx import Document # Import locally as in original code
            docx_filename = output_base + ".docx"
            docx_path = os.path.join(app.config['UPLOAD_FOLDER'], docx_filename)
            
            document = Document()
            for idx, page_text in enumerate(all_extracted_text):
                document.add_paragraph(page_text)
                if idx < len(all_extracted_text) - 1: # Add page break if not the last page
                    document.add_page_break()
            document.save(docx_path)
            generated_files_info.append({'type': 'docx', 'name': docx_filename})
        
        elif output_format == 'txt':
            txt_filename = output_base + ".txt"
            txt_path = os.path.join(app.config['UPLOAD_FOLDER'], txt_filename)
            
            with open(txt_path, 'w', encoding='utf-8') as txt_file:
                for i, page_text in enumerate(all_extracted_text):
                    txt_file.write(page_text)
                    if i < len(all_extracted_text) - 1:
                        txt_file.write('\\n\\n--- PAGE BREAK ---\\n\\n')
            generated_files_info.append({'type': 'txt', 'name': txt_filename})

        task['status'] = 'completed'
        task['percentage'] = 100
        task['result'] = generated_files_info # Store info about generated file(s)
        if has_errors_during_extraction:
            task['message'] = 'Processing complete with some errors. Please check the output file.'
        else:
            task['message'] = 'Processing complete! Your file is ready for download.'
        processing_tasks[task_id] = task # Final update

    except Exception as e:
        app.logger.error(f"Error processing task {task_id}: {str(e)}", exc_info=True)
        if task_id in processing_tasks: # Ensure task exists
            task['status'] = 'error'
            task['message'] = f'An critical error occurred: {str(e)}'
            task['percentage'] = 100 # Mark as done for progress bar UI
            processing_tasks[task_id] = task # Update task
    finally:
        # Clean up temporary directory for images
        if temp_dir_for_images and os.path.exists(temp_dir_for_images):
            try:
                shutil.rmtree(temp_dir_for_images)
            except Exception as e:
                app.logger.error(f"Error cleaning up temp_dir {temp_dir_for_images} for task {task_id}: {str(e)}")
        
        # Clean up the originally uploaded PDF file
        if filepath and os.path.exists(filepath): # filepath is from args
            try:
                os.remove(filepath)
            except Exception as e:
                app.logger.error(f"Error cleaning up uploaded file {filepath} for task {task_id}: {str(e)}")
        
        # Update task to indicate original file cleaned up
        if task_id in processing_tasks:
             processing_tasks[task_id]['original_filepath_cleaned_up'] = True

@app.route('/progress/<task_id>') # Ensure this route is correct
def get_progress_status(task_id):
    task = processing_tasks.get(task_id)
    if not task:
        return jsonify({'status': 'error', 'message': 'Task not found. It might have expired or never started.', 'percentage': 100}), 404
    return jsonify(task)

@app.route('/download-result/<task_id>')
def download_result(task_id):
    if task_id not in processing_tasks or processing_tasks[task_id]['status'] != 'completed':
        flash('The requested processing task does not exist or is not complete.')
        return redirect(url_for('index'))
    
    task = processing_tasks[task_id]
    
    # Show warning if there were errors during processing
    if task.get('has_errors', False):
        flash('Some pages could not be processed correctly. Please check the downloaded file(s).')
    
    # Render the download page with the list of generated files
    return render_template('download.html', files=task['result'])

if __name__ == '__main__':
    app.run(debug=True)