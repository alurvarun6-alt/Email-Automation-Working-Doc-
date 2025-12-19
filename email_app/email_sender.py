import smtplib
import ssl
import base64
import hashlib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from pathlib import Path
import re
from html import unescape
from config import IMAGE_FOLDER


def strip_html_tags(html_content):
    """Convert HTML to plain text for fallback."""
    # Remove style and script tags with content
    text = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Replace <br> and </p> with newlines
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    # Remove all other tags
    text = re.sub(r'<[^>]+>', '', text)
    # Unescape HTML entities
    text = unescape(text)
    # Clean up whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()


def find_base64_images(html_content):
    """Find all base64 data URL images in HTML."""
    # Match src="data:image/...;base64,..." pattern
    pattern = r'src=["\']data:image/([^;]+);base64,([^"\']+)["\']'
    matches = re.findall(pattern, html_content)
    # Return list of (image_type, base64_data, unique_id)
    results = []
    for i, (img_type, b64_data) in enumerate(matches):
        # Create a unique ID based on content hash
        content_hash = hashlib.md5(b64_data[:100].encode()).hexdigest()[:8]
        unique_id = f"img{i}_{content_hash}.{img_type}"
        results.append({
            'type': img_type,
            'data': b64_data,
            'cid': unique_id
        })
    return results


def find_file_images(html_content):
    """Find all file-based image references in HTML."""
    # Match src="/uploads/images/filename.ext" pattern
    pattern = r'src=["\']/?uploads/images/([^"\']+)["\']'
    matches = re.findall(pattern, html_content)
    return list(set(matches))


def prepare_html_with_cid(html_content, base64_images):
    """Replace base64 data URLs with Content-ID references."""
    processed_html = html_content
    for img in base64_images:
        # Replace the data URL with cid: reference
        pattern = rf'src=["\']data:image/{re.escape(img["type"])};base64,{re.escape(img["data"])}["\']'
        replacement = f'src="cid:{img["cid"]}"'
        processed_html = re.sub(pattern, replacement, processed_html)
    return processed_html


def prepare_html_for_sending(html_content, file_images):
    """Replace file image URLs with Content-ID references for embedding."""
    processed_html = html_content
    for image_filename in file_images:
        # Replace the URL with cid: reference
        pattern = rf'src=["\']/?uploads/images/{re.escape(image_filename)}["\']'
        replacement = f'src="cid:{image_filename}"'
        processed_html = re.sub(pattern, replacement, processed_html)
    return processed_html


def build_email_message(recipient, subject, html_template, sender_email, base64_images=None, file_images=None):
    """Build a MIME email message for a recipient."""
    email_addr = recipient['email']
    display_name = recipient['display_name']

    # Personalize the HTML content
    personalized_html = html_template.replace('{{name}}', display_name)

    # Create the message structure
    message = MIMEMultipart('related')
    message['Subject'] = subject
    message['From'] = sender_email
    message['To'] = email_addr

    # Create alternative container for plain/HTML versions
    alternative = MIMEMultipart('alternative')
    message.attach(alternative)

    # Plain text version
    plain_text = strip_html_tags(personalized_html)
    alternative.attach(MIMEText(plain_text, 'plain', 'utf-8'))

    # HTML version
    alternative.attach(MIMEText(personalized_html, 'html', 'utf-8'))

    # Attach base64 images as CID embedded images
    if base64_images:
        for img in base64_images:
            try:
                # Decode base64 data
                image_data = base64.b64decode(img['data'])
                image_type = img['type'] if img['type'] != 'jpg' else 'jpeg'

                image_part = MIMEImage(image_data, _subtype=image_type)
                image_part.add_header('Content-ID', f'<{img["cid"]}>')
                image_part.add_header('Content-Disposition', 'inline', filename=img['cid'])
                message.attach(image_part)
            except Exception as e:
                print(f"Error attaching image: {e}")

    # Attach file-based images
    if file_images:
        for image_filename in file_images:
            image_path = IMAGE_FOLDER / image_filename
            if image_path.exists():
                with open(image_path, 'rb') as img_file:
                    ext = image_path.suffix.lower()
                    image_type = {
                        '.jpg': 'jpeg',
                        '.jpeg': 'jpeg',
                        '.png': 'png',
                        '.gif': 'gif',
                        '.webp': 'webp'
                    }.get(ext, 'jpeg')

                    image_part = MIMEImage(img_file.read(), _subtype=image_type)
                    image_part.add_header('Content-ID', f'<{image_filename}>')
                    image_part.add_header('Content-Disposition', 'inline', filename=image_filename)
                    message.attach(image_part)

    return message


