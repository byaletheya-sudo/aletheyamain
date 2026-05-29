from flask import Flask, request, jsonify, send_from_directory, send_file
from openai import OpenAI
import base64
import os
import re
import time

app = Flask(__name__)

GENERATED_DIR = os.path.join(os.path.dirname(__file__), "generated")
os.makedirs(GENERATED_DIR, exist_ok=True)

def load_api_key():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENAI_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return os.environ.get("OPENAI_API_KEY", "")

API_KEY = load_api_key()


def sanitize_filename(name):
    return re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')[:80]


@app.route("/")
def index():
    return send_file("index.html")


@app.route("/status")
def status():
    return jsonify({"has_key": bool(API_KEY and API_KEY != "sk-your-key-here")})


@app.route("/generate", methods=["POST"])
def generate():
    data = request.json
    vehicle = data.get("vehicle", "").strip()
    prompt_template = data.get("prompt_template", "").strip()

    if not API_KEY or API_KEY == "sk-your-key-here":
        return jsonify({"error": "No API key configured. Add your key to the .env file."}), 400

    if not vehicle:
        return jsonify({"error": "Missing vehicle name"}), 400

    prompt = prompt_template.replace("{vehicle}", vehicle) if prompt_template else (
        f"A professional, high-quality photo of a {vehicle}, "
        f"studio lighting, showroom setting, clean background, "
        f"front 3/4 angle, photorealistic"
    )

    try:
        client = OpenAI(api_key=API_KEY)
        result = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            n=1,
            size="1024x1024",
            quality="high",
        )

        image_b64 = result.data[0].b64_json
        image_bytes = base64.b64decode(image_b64)

        filename = f"{sanitize_filename(vehicle)}_{int(time.time())}.png"
        filepath = os.path.join(GENERATED_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(image_bytes)

        return jsonify({
            "success": True,
            "filename": filename,
            "vehicle": vehicle,
            "prompt": prompt,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(GENERATED_DIR, filename)


@app.route("/images")
def list_images():
    files = sorted(os.listdir(GENERATED_DIR), reverse=True)
    files = [f for f in files if f.endswith(".png")]
    return jsonify(files)


if __name__ == "__main__":
    if not API_KEY or API_KEY == "sk-your-key-here":
        print("WARNING: No API key set. Edit .env and add your OPENAI_API_KEY.")
    else:
        print(f"API key loaded: sk-...{API_KEY[-4:]}")
    print("Image generator running at http://localhost:5050")
    print(f"Images will be saved to: {GENERATED_DIR}")
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False)
