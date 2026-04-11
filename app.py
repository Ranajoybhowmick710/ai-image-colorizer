import numpy as np
import cv2
import os
import urllib.request
from flask import Flask, render_template, request, send_file, redirect
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ── Model Paths ─────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)

PROTOTXT = os.path.join(BASE_DIR, "model/colorization_deploy_v2.prototxt")
MODEL    = os.path.join(BASE_DIR, "model/colorization_release_v2.caffemodel")
POINTS   = os.path.join(BASE_DIR, "model/pts_in_hull.npy")

# ── Auto Download ───────────────────────────────────
def download_file(url, path):
    if not os.path.exists(path):
        print(f"Downloading {path}...")
        urllib.request.urlretrieve(url, path)
        print("Download complete!")

# Model URLs
PROTO_URL  = "https://raw.githubusercontent.com/richzhang/colorization/master/models/colorization_deploy_v2.prototxt"
MODEL_URL  = "https://github.com/richzhang/colorization/releases/download/v1.0/colorization_release_v2.caffemodel"
POINTS_URL = "https://github.com/richzhang/colorization/raw/master/resources/pts_in_hull.npy"

# Ensure model folder exists
os.makedirs("model", exist_ok=True)

# Download if missing
download_file(PROTO_URL, PROTOTXT)
download_file(MODEL_URL, MODEL)
download_file(POINTS_URL, POINTS)

net = cv2.dnn.readNetFromCaffe(PROTOTXT, MODEL)
pts = np.load(POINTS)

class8 = net.getLayerId("class8_ab")
conv8  = net.getLayerId("conv8_313_rh")

pts = pts.transpose().reshape(2, 313, 1, 1)
net.getLayer(class8).blobs = [pts.astype("float32")]
net.getLayer(conv8).blobs  = [np.full([1, 313], 2.606, dtype="float32")]

# ── Helpers ──────────────────────────────────────────────────────────────────
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def colorize(image_bgr):
    """
    Pure model colorization — no saturation manipulation, no post-processing.
    The ab channels predicted by the network are used exactly as-is.
    """
    scaled = image_bgr.astype("float32") / 255.0
    lab    = cv2.cvtColor(scaled, cv2.COLOR_BGR2LAB)

    # Resize to the network's expected input size and extract L channel
    resized = cv2.resize(lab, (224, 224))
    L_input = cv2.split(resized)[0]
    L_input -= 50  # mean-centre as the model expects

    # Forward pass
    net.setInput(cv2.dnn.blobFromImage(L_input))
    ab = net.forward()[0].transpose((1, 2, 0))  # (H, W, 2)

    # Resize ab predictions back to the original image size
    ab = cv2.resize(ab, (image_bgr.shape[1], image_bgr.shape[0]))

    # Recombine with the original full-resolution L channel
    L_full    = cv2.split(lab)[0]
    colorized = np.concatenate((L_full[:, :, np.newaxis], ab), axis=2)

    # Convert back to BGR
    colorized = cv2.cvtColor(colorized, cv2.COLOR_LAB2BGR)
    colorized = np.clip(colorized, 0, 1)
    colorized = (255 * colorized).astype("uint8")

    return colorized


# ── Routes ───────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("image")
        if not file or file.filename == "":
            return redirect("/")
        if not allowed_file(file.filename):
            return render_template("index.html", show_result=False,
                                   error="Unsupported file type. Please upload a JPEG, PNG, BMP, WEBP, or TIFF image.")

        try:
            filename   = secure_filename(file.filename)
            input_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(input_path)

            image = cv2.imread(input_path)
            if image is None:
                raise ValueError("Could not decode image. The file may be corrupted.")

            # Resize very large images to keep inference fast
            h, w = image.shape[:2]
            max_dim = 1024
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                image = cv2.resize(image, (int(w * scale), int(h * scale)),
                                   interpolation=cv2.INTER_AREA)

            # Colorize with raw model output — no post-processing
            result = colorize(image)

            output_path = os.path.join(app.config["OUTPUT_FOLDER"], "result.jpg")
            cv2.imwrite(output_path, result, [cv2.IMWRITE_JPEG_QUALITY, 95])

            return render_template(
                "index.html",
                input_img="/" + input_path,
                output_img="/" + output_path,
                show_result=True,
            )

        except Exception as exc:
            return render_template("index.html", show_result=False,
                                   error=f"Processing failed: {str(exc)}")

    return render_template("index.html", show_result=False)


@app.route("/download")
def download():
    path = os.path.join(app.config["OUTPUT_FOLDER"], "result.jpg")
    if not os.path.exists(path):
        return redirect("/")
    return send_file(path, as_attachment=True, download_name="colorized_result.jpg")


@app.route("/clear")
def clear():
    for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
        for f in os.listdir(folder):
            try:
                os.remove(os.path.join(folder, f))
            except OSError:
                pass
    return redirect("/")


@app.errorhandler(413)
def too_large(_):
    return render_template("index.html", show_result=False,
                           error="File too large. Maximum upload size is 16 MB."), 413


if __name__ == "__main__":
    app.run(debug=True)