def test_smtp_connection(host, port, username, password, use_tls=True, use_ssl=False):
    """Test SMTP connection with provided credentials."""
    try:
        if use_ssl:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(host, port, context=context, timeout=20)
        else:
            server = smtplib.SMTP(host, port, timeout=20)
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()

        server.login(username, password)
        server.quit()
        return True, "Connection successful"
    except smtplib.SMTPAuthenticationError as e:
        return False, f"Authentication failed: {str(e)}"
    except smtplib.SMTPConnectError as e:
        return False, f"Could not connect to {host}:{port}: {str(e)}"
    except smtplib.SMTPNotSupportedError as e:
        return False, f"Server doesn't support this feature: {str(e)}"
    except ssl.SSLError as e:
        return False, f"SSL/TLS error: {str(e)}"
    except TimeoutError:
        return False, f"Connection timed out (port {port} may be blocked)"
    except ConnectionRefusedError:
        return False, f"Connection refused on port {port}"
    except OSError as e:
        if 'timed out' in str(e).lower():
            return False, f"Connection timed out (port {port} may be blocked)"
        return False, f"Network error: {str(e)}"
    except Exception as e:
        return False, f"Error: {type(e).__name__}: {str(e)}"


def test_all_configurations(host, username, password):
    """Test all common SMTP configurations and return results."""
    configurations = [
        # (port, use_tls, use_ssl, description)
        (587, True, False, "Port 587 + STARTTLS (standard)"),
        (587, False, False, "Port 587 plain (no encryption)"),
        (465, False, True, "Port 465 + SSL (legacy secure)"),
        (25, False, False, "Port 25 plain (often blocked)"),
        (25, True, False, "Port 25 + STARTTLS"),
        (2525, True, False, "Port 2525 + STARTTLS (alternative)"),
        (2525, False, False, "Port 2525 plain"),
        (26, False, False, "Port 26 plain (alternative to 25)"),
    ]

    results = []
    for port, use_tls, use_ssl, description in configurations:
        success, message = test_smtp_connection(host, port, username, password, use_tls, use_ssl)
        results.append({
            'port': port,
            'use_tls': use_tls,
            'use_ssl': use_ssl,
            'description': description,
            'success': success,
            'message': message
        })

    return results


def send_emails(smtp_config, recipients, subject, html_content, progress_callback=None):
    """
    Send emails to all recipients.

    Args:
        smtp_config: dict with host, port, username, password, use_tls, use_ssl
        recipients: list of recipient dicts with email, display_name
        subject: email subject line
        html_content: HTML template with {{name}} placeholder
        progress_callback: optional function to call with (recipient_id, status, error)

    Returns:
        dict with sent_count, failed_count, and results list
    """
    results = {
        'sent_count': 0,
        'failed_count': 0,
        'results': []
    }

    # Find base64 images and convert to CID references
    base64_images = find_base64_images(html_content)
    prepared_html = prepare_html_with_cid(html_content, base64_images)

    # Also handle any file-based images
    file_images = find_file_images(prepared_html)
    prepared_html = prepare_html_for_sending(prepared_html, file_images)

    try:
        # Establish SMTP connection
        if smtp_config.get('use_ssl'):
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(
                smtp_config['host'],
                smtp_config['port'],
                context=context,
                timeout=30
            )
        else:
            server = smtplib.SMTP(
                smtp_config['host'],
                smtp_config['port'],
                timeout=30
            )
            server.ehlo()
            if smtp_config.get('use_tls', True):
                server.starttls()
                server.ehlo()

        server.login(smtp_config['username'], smtp_config['password'])

        # Send to each recipient
        for recipient in recipients:
            recipient_result = {
                'id': recipient.get('id'),
                'email': recipient['email'],
                'display_name': recipient['display_name'],
                'status': 'pending',
                'error': None
            }

            try:
                message = build_email_message(
                    recipient,
                    subject,
                    prepared_html,
                    smtp_config['username'],
                    base64_images=base64_images,
                    file_images=file_images
                )
                server.sendmail(
                    smtp_config['username'],
                    [recipient['email']],
                    message.as_string()
                )
                recipient_result['status'] = 'sent'
                results['sent_count'] += 1

            except Exception as e:
                recipient_result['status'] = 'failed'
                recipient_result['error'] = str(e)
                results['failed_count'] += 1

            results['results'].append(recipient_result)

            # Call progress callback if provided
            if progress_callback and recipient.get('id'):
                progress_callback(
                    recipient['id'],
                    recipient_result['status'],
                    recipient_result['error']
                )

        server.quit()

    except Exception as e:
        # If connection fails, mark all remaining as failed
        error_msg = f"SMTP connection error: {str(e)}"
        for recipient in recipients:
            if not any(r['email'] == recipient['email'] for r in results['results']):
                results['results'].append({
                    'id': recipient.get('id'),
                    'email': recipient['email'],
                    'display_name': recipient['display_name'],
                    'status': 'failed',
                    'error': error_msg
                })
                results['failed_count'] += 1

                if progress_callback and recipient.get('id'):
                    progress_callback(recipient['id'], 'failed', error_msg)

    return results
