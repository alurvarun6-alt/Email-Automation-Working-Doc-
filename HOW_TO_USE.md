# Email Automation Tool - Setup Guide

## One-Time Setup (5 minutes)

### Step 1: Install Python

**Mac:**
1. Open Terminal (press Cmd + Space, type "Terminal", press Enter)
2. Copy and paste this command, then press Enter:
   ```
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
3. When that finishes, run:
   ```
   brew install python3
   ```

**Windows:**
1. Go to https://www.python.org/downloads/
2. Click "Download Python 3.x.x"
3. Run the installer
4. **IMPORTANT:** Check the box that says "Add Python to PATH"
5. Click "Install Now"
6. Restart your computer

### Step 2: Download the Tool

1. Download this folder to your computer
2. Put it somewhere easy to find (like your Desktop)

---

## Using the Tool

### Starting the Tool

**Mac:**
1. Double-click `Start_Email_Tool.command`
2. If asked "Are you sure you want to open it?", click "Open"
3. Your browser will open automatically

**Windows:**
1. Double-click `Start_Email_Tool.bat`
2. Your browser will open automatically

### Logging In

1. Enter your Wunderkind email (e.g., `yourname@wunderkind-pr.com`)
2. Enter your email password (same one you use to check email)
3. Click "Sign In"

### Sending Emails

1. Click "Compose" or "New Campaign"
2. Enter a campaign name (for your records)
3. Enter the email subject line
4. Write your email in the text editor
   - Use the toolbar to bold, italicize, add images, etc.
   - Type `{{name}}` where you want the recipient's name to appear
5. Upload your CSV file with recipients
6. Click "Send Emails"

### CSV File Format

Your CSV file should have these columns:
```
Name,Email,Company
John Smith,john@example.com,Example News
Jane Doe,jane@newspaper.com,Daily Times
,editor@magazine.com,Literary Magazine
```

- **Name** - Person's name (optional - if empty, Company will be used)
- **Email** - Email address (required)
- **Company** - Company name (optional - used if Name is empty)

### Stopping the Tool

Just close the black terminal/command window.

---

## Troubleshooting

### "Python is not installed"
Follow Step 1 above to install Python.

### "Connection timed out" or login fails
Make sure you're connected to the internet and your email/password are correct.

### Other issues
Contact your administrator with a screenshot of the error.
