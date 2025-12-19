import os
import io
import uuid
import shutil
import logging
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

import pandas as pd
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, send_from_directory
)
from werkzeug.utils import secure_filename

# PIL for image validation
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

import config
import database as db
from email_sender import test_smtp_connection, test_all_configurations, send_emails

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload


# ============================================================================
# Authentication helpers
# ============================================================================

def login_required(f):
    """Decorator to require login for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if this is an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
                  request.content_type == 'multipart/form-data' or \
                  request.accept_mimetypes.best == 'application/json'

        if 'smtp_username' not in session:
            if is_ajax:
                return jsonify({'error': 'Please log in again'}), 401
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        # Check session timeout
        if 'login_time' in session:
            login_time = datetime.fromisoformat(session['login_time'])
            if datetime.now() - login_time > timedelta(seconds=config.SESSION_TIMEOUT):
                session.clear()
                if is_ajax:
                    return jsonify({'error': 'Session expired. Please log in again'}), 401
                flash('Session expired. Please log in again.', 'warning')
                return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def get_smtp_config():
    """Get SMTP configuration from session."""
    return {
        'host': session.get('smtp_host'),
        'port': int(session.get('smtp_port', 587)),
        'username': session.get('smtp_username'),
        'password': session.get('smtp_password'),
        'use_tls': session.get('smtp_use_tls', True),
        'use_ssl': session.get('smtp_use_ssl', False),
    }


def allowed_file(filename, allowed_extensions):
    """Check if file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


def get_file_extension(filename):
    """Get the lowercase file extension."""
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    return ''


def validate_image_magic_bytes(file_data, extension):
    """
    Validate that file content matches expected magic bytes for the extension.
    Returns (is_valid, error_message).
    """
    if extension not in config.IMAGE_MAGIC_BYTES:
        return False, f"Unknown image type: {extension}"

    magic_signatures = config.IMAGE_MAGIC_BYTES[extension]

    for signature in magic_signatures:
        if file_data[:len(signature)] == signature:
            # Special check for WebP: verify 'WEBP' at offset 8
            if extension == 'webp':
                if len(file_data) >= 12 and file_data[8:12] == b'WEBP':
                    return True, None
            else:
                return True, None

    return False, "File content doesn't match its extension (possible file corruption or mislabeled file)"


def validate_image_with_pil(file_data):
    """
    Use PIL to validate that the file is a valid, non-corrupted image.
    Returns (is_valid, error_message, image_info).
    """
    if not PIL_AVAILABLE:
        return True, None, {}  # Skip validation if PIL not available

    try:
        image = Image.open(io.BytesIO(file_data))
        # Force load the image data to catch truncated files
        image.load()

        image_info = {
            'format': image.format,
            'size': image.size,
            'mode': image.mode
        }

        # Check for reasonable dimensions (prevent decompression bombs)
        width, height = image.size
        if width > 10000 or height > 10000:
            return False, f"Image dimensions too large ({width}x{height}). Maximum is 10000x10000.", None

        # Check for reasonable pixel count
        if width * height > 50000000:  # 50 megapixels
            return False, "Image has too many pixels (over 50 megapixels)", None

        return True, None, image_info

    except Exception as e:
        return False, f"Invalid or corrupted image file: {str(e)}", None


def check_disk_space():
    """
    Check if there's enough disk space for uploads.
    Returns (has_space, free_mb).
    """
    try:
        total, used, free = shutil.disk_usage(config.IMAGE_FOLDER)
        free_mb = free // (1024 * 1024)
        return free_mb >= config.MIN_DISK_SPACE_MB, free_mb
    except Exception as e:
        logger.warning(f"Could not check disk space: {e}")
        return True, -1  # Assume OK if we can't check


def generate_unique_filename(original_filename):
    """
    Generate a unique filename using UUID to prevent collisions.
    Format: YYYYMMDD_HHMMSS_<uuid8>_<original_name>
    """
    safe_name = secure_filename(original_filename)
    if not safe_name:
        safe_name = "image"

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_id = uuid.uuid4().hex[:8]  # 8 character unique ID

    return f"{timestamp}_{unique_id}_{safe_name}"


# ============================================================================
# Routes - Authentication
# ============================================================================

