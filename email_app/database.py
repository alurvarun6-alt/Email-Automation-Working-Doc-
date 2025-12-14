import sqlite3
from datetime import datetime
from pathlib import Path
from config import DATABASE_PATH


def get_db_connection():
    """Create a database connection with row factory."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with required tables."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Templates table - stores reusable email templates
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subject TEXT NOT NULL,
            html_content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Campaigns table - stores each email sending campaign
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            template_id INTEGER,
            subject TEXT NOT NULL,
            total_recipients INTEGER DEFAULT 0,
            sent_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (template_id) REFERENCES templates (id)
        )
    ''')

    # Recipients table - stores individual recipient results
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recipients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            name TEXT,
            email TEXT NOT NULL,
            company TEXT,
            display_name TEXT,
            status TEXT DEFAULT 'pending',
            error_message TEXT,
            sent_at TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
        )
    ''')

    conn.commit()
    conn.close()


# Template CRUD operations
def create_template(name, subject, html_content):
    """Create a new email template."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO templates (name, subject, html_content) VALUES (?, ?, ?)',
        (name, subject, html_content)
    )
    template_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return template_id


def get_all_templates():
    """Get all templates ordered by most recent."""
    conn = get_db_connection()
    templates = conn.execute(
        'SELECT * FROM templates ORDER BY updated_at DESC'
    ).fetchall()
    conn.close()
    return templates


def get_template(template_id):
    """Get a specific template by ID."""
    conn = get_db_connection()
    template = conn.execute(
        'SELECT * FROM templates WHERE id = ?', (template_id,)
    ).fetchone()
    conn.close()
    return template


def update_template(template_id, name, subject, html_content):
    """Update an existing template."""
    conn = get_db_connection()
    conn.execute(
        '''UPDATE templates
           SET name = ?, subject = ?, html_content = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?''',
        (name, subject, html_content, template_id)
    )
    conn.commit()
    conn.close()


def delete_template(template_id):
    """Delete a template."""
    conn = get_db_connection()
    conn.execute('DELETE FROM templates WHERE id = ?', (template_id,))
    conn.commit()
    conn.close()


# Campaign CRUD operations
def create_campaign(name, subject, template_id=None):
    """Create a new campaign."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO campaigns (name, subject, template_id) VALUES (?, ?, ?)',
        (name, subject, template_id)
    )
    campaign_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return campaign_id


def get_all_campaigns():
    """Get all campaigns ordered by most recent."""
    conn = get_db_connection()
    campaigns = conn.execute(
        'SELECT * FROM campaigns ORDER BY created_at DESC'
    ).fetchall()
    conn.close()
    return campaigns


def get_campaign(campaign_id):
    """Get a specific campaign by ID."""
    conn = get_db_connection()
    campaign = conn.execute(
        'SELECT * FROM campaigns WHERE id = ?', (campaign_id,)
    ).fetchone()
    conn.close()
    return campaign


def update_campaign_stats(campaign_id, total=None, sent=None, failed=None, status=None):
    """Update campaign statistics."""
    conn = get_db_connection()
    updates = []
    values = []

    if total is not None:
        updates.append('total_recipients = ?')
        values.append(total)
    if sent is not None:
        updates.append('sent_count = ?')
        values.append(sent)
    if failed is not None:
        updates.append('failed_count = ?')
        values.append(failed)
    if status is not None:
        updates.append('status = ?')
        values.append(status)
        if status == 'completed':
            updates.append('completed_at = CURRENT_TIMESTAMP')

    if updates:
        values.append(campaign_id)
        conn.execute(
            f'UPDATE campaigns SET {", ".join(updates)} WHERE id = ?',
            values
        )
        conn.commit()
    conn.close()


# Recipient operations
def add_recipients(campaign_id, recipients_list):
    """Add multiple recipients to a campaign."""
    conn = get_db_connection()
    cursor = conn.cursor()

    for recipient in recipients_list:
        name = recipient.get('name', '').strip()
        email = recipient.get('email', '').strip()
        company = recipient.get('company', '').strip()

        # Determine display name: prefer name, fallback to company
        display_name = name if name else company if company else 'there'

        cursor.execute(
            '''INSERT INTO recipients (campaign_id, name, email, company, display_name)
               VALUES (?, ?, ?, ?, ?)''',
            (campaign_id, name, email, company, display_name)
        )

    conn.commit()
    conn.close()


def get_campaign_recipients(campaign_id):
    """Get all recipients for a campaign."""
    conn = get_db_connection()
    recipients = conn.execute(
        'SELECT * FROM recipients WHERE campaign_id = ? ORDER BY id',
        (campaign_id,)
    ).fetchall()
    conn.close()
    return recipients


def update_recipient_status(recipient_id, status, error_message=None):
    """Update a recipient's send status."""
    conn = get_db_connection()
    if status == 'sent':
        conn.execute(
            '''UPDATE recipients
               SET status = ?, sent_at = CURRENT_TIMESTAMP
               WHERE id = ?''',
            (status, recipient_id)
        )
    else:
        conn.execute(
            '''UPDATE recipients
               SET status = ?, error_message = ?
               WHERE id = ?''',
            (status, error_message, recipient_id)
        )
    conn.commit()
    conn.close()


# Initialize database when module is imported
init_db()
