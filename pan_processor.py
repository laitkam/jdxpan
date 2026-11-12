import os
from pathlib import Path

import fitz
import numpy as np
from PIL import Image, ImageOps

# Coordinates retained from the existing Jdx PAN Form Filler.
PHOTO_LEFT = fitz.Rect(16.5, 112.5, 110.5, 235.5)
PHOTO_RIGHT = fitz.Rect(484.5, 112.5, 578.5, 235.5)
DECLARATION_SIG = fitz.Rect(438, 730, 555, 775)

LEFT_SIGNATURE_CENTER_X = PHOTO_LEFT.x1 + 31
LEFT_SIGNATURE_CENTER_Y = PHOTO_LEFT.y0 + 54
LEFT_SIGNATURE_WIDTH_PT = 100
LEFT_SIGNATURE_ROTATION_DEG = 22

DECL_SIGNATURE_CENTER_X = 468
DECL_SIGNATURE_CENTER_Y = 770
DECL_SIGNATURE_WIDTH_PT = 100
DECL_SIGNATURE_ROTATION_DEG = -4

def prepare_photo(source, output):
    im = Image.open(source).convert("RGB")
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = max(0, min(h - side, int((h - side) * 0.30)))
    im = im.crop((left, top, left + side, top + side))
    im = ImageOps.fit(im, (213, 213), method=Image.Resampling.LANCZOS)
    for quality in range(92, 39, -3):
        im.save(output, "JPEG", quality=quality, optimize=True, dpi=(300, 300))
        if os.path.getsize(output) < 30 * 1024:
            break
    if os.path.getsize(output) >= 30 * 1024:
        raise RuntimeError("Could not compress photo below 30 KB.")
    return output

def crop_ink(source):
    im = Image.open(source).convert("RGB")
    arr = np.asarray(im)
    strength = 255 - np.min(arr, axis=2)
    ys, xs = np.where(strength > 35)
    if len(xs):
        pad = max(12, int(min(im.size) * 0.025))
        im = im.crop((max(0, int(xs.min())-pad),
                      max(0, int(ys.min())-pad),
                      min(im.width, int(xs.max())+pad+1),
                      min(im.height, int(ys.max())+pad+1)))
    return im

def signature_overlay(source):
    im = crop_ink(source)
    arr = np.asarray(im).astype(np.int16)
    darkness = 255 - np.min(arr, axis=2)
    alpha = np.clip((darkness - 22) * 1.45, 0, 255).astype(np.uint8)
    rgba = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
    rgba[:, :, :3] = np.clip(arr, 0, 255).astype(np.uint8)
    rgba[:, :, 3] = alpha
    return Image.fromarray(rgba, "RGBA")

def prepare_signature_jpeg(source, output):
    im = crop_ink(source)
    gray = ImageOps.autocontrast(ImageOps.grayscale(im))
    gray = gray.point(lambda p: 0 if p < 205 else 255, mode="1").convert("L")
    canvas = Image.new("L", (gray.width + 80, gray.height + 50), 255)
    canvas.paste(gray, (40, 25))
    if canvas.width > 1200:
        nh = round(canvas.height * 1200 / canvas.width)
        canvas = canvas.resize((1200, nh), Image.Resampling.LANCZOS)
    for quality in range(95, 39, -5):
        canvas.save(output, "JPEG", quality=quality, optimize=True, dpi=(600, 600))
        if os.path.getsize(output) < 60 * 1024:
            break
    if os.path.getsize(output) >= 60 * 1024:
        raise RuntimeError("Could not compress signature below 60 KB.")
    return output

def rotated_signature_png(sig, target_width_pt, angle, out_path):
    width_px = max(1, int(target_width_pt * 3))
    height_px = max(1, round(sig.height * width_px / sig.width))
    sig = sig.resize((width_px, height_px), Image.Resampling.LANCZOS)
    sig = sig.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    sig.save(out_path)
    return sig.width / 3.0, sig.height / 3.0

def insert_centered_signature(page, sig, center_x, center_y, width_pt, angle, temp_path):
    out_w, out_h = rotated_signature_png(sig, width_pt, angle, temp_path)
    rect = fitz.Rect(center_x - out_w/2, center_y - out_h/2,
                     center_x + out_w/2, center_y + out_h/2)
    page.insert_image(rect, filename=temp_path, keep_proportion=False, overlay=True)

def create_outputs(pdf_path, photo_path, signature_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    photo_out = os.path.join(output_dir, "PAN_Photo.jpg")
    signature_out = os.path.join(output_dir, "PAN_Signature.jpg")
    page1_out = os.path.join(output_dir, "PAN_Form_Page_1.jpg")
    page2_out = os.path.join(output_dir, "PAN_Form_Page_2.jpg")
    left_temp = os.path.join(output_dir, "_left_signature.png")
    decl_temp = os.path.join(output_dir, "_declaration_signature.png")

    prepare_photo(photo_path, photo_out)
    prepare_signature_jpeg(signature_path, signature_out)
    sig = signature_overlay(signature_path)

    doc = fitz.open(pdf_path)
    try:
        if len(doc) < 2:
            raise RuntimeError("Please select the two-page PAN application PDF.")
        page1 = doc[0]
        page1.insert_image(PHOTO_LEFT, filename=photo_out, keep_proportion=False, overlay=True)
        page1.insert_image(PHOTO_RIGHT, filename=photo_out, keep_proportion=False, overlay=True)
        insert_centered_signature(page1, sig, LEFT_SIGNATURE_CENTER_X, LEFT_SIGNATURE_CENTER_Y,
                                  LEFT_SIGNATURE_WIDTH_PT, LEFT_SIGNATURE_ROTATION_DEG, left_temp)

        page2 = doc[1]
        insert_centered_signature(page2, sig, DECL_SIGNATURE_CENTER_X, DECL_SIGNATURE_CENTER_Y,
                                  DECL_SIGNATURE_WIDTH_PT, DECL_SIGNATURE_ROTATION_DEG, decl_temp)

        # Render the completed pages at 300 DPI to JPEG.
        matrix = fitz.Matrix(300 / 72, 300 / 72)
        for index, output in ((0, page1_out), (1, page2_out)):
            pix = doc[index].get_pixmap(matrix=matrix, alpha=False, colorspace=fitz.csRGB)
            pix.save(output)
            # Ensure JPEG output rather than PNG; PyMuPDF saves PNG by default.
            with Image.open(output) as rendered:
                rendered.convert("RGB").save(output, "JPEG", quality=95, optimize=True, dpi=(300, 300))
    finally:
        doc.close()
        for temp in (left_temp, decl_temp):
            try:
                os.remove(temp)
            except OSError:
                pass

    return page1_out, page2_out, photo_out, signature_out
