# Railway Deployment Guide for Python Apps

## Lessons Learned

This guide documents what works for deploying Python apps on Railway (as of December 2024).

---

## Required Files at Root Level

Railway needs these files **at the repository root** (not in a subdirectory):

### 1. `requirements.txt`
```
Flask>=3.0.0
pandas>=2.2.0
gunicorn>=21.2.0
```

**Important:**
- Use `>=` instead of `==` for version flexibility
- Railway uses Python 3.13 by default - make sure packages support it
- pandas 2.1.x does NOT work with Python 3.13, use 2.2.0+

### 2. `Procfile`
```
web: cd your_app_folder && gunicorn app:app --bind 0.0.0.0:$PORT
```

**Important:**
- Must bind to `$PORT` (Railway sets this automatically)
- Use `cd` if your app is in a subdirectory

---

## What Doesn't Work

| Approach | Problem |
|----------|---------|
| `requirements.txt` only in subdirectory | Railway can't detect Python |
| `nixpacks.toml` | Railway switched to Railpack, ignores this |
| `railway.json` with custom build commands | Often ignored by Railpack |
| Pinned old pandas versions (2.1.x) | Incompatible with Python 3.13 |

---

## Deployment Checklist

- [ ] `requirements.txt` at repo root
- [ ] `Procfile` at repo root
- [ ] All package versions compatible with Python 3.13
- [ ] App binds to `$PORT` environment variable
- [ ] Set `SECRET_KEY` environment variable in Railway dashboard

---

## Environment Variables to Set

In Railway dashboard → Your Project → Variables:

| Variable | Purpose | Example |
|----------|---------|---------|
| `SECRET_KEY` | Flask session security | Click "Generate" or use random string |
| `FLASK_DEBUG` | Enable debug mode | `false` for production |

---

## Accessing Your Deployed App

1. Go to Railway dashboard
2. Click your project
3. Click "Settings" tab
4. Under "Domains", click "Generate Domain" (or add custom domain)
5. Your app is live at `https://your-app-name.up.railway.app`