@app.route('/', methods=['GET'])
def index():
    """Redirect to dashboard or login."""
    if 'smtp_username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login with SMTP credentials."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        host = request.form.get('host', '').strip()
        port = request.form.get('port', '587').strip()
        use_tls = request.form.get('use_tls') == 'on'
        use_ssl = request.form.get('use_ssl') == 'on'

        # Validate inputs
        if not all([email, password, host]):
            flash('Please fill in all required fields.', 'error')
            return render_template('login.html')

        try:
            port_int = int(port)
        except ValueError:
            flash('Port must be a number.', 'error')
            return render_template('login.html')

        # Test SMTP connection
        success, message = test_smtp_connection(
            host, port_int, email, password, use_tls, use_ssl
        )

        if success:
            # Store credentials in session
            session['smtp_host'] = host
            session['smtp_port'] = port_int
            session['smtp_username'] = email
            session['smtp_password'] = password
            session['smtp_use_tls'] = use_tls
            session['smtp_use_ssl'] = use_ssl
            session['login_time'] = datetime.now().isoformat()

            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash(message, 'error')
            return render_template('login.html',
                                   email=email, host=host, port=port)

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Log out and clear session."""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/diagnose', methods=['GET', 'POST'])
def diagnose():
    """Test all SMTP configurations to find what works."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        host = request.form.get('host', '').strip()

        if not all([email, password, host]):
            return jsonify({'error': 'Please fill in all fields'}), 400

        results = test_all_configurations(host, email, password)
        return jsonify({'results': results})

    # GET request - show the diagnostic page
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>SMTP Diagnostic Tool</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input { width: 100%; padding: 10px; font-size: 16px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
            button { background: #667eea; color: white; padding: 12px 24px; border: none; border-radius: 4px; font-size: 16px; cursor: pointer; }
            button:hover { background: #5a6fd6; }
            button:disabled { background: #ccc; }
            .results { margin-top: 30px; }
            .result { padding: 15px; margin: 10px 0; border-radius: 4px; }
            .success { background: #d4edda; border: 1px solid #c3e6cb; }
            .failure { background: #f8d7da; border: 1px solid #f5c6cb; }
            .testing { background: #fff3cd; border: 1px solid #ffeeba; }
            h1 { color: #333; }
            .config { font-weight: bold; }
            .message { color: #666; font-size: 14px; margin-top: 5px; }
            .loading { text-align: center; padding: 20px; }
        </style>
    </head>
    <body>
        <h1>SMTP Diagnostic Tool</h1>
        <p>This tool tests all common SMTP port/encryption combinations to find what works with your mail server.</p>

        <form id="diagnoseForm">
            <div class="form-group">
                <label>Email Address</label>
                <input type="email" name="email" required placeholder="you@company.com">
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" required>
            </div>
            <div class="form-group">
                <label>SMTP Server</label>
                <input type="text" name="host" required placeholder="mail.company.com">
            </div>
            <button type="submit" id="submitBtn">Test All Configurations</button>
        </form>

        <div class="results" id="results"></div>

        <script>
            document.getElementById('diagnoseForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                const btn = document.getElementById('submitBtn');
                const resultsDiv = document.getElementById('results');

                btn.disabled = true;
                btn.textContent = 'Testing (this takes about 2-3 minutes)...';
                resultsDiv.innerHTML = '<div class="loading">Testing 8 different configurations... Please wait.</div>';

                const formData = new FormData(this);

                try {
                    const response = await fetch('/diagnose', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await response.json();

                    if (data.error) {
                        resultsDiv.innerHTML = '<div class="result failure">' + data.error + '</div>';
                    } else {
                        let html = '<h2>Results:</h2>';
                        let anySuccess = false;

                        for (const r of data.results) {
                            const statusClass = r.success ? 'success' : 'failure';
                            const statusText = r.success ? 'SUCCESS' : 'FAILED';
                            if (r.success) anySuccess = true;

                            html += `<div class="result ${statusClass}">
                                <div class="config">${statusText}: ${r.description}</div>
                                <div class="message">${r.message}</div>
                            </div>`;
                        }

                        if (!anySuccess) {
                            html += '<div class="result failure"><strong>No working configuration found.</strong> The mail server may only support port 25 which is blocked by cloud providers.</div>';
                        }

                        resultsDiv.innerHTML = html;
                    }
                } catch (err) {
                    resultsDiv.innerHTML = '<div class="result failure">Error: ' + err.message + '</div>';
                }

                btn.disabled = false;
                btn.textContent = 'Test All Configurations';
            });
        </script>
    </body>
    </html>
    '''


# ============================================================================
# Routes - Dashboard
# ============================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard showing recent campaigns and templates."""
    campaigns = db.get_all_campaigns()
    templates = db.get_all_templates()
    return render_template('dashboard.html',
                           campaigns=campaigns,
                           templates=templates,
                           user_email=session.get('smtp_username'))


# ============================================================================
# Routes - Templates
# ============================================================================

@app.route('/templates')
@login_required
def templates_list():
    """List all saved templates."""
    templates = db.get_all_templates()
    return render_template('templates.html', templates=templates)


@app.route('/templates/new', methods=['GET', 'POST'])
@login_required
def template_new():
    """Create a new template."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        subject = request.form.get('subject', '').strip()
        html_content = request.form.get('html_content', '')

        if not name or not subject:
            flash('Template name and subject are required.', 'error')
            return render_template('template_edit.html',
                                   template=None,
                                   name=name,
                                   subject=subject,
                                   html_content=html_content)

        template_id = db.create_template(name, subject, html_content)
        flash('Template saved successfully!', 'success')
        return redirect(url_for('templates_list'))

    return render_template('template_edit.html', template=None)


@app.route('/templates/<int:template_id>/edit', methods=['GET', 'POST'])
@login_required
def template_edit(template_id):
    """Edit an existing template."""
    template = db.get_template(template_id)
    if not template:
        flash('Template not found.', 'error')
        return redirect(url_for('templates_list'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        subject = request.form.get('subject', '').strip()
        html_content = request.form.get('html_content', '')

        if not name or not subject:
            flash('Template name and subject are required.', 'error')
            return render_template('template_edit.html',
                                   template=template,
                                   name=name,
                                   subject=subject,
                                   html_content=html_content)

        db.update_template(template_id, name, subject, html_content)
        flash('Template updated successfully!', 'success')
        return redirect(url_for('templates_list'))

    return render_template('template_edit.html', template=template)


@app.route('/templates/<int:template_id>/delete', methods=['POST'])
@login_required
def template_delete(template_id):
    """Delete a template."""
    db.delete_template(template_id)
    flash('Template deleted.', 'info')
    return redirect(url_for('templates_list'))


# ============================================================================
# Routes - Compose & Send
# ============================================================================

@app.route('/compose', methods=['GET', 'POST'])
@login_required
def compose():
    """Compose a new email campaign."""
    templates = db.get_all_templates()

    # Check if starting from a template
    template_id = request.args.get('template_id')
    selected_template = None
    if template_id:
        selected_template = db.get_template(int(template_id))

    return render_template('compose.html',
                           templates=templates,
                           selected_template=selected_template)


@app.route('/compose/preview', methods=['POST'])
@login_required
def compose_preview():
    """Preview email with sample data."""
    html_content = request.form.get('html_content', '')
    # Replace placeholder with sample name
    preview_html = html_content.replace('{{name}}', 'Sample Recipient')
    return jsonify({'html': preview_html})


@app.route('/compose/send', methods=['POST'])
@login_required
def compose_send():
    """Parse CSV and send emails."""
    campaign_name = request.form.get('campaign_name', '').strip()
    subject = request.form.get('subject', '').strip()
    html_content = request.form.get('html_content', '')
    save_template = request.form.get('save_template') == 'on'
    template_name = request.form.get('template_name', '').strip()

    # Validate required fields
    if not campaign_name or not subject:
        flash('Campaign name and subject are required.', 'error')
        return redirect(url_for('compose'))

    # Handle CSV file
    if 'csv_file' not in request.files:
        flash('Please upload a CSV file with recipients.', 'error')
        return redirect(url_for('compose'))

    csv_file = request.files['csv_file']
    if csv_file.filename == '':
        flash('Please select a CSV file.', 'error')
        return redirect(url_for('compose'))

    if not allowed_file(csv_file.filename, config.ALLOWED_CSV_EXTENSIONS):
        flash('Please upload a valid CSV file.', 'error')
        return redirect(url_for('compose'))

    # Parse CSV
    try:
        csv_content = csv_file.read().decode('utf-8')
        df = pd.read_csv(io.StringIO(csv_content))
        df.columns = df.columns.str.strip().str.lower()

        # Validate required column
        if 'email' not in df.columns:
            flash('CSV must have an "Email" column.', 'error')
            return redirect(url_for('compose'))

        # Clean and prepare recipients
        recipients = []
        for _, row in df.iterrows():
            email = str(row.get('email', '')).strip()
            if not email or email == 'nan':
                continue

            name = str(row.get('name', '')).strip()
            if name == 'nan':
                name = ''
            company = str(row.get('company', '')).strip()
            if company == 'nan':
                company = ''

            recipients.append({
                'email': email,
                'name': name,
                'company': company
            })

        if not recipients:
            flash('No valid email addresses found in CSV.', 'error')
            return redirect(url_for('compose'))

    except Exception as e:
        flash(f'Error parsing CSV: {str(e)}', 'error')
        return redirect(url_for('compose'))

    # Save template if requested
    template_id = None
    if save_template and template_name:
        template_id = db.create_template(template_name, subject, html_content)

    # Create campaign
    campaign_id = db.create_campaign(campaign_name, subject, template_id)
    db.add_recipients(campaign_id, recipients)
    db.update_campaign_stats(campaign_id, total=len(recipients), status='sending')

    # Get recipients with IDs from database
    db_recipients = db.get_campaign_recipients(campaign_id)
    recipients_with_ids = [
        {
            'id': r['id'],
            'email': r['email'],
            'display_name': r['display_name']
        }
        for r in db_recipients
    ]

    # Progress callback to update database
    def update_progress(recipient_id, status, error):
        db.update_recipient_status(recipient_id, status, error)

    # Send emails
    smtp_config = get_smtp_config()
    results = send_emails(
        smtp_config,
        recipients_with_ids,
        subject,
        html_content,
        update_progress
    )

    # Update campaign stats
    db.update_campaign_stats(
        campaign_id,
        sent=results['sent_count'],
        failed=results['failed_count'],
        status='completed'
    )

    flash(f'Campaign complete: {results["sent_count"]} sent, {results["failed_count"]} failed.',
          'success' if results['failed_count'] == 0 else 'warning')
    return redirect(url_for('campaign_results', campaign_id=campaign_id))


# ============================================================================
# Routes - Campaign Results
# ============================================================================

@app.route('/campaigns/<int:campaign_id>')
@login_required
def campaign_results(campaign_id):
    """View results for a specific campaign."""
    campaign = db.get_campaign(campaign_id)
    if not campaign:
        flash('Campaign not found.', 'error')
        return redirect(url_for('dashboard'))

    recipients = db.get_campaign_recipients(campaign_id)
    return render_template('results.html',
                           campaign=campaign,
                           recipients=recipients)


# ============================================================================
# Routes - Image Upload
# ============================================================================

@app.route('/upload/image', methods=['POST'])
@login_required
def upload_image():
    """
    Handle image upload from Quill editor with comprehensive validation and error handling.

    Validation steps:
    1. Check file presence in request
    2. Check filename is not empty
    3. Check file extension is allowed
    4. Check file size is within limits
    5. Check disk space availability
    6. Validate file content (magic bytes)
    7. Validate image with PIL (if available)
    8. Save file with error handling

    Returns JSON with 'url' on success or 'error' on failure.
    """
    try:
        # Step 1: Check file presence
        if 'image' not in request.files:
            logger.warning("Upload attempt with no image file in request")
            return jsonify({
                'error': 'No image file provided',
                'code': 'NO_FILE'
            }), 400

        file = request.files['image']

        # Step 2: Check filename
        if file.filename == '':
            logger.warning("Upload attempt with empty filename")
            return jsonify({
                'error': 'No file selected',
                'code': 'EMPTY_FILENAME'
            }), 400

        # Step 3: Check extension
        extension = get_file_extension(file.filename)
        if not allowed_file(file.filename, config.ALLOWED_IMAGE_EXTENSIONS):
            allowed = ', '.join(config.ALLOWED_IMAGE_EXTENSIONS)
            logger.warning(f"Upload attempt with invalid extension: {extension}")
            return jsonify({
                'error': f'Invalid file type. Allowed types: {allowed}',
                'code': 'INVALID_TYPE',
                'allowed_types': list(config.ALLOWED_IMAGE_EXTENSIONS)
            }), 400

        # Step 4: Read file content and check size
        file_data = file.read()
        file_size = len(file_data)

        if file_size == 0:
            logger.warning("Upload attempt with empty file")
            return jsonify({
                'error': 'File is empty',
                'code': 'EMPTY_FILE'
            }), 400

        if file_size > config.MAX_IMAGE_SIZE:
            max_mb = config.MAX_IMAGE_SIZE / (1024 * 1024)
            file_mb = file_size / (1024 * 1024)
            logger.warning(f"Upload attempt with oversized file: {file_mb:.1f}MB")
            return jsonify({
                'error': f'File too large ({file_mb:.1f}MB). Maximum size is {max_mb:.0f}MB',
                'code': 'FILE_TOO_LARGE',
                'max_size_mb': max_mb,
                'file_size_mb': round(file_mb, 1)
            }), 400

        # Step 5: Check disk space
        has_space, free_mb = check_disk_space()
        if not has_space:
            logger.error(f"Insufficient disk space: {free_mb}MB free")
            return jsonify({
                'error': 'Server storage is full. Please try again later.',
                'code': 'DISK_FULL',
                'retry': True  # Client can retry later
            }), 507  # 507 Insufficient Storage

        # Step 6: Validate magic bytes
        is_valid, error_msg = validate_image_magic_bytes(file_data, extension)
        if not is_valid:
            logger.warning(f"Magic byte validation failed for {file.filename}: {error_msg}")
            return jsonify({
                'error': error_msg,
                'code': 'INVALID_CONTENT'
            }), 400

        # Step 7: Validate with PIL
        is_valid, error_msg, image_info = validate_image_with_pil(file_data)
        if not is_valid:
            logger.warning(f"PIL validation failed for {file.filename}: {error_msg}")
            return jsonify({
                'error': error_msg,
                'code': 'INVALID_IMAGE'
            }), 400

        # Step 8: Generate unique filename and save
        filename = generate_unique_filename(file.filename)
        filepath = config.IMAGE_FOLDER / filename

        try:
            # Write file with explicit error handling
            with open(filepath, 'wb') as f:
                f.write(file_data)

            # Verify the file was written correctly
            if not filepath.exists():
                raise IOError("File was not created")

            saved_size = filepath.stat().st_size
            if saved_size != file_size:
                filepath.unlink()  # Clean up incomplete file
                raise IOError(f"File size mismatch: expected {file_size}, got {saved_size}")

            logger.info(f"Successfully uploaded image: {filename} ({file_size} bytes)")

            # Return success with URL
            image_url = url_for('uploaded_image', filename=filename)
            return jsonify({
                'url': image_url,
                'filename': filename,
                'size': file_size,
                'dimensions': image_info.get('size') if image_info else None
            })

        except PermissionError as e:
            logger.error(f"Permission denied saving file: {e}")
            return jsonify({
                'error': 'Server cannot save files. Please contact support.',
                'code': 'PERMISSION_DENIED',
                'retry': False
            }), 500

        except IOError as e:
            logger.error(f"IO error saving file: {e}")
            # Clean up partial file if it exists
            if filepath.exists():
                try:
                    filepath.unlink()
                except Exception:
                    pass
            return jsonify({
                'error': 'Failed to save file. Please try again.',
                'code': 'SAVE_FAILED',
                'retry': True
            }), 500

    except Exception as e:
        # Catch-all for unexpected errors
        logger.exception(f"Unexpected error in upload_image: {e}")
        return jsonify({
            'error': 'An unexpected error occurred. Please try again.',
            'code': 'UNKNOWN_ERROR',
            'retry': True
        }), 500


@app.route('/uploads/images/<filename>')
def uploaded_image(filename):
    """Serve uploaded images."""
    return send_from_directory(config.IMAGE_FOLDER, filename)


# ============================================================================
# API Routes
# ============================================================================

@app.route('/api/template/<int:template_id>')
@login_required
def api_get_template(template_id):
    """Get template data as JSON."""
    template = db.get_template(template_id)
    if not template:
        return jsonify({'error': 'Template not found'}), 404
    return jsonify({
        'id': template['id'],
        'name': template['name'],
        'subject': template['subject'],
        'html_content': template['html_content']
    })


# ============================================================================
# Error handlers
# ============================================================================

@app.errorhandler(413)
def too_large(e):
    flash('File is too large. Maximum size is 16MB.', 'error')
    return redirect(request.url)


# ============================================================================
# Run
# ============================================================================

if __name__ == '__main__':
    # Ensure database is initialized
    db.init_db()

    # Use port 5001 by default (5000 conflicts with Mac AirPlay)
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    print(f"\n✓ Email Tool is running!")
    print(f"✓ Open your browser to: http://localhost:{port}\n")

    app.run(debug=debug, host='0.0.0.0', port=port)
