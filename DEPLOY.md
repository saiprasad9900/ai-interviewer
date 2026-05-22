# Deploy ARIA via GitHub

**Recommended (easiest):** one app on [Streamlit Community Cloud](https://share.streamlit.io) — the backend runs inside the same app automatically.

| Part | Host | Free tier |
|------|------|-----------|
| **Full app** (Streamlit + API) | [Streamlit Cloud](https://share.streamlit.io) | Yes |
| **Backend only** (optional) | [Render](https://render.com) | Yes |

Repo: **https://github.com/saiprasad9900/ai-interviewer**

---

## Step 1 — Push code to GitHub

### 1a. Create a new repository on GitHub

1. Go to https://github.com/new  
2. Name it e.g. `ai-interviewer`  
3. **Do not** add README, .gitignore, or license (this project already has them)  
4. Click **Create repository**

### 1b. Push from your PC (PowerShell)

```powershell
cd "c:\Users\dell\OneDrive\Projects\ai_interviewer"

$git = "C:\Program Files\Git\bin\git.exe"

& $git init
& $git add .
& $git commit -m "Initial commit: AI interview agent with Groq and virtual interviewer"

# Replace YOUR_USERNAME with your GitHub username
& $git branch -M main
& $git remote add origin https://github.com/YOUR_USERNAME/ai-interviewer.git
& $git push -u origin main
```

When prompted, sign in with GitHub (browser or personal access token).

> **Never commit `.env`** — it is in `.gitignore`. API keys go only in host dashboards.

---

## Step 2 — Deploy the backend (Render)

1. Sign in at https://render.com with **GitHub**  
2. **New +** → **Blueprint** (or **Web Service** → connect repo)  
3. Select your `ai-interviewer` repository  
4. Render reads `render.yaml` automatically  
5. Under **Environment**, add:
   - `GROQ_API_KEY` = your Groq key (`gsk_...`)  
6. Click **Deploy**  
7. When live, copy the URL, e.g. `https://ai-interviewer-api.onrender.com`  
8. Test: open `https://YOUR-API.onrender.com/health` → should show `{"status":"ok",...}`

Free tier may sleep after inactivity; first request can take ~30s to wake up.

---

## Step 3 — Deploy on Streamlit Cloud (one app, recommended)

1. Sign in at https://share.streamlit.io with **GitHub** (same account: `saiprasad9900`)  
2. **Create app** → Repository: `saiprasad9900/ai-interviewer`, Branch: `main`  
3. **Main file path**: `streamlit_app.py`  
4. **Secrets** (only Groq key required — backend is embedded):

```toml
GROQ_API_KEY = "gsk_your_key_here"
```

Use the **exact** key name `GROQ_API_KEY` (see `.streamlit/secrets.toml.example`).

- Do **not** set `USE_MOCK_LLM` (that forces demo mode).
- Do **not** set `API_BASE` unless you use a separate Render backend (Step 2).
- After saving secrets, click **Reboot app** (or wait for redeploy).

5. Click **Deploy**

Your public URL: `https://<app-name>.streamlit.app`

**Direct deploy link** (after signing in):  
https://share.streamlit.io/deploy?repository=saiprasad9900/ai-interviewer&branch=main&mainModule=streamlit_app.py

---

## Step 4 — Verify

1. Open the Streamlit URL  
2. Start an interview — ARIA should ask questions (Groq + TTS via backend)  
3. If you see “Cannot reach backend”, check `API_BASE` in Streamlit secrets matches the Render URL

---

## Updating after changes

```powershell
& $git add .
& $git commit -m "Describe your change"
& $git push
```

Render and Streamlit redeploy automatically from `main`.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Build fails on Streamlit | Ensure `requirements.txt` has no local-only packages failing on Linux |
| Backend 502 / slow start | Render free tier cold start; wait and retry |
| `demo_mode: true` on production | Set `GROQ_API_KEY` in Render environment |
| Avatar image missing | Unsplash image needs internet; app still works |

---

## Optional: only Streamlit (demo mode)

If you skip Render, set in Streamlit secrets:

```toml
USE_MOCK_LLM = "1"
```

Questions use built-in demo mode (no Groq). Voice/avatar still work for TTS if backend is not used — TTS requires the API, so deploy the backend for full features.
