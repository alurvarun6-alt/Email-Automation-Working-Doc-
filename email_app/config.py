import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent

# Database
DATABASE_PATH = BASE_DIR / 'email_automation.db'

# Upload folders
UPLOAD_FOLDER = BASE_DIR / 'uploads'
IMAGE_FOLDER = UPLOAD_FOLDER / 'images'

# Ensure folders exist
UPLOAD_FOLDER.mkdir(exist_ok=True)
IMAGE_FOLDER.mkdir(exist_ok=True)

# Allowed file extensions
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_CSV_EXTENSIONS = {'csv'}

# Image upload limits
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB per image
MIN_DISK_SPACE_MB = 100  # Minimum free disk space in MB

# Magic bytes for image validation (file signatures)
IMAGE_MAGIC_BYTES = {
    'png': [b'\x89PNG\r\n\x1a\n'],
    'jpg': [b'\xff\xd8\xff'],
    'jpeg': [b'\xff\xd8\xff'],
    'gif': [b'GIF87a', b'GIF89a'],
    'webp': [b'RIFF'],  # WebP files start with RIFF, then have WEBP at offset 8
}

# Flask secret key (change in production)
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Session timeout (in seconds) - 8 hours
SESSION_TIMEOUT = 8 * 60 * 60
