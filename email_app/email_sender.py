import smtplib
import ssl
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


def find_embedded_images(html_content):
    """Find all image references in HTML that need to be embedded."""
    # Match src="/uploads/images/filename.ext" pattern
    pattern = r'src=["\']/?uploads/images/([^"\']+)["\']'
    matches = re.findall(pattern, html_content)
    return list(set(matches))  # Remove duplicates


def prepare_html_for_sending(html_content, images_to_embed):
    """Replace image URLs with Content-ID references for embedding."""
    processed_html = html_content
    for image_filename in images_to_embed:
        # Replace the URL with cid: reference
        pattern = rf'src=["\']/?uploads/images/{re.escape(image_filename)}["\']'
        replacement = f'src="cid:{image_filename}"'
        processed_html = re.sub(pattern, replacement, processed_html)
    return processed_html


def build_email_message(recipient, subject, html_template, sender_email):
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

    # Find and attach embedded images
    images_to_embed = find_embedded_images(html_template)
    for image_filename in images_to_embed:
        image_path = IMAGE_FOLDER / image_filename
        if image_path.exists():
            with open(image_path, 'rb') as img_file:
                # Determine image type
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
            server = smtplib.SMTP_SSL(host, port, context=context, timeout=30)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()

        server.login(username, password)
        server.quit()
        return True, "Connection successful"
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed. Please check your email and password."
    except smtplib.SMTPConnectError:
        return False, f"Could not connect to {host}:{port}. Please check the server address."
    except TimeoutError:
        return False, f"Connection timed out on port {port}. Port 25 is often blocked by cloud hosts. Try port 587 with TLS enabled, or port 465 with SSL enabled."
    except Exception as e:
        if 'timed out' in str(e).lower():
            return False, f"Connection timed out on port {port}. Port 25 is often blocked by cloud hosts. Try port 587 with TLS enabled, or port 465 with SSL enabled."
        return False, f"Connection error: {str(e)}"


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

    # Find images and prepare HTML
    images_to_embed = find_embedded_images(html_content)
    prepared_html = prepare_html_for_sending(html_content, images_to_embed)

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
                    smtp_config['username']
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
