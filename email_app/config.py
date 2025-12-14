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

# Flask secret key (change in production)
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Session timeout (in seconds) - 8 hours
SESSION_TIMEOUT = 8 * 60 * 60
