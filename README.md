# Jdx PAN Form Filler — Online version

This project converts the existing desktop workflow into a browser-based application.

## Output files

The app returns one ZIP containing:
- `PAN_Form_Page_1.jpg`
- `PAN_Form_Page_2.jpg`
- `PAN_Photo.jpg`
- `PAN_Signature.jpg`

The original automatic placement coordinates and image preparation rules are retained in `pan_processor.py`. The completed form pages are rendered at 300 DPI.

## Run locally

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Deploy online with GitHub + Render

1. Create a **private GitHub repository** (recommended, because this is an application handling sensitive PAN documents).
2. Upload all project files and folders. Do not upload real customer forms, photos or signatures.
3. On Render, choose **New + → Web Service** and connect the GitHub repository.
4. Render can detect `render.yaml`; otherwise set:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app --workers 1 --threads 4 --timeout 120`
5. Deploy. Render will provide a public `https://...onrender.com` URL. Anyone with the link can open the app; no login is configured.

## Important privacy and deployment notes

- This version has no login, as requested. Anyone with the URL can use it.
- Uploaded files are written to a temporary per-request folder and cleanup is requested after the download response closes.
- A hosting provider may retain infrastructure logs or temporary storage snapshots outside this application's control. Do not use this for real PAN documents until you have reviewed the host's privacy, retention and security terms.
- Set an appropriate upload-size limit and consider adding rate limiting before broad public use.
- The free hosting plan may sleep when idle, so the first request after inactivity can be slower.
