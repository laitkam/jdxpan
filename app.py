import os
import tempfile
import zipfile
from pathlib import Path

from flask import Flask, render_template, request, send_file, abort, after_this_request
from werkzeug.utils import secure_filename

from pan_processor import create_outputs

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB total request

ALLOWED_PDF = {".pdf"}
ALLOWED_IMAGES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/process")
def process():
    form = request.files.get("form_pdf")
    photo = request.files.get("photo")
    signature = request.files.get("signature")

    if not form or not photo or not signature:
        return render_template("index.html", error="Please select the PAN PDF, photo and signature."), 400

    if Path(form.filename or "").suffix.lower() not in ALLOWED_PDF:
        return render_template("index.html", error="The application form must be a PDF."), 400
    if Path(photo.filename or "").suffix.lower() not in ALLOWED_IMAGES:
        return render_template("index.html", error="The photo must be an image file."), 400
    if Path(signature.filename or "").suffix.lower() not in ALLOWED_IMAGES:
        return render_template("index.html", error="The signature must be an image file."), 400

    workdir = Path(tempfile.mkdtemp(prefix="jdxpan_"))
    try:
        form_path = workdir / ("form" + Path(secure_filename(form.filename)).suffix.lower())
        photo_path = workdir / ("photo" + Path(secure_filename(photo.filename)).suffix.lower())
        sign_path = workdir / ("signature" + Path(secure_filename(signature.filename)).suffix.lower())
        form.save(form_path)
        photo.save(photo_path)
        signature.save(sign_path)

        outputs = create_outputs(str(form_path), str(photo_path), str(sign_path), str(workdir / "output"))
        output_paths = [Path(p) for p in outputs]
        expected = ["PAN_Form_Page_1.jpg", "PAN_Form_Page_2.jpg", "PAN_Photo.jpg", "PAN_Signature.jpg"]
        for name in expected:
            if not (workdir / "output" / name).exists():
                raise RuntimeError("The processing engine did not create " + name)

        zip_path = workdir / "Jdx_PAN_Output.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in expected:
                zf.write(workdir / "output" / name, arcname=name)

        @after_this_request
        def cleanup(response):
            # Remove temporary customer files after the response has been sent.
            # send_file may stream from this path; cleanup is deferred to close.
            response.call_on_close(lambda: __import__("shutil").rmtree(workdir, ignore_errors=True))
            return response

        return send_file(zip_path, as_attachment=True, download_name="Jdx_PAN_Completed_Files.zip",
                         mimetype="application/zip")
    except Exception as exc:
        import shutil
        shutil.rmtree(workdir, ignore_errors=True)
        return render_template("index.html", error=f"Could not process the application: {exc}"), 400

@app.errorhandler(413)
def too_large(_error):
    return render_template("index.html", error="The selected files are too large. Maximum combined upload size is 20 MB."), 413

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
