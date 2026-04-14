import numpy as np
import cv2
import os
import urllib.request
from flask import Flask, render_template, request, send_file, redirect
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ── Config ───────────────────────────────────────────
UPLOAD_FOLDER    = "static/uploads"
OUTPUT_FOLDER    = "static/outputs"
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "bmp", "webp", "tiff", "tif"}

app.config["UPLOAD_FOLDER"]    = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"]    = OUTPUT_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ── Model Paths ──────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)

PROTOTXT = os.path.join(BASE_DIR, "model/colorization_deploy_v2.prototxt")
MODEL    = os.path.join(BASE_DIR, "model/colorization_release_v2.caffemodel")
POINTS   = os.path.join(BASE_DIR, "model/pts_in_hull.npy")

PROTO_URL  = "https://raw.githubusercontent.com/richzhang/colorization/refs/heads/caffe/colorization/models/colorization_deploy_v2.prototxt"
MODEL_URL  = "https://www.dropbox.com/s/dx0qvhhp5hbcx7z/colorization_release_v2.caffemodel?dl=1"
POINTS_URL = "https://raw.githubusercontent.com/richzhang/colorization/refs/heads/caffe/colorization/resources/pts_in_hull.npy"

# ── Auto Download ─────────────────────────────────────
def download_file(url, path):
    print(f"Downloading {os.path.basename(path)} …")
    urllib.request.urlretrieve(url, path)
    print("Done.")

os.makedirs("model", exist_ok=True)
download_file(PROTO_URL,  PROTOTXT)
download_file(MODEL_URL,  MODEL)
download_file(POINTS_URL, POINTS)

# ── Lazy Load Model ──────────────────────────────────
net = None

def load_model():
    global net

    if net is None:
        print("Loading model...")

        net = cv2.dnn.readNetFromCaffe(PROTOTXT, MODEL)
        pts = np.load(POINTS)

        class8 = net.getLayerId("class8_ab")
        conv8  = net.getLayerId("conv8_313_rh")

        pts = pts.transpose().reshape(2, 313, 1, 1)
        net.getLayer(class8).blobs = [pts.astype("float32")]
        net.getLayer(conv8).blobs  = [np.full([1, 313], 2.606, dtype="float32")]

        print("Model loaded ✅")

    return net

# ── Helpers ───────────────────────────────────────────
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def colorize(image_bgr):
    net = load_model()

    scaled = image_bgr.astype("float32") / 255.0
    lab = cv2.cvtColor(scaled, cv2.COLOR_BGR2LAB)

    resized = cv2.resize(lab, (224, 224))
    L_input = cv2.split(resized)[0]
    L_input -= 50

    net.setInput(cv2.dnn.blobFromImage(L_input))
    ab = net.forward()[0].transpose((1, 2, 0))

    ab = cv2.resize(ab, (image_bgr.shape[1], image_bgr.shape[0]))

    L_full = cv2.split(lab)[0]
    colorized = np.concatenate((L_full[:, :, np.newaxis], ab), axis=2)

    colorized = cv2.cvtColor(colorized, cv2.COLOR_LAB2BGR)
    colorized = np.clip(colorized, 0, 1)
    colorized = (255 * colorized).astype("uint8")

    return colorized

# ── Routes ────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("image")

        if not file or file.filename == "":
            return redirect("/")

        if not allowed_file(file.filename):
            return render_template("index.html", show_result=False,
                                   error="Unsupported file type")

        try:
            filename = secure_filename(file.filename)
            input_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(input_path)

            image = cv2.imread(input_path)
            if image is None:
                raise ValueError("Invalid image")

            # 🔥 Reduce size (prevents crash)
            h, w = image.shape[:2]
            max_dim = 512
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                image = cv2.resize(image, (int(w * scale), int(h * scale)))

            result = colorize(image)

            output_path = os.path.join(app.config["OUTPUT_FOLDER"], "result.jpg")
            cv2.imwrite(output_path, result)

            return render_template(
                "index.html",
                input_img="/" + input_path,
                output_img="/" + output_path,
                show_result=True
            )

        except Exception as e:
            print("ERROR:", e)
            return render_template("index.html", show_result=False,
                                   error="Processing failed. Try smaller image.")

    return render_template("index.html", show_result=False)

@app.route("/download")
def download():
    path = os.path.join(app.config["OUTPUT_FOLDER"], "result.jpg")
    if not os.path.exists(path):
        return redirect("/")
    return send_file(path, as_attachment=True)

@app.route("/clear")
def clear():
    for folder in [app.config["UPLOAD_FOLDER"], app.config["OUTPUT_FOLDER"]]:
        for f in os.listdir(folder):
            try:
                os.remove(os.path.join(folder, f))
            except:
                pass
    return redirect("/")

# ── Run ──────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)