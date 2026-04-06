import io
import cv2
import numpy as np
from flask import Flask, request, jsonify, send_file
app = Flask(__name__)

MAX_SIZE = 10 * 1024 * 1024  # 10 MB


def decode_image(file_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("Cannot decode image")
    return img


def encode_image(img: np.ndarray, fmt: str = ".jpg") -> bytes:
    success, buf = cv2.imencode(fmt, img)
    if not success:
        raise ValueError("Cannot encode image")
    return buf.tobytes()


@app.route("/api/process", methods=["POST"])
def process():
    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400

    operation = request.form.get("operation", "")
    if operation not in ("detect_faces", "remove_bg", "find_edges"):
        return jsonify({"error": f"Unknown operation: {operation}"}), 400

    file = request.files["image"]
    data = file.read(MAX_SIZE + 1)
    if len(data) > MAX_SIZE:
        return jsonify({"error": "Image too large (max 10 MB)"}), 413

    try:
        img = decode_image(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if operation == "detect_faces":
        result, mime = op_detect_faces(img)
    elif operation == "remove_bg":
        result, mime = op_remove_bg(img)
    elif operation == "find_edges":
        result, mime = op_find_edges(img)

    return send_file(
        io.BytesIO(result),
        mimetype=mime,
        as_attachment=False,
        download_name="result.jpg" if mime == "image/jpeg" else "result.png",
    )


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def _get_cascade_path() -> str:
    """Return an ASCII-only path to the Haar cascade XML.

    On Windows, cv2.data.haarcascades may contain non-ASCII characters
    (e.g. a Cyrillic username), which OpenCV's FileStorage cannot open.
    We copy the file once to the backend directory and reuse the copy.
    """
    import os, shutil
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_haar_face.xml")
    if not os.path.exists(local):
        src = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        if not os.path.exists(src):
            raise FileNotFoundError("Haar cascade not found in OpenCV data dir")
        shutil.copy2(src, local)
    return local


def op_detect_faces(img: np.ndarray):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img

    face_cascade = cv2.CascadeClassifier(_get_cascade_path())
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30),
    )

    out = img.copy()
    if img.ndim == 2:
        out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)

    color = (0, 255, 80)  # bright green
    thickness = max(2, min(out.shape[:2]) // 150)
    for x, y, w, h in faces:
        cv2.rectangle(out, (x, y), (x + w, y + h), color, thickness)
        label = "Face"
        font_scale = max(0.5, min(out.shape[:2]) / 1000)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
        cv2.rectangle(out, (x, y - th - 6), (x + tw + 4, y), color, -1)
        cv2.putText(
            out, label, (x + 2, y - 4),
            cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), 1, cv2.LINE_AA
        )

    return encode_image(out, ".jpg"), "image/jpeg"


def op_remove_bg(img: np.ndarray):
    """Remove background using rembg."""
    try:
        from rembg import remove as rembg_remove
    except ImportError:
        return _remove_bg_grabcut(img)

    # Convert BGR -> RGB for rembg
    if img.ndim == 3 and img.shape[2] == 3:
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    elif img.ndim == 3 and img.shape[2] == 4:
        rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
    else:
        rgb = img

    import PIL.Image
    pil_img = PIL.Image.fromarray(rgb)
    result_pil = rembg_remove(pil_img)

    # Convert back to BGRA numpy
    result_np = np.array(result_pil)
    if result_np.shape[2] == 4:
        bgra = cv2.cvtColor(result_np, cv2.COLOR_RGBA2BGRA)
    else:
        bgra = cv2.cvtColor(result_np, cv2.COLOR_RGB2BGR)

    return encode_image(bgra, ".png"), "image/png"


def _remove_bg_grabcut(img: np.ndarray):
    """Fallback background removal using GrabCut."""
    h, w = img.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    margin = min(h, w) // 10
    rect = (margin, margin, w - 2 * margin, h - 2 * margin)
    cv2.grabCut(img, mask, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
    fg_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

    bgra = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = fg_mask
    return encode_image(bgra, ".png"), "image/png"


def op_find_edges(img: np.ndarray):
    """Apply Canny edge detection and overlay on the original."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Auto threshold via median
    median = np.median(blurred)
    sigma = 0.33
    lower = int(max(0, (1.0 - sigma) * median))
    upper = int(min(255, (1.0 + sigma) * median))
    edges = cv2.Canny(blurred, lower, upper)

    # Dilate slightly for visibility
    kernel = np.ones((2, 2), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)

    # Colorize edges (cyan) and blend with original
    out = img.copy() if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    overlay = np.zeros_like(out)
    overlay[edges > 0] = (255, 220, 0)  # cyan-yellow in BGR

    out = cv2.addWeighted(out, 0.6, overlay, 0.9, 0)
    return encode_image(out, ".jpg"), "image/jpeg"


if __name__ == "__main__":
    app.run(debug=True, port=5000)
