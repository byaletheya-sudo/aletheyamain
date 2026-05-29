from flask import Flask, request, jsonify, send_from_directory, send_file
from openai import OpenAI
import base64
import os
import re
import time

app = Flask(__name__)

GENERATED_DIR = os.path.join(os.path.dirname(__file__), "generated")
os.makedirs(GENERATED_DIR, exist_ok=True)

DEFAULT_PROMPT = """You are my automotive image generator. I will provide vehicle models one at a time.
STEP 1 — REFERENCE FIRST (do this before every image): Before generating, briefly describe the real vehicle's defining visual features — grille shape and pattern, headlight design, body proportions, roofline (SUV vs. coupe/sloped), wheel style, and badge placement. If you have web access, look it up to confirm; if not, state the known factory design. Use this description as the blueprint so the rendered car accurately matches the real model. Then wait — show me the description and the image together.
STEP 2 — GENERATE: Render the vehicle. Every image must match the EXACT SAME composition, framing, lighting, scale, and perspective as the FIRST generated image. Never change the visual style between vehicles. After each image, stop and wait. When I say "next," do Step 1 then Step 2 for the next car.
MANDATORY CONSISTENCY RULES — NEVER CHANGE:
• Vehicle centered in frame • Front 3/4 angle • Facing slightly left • Entire vehicle visible with identical spacing around the car in every image • Portrait 4:5 aspect ratio • Pure solid white background only • No floor • No shadows • No reflections • No gradients • No environment or scenery • Car windows fully opaque dark tinted black glass • Cool cinematic showroom lighting • Photorealistic ultra-high-resolution rendering • Sharp edges with clean cutout separation from background
CRITICAL SCALE & FRAMING LOCK:
The vehicle MUST occupy the EXACT SAME percentage of the frame as the previous image.
DO NOT: • zoom in or out • change focal length • change camera distance • alter crop • alter perspective • alter wheel positioning • alter roof height within frame • alter tire-to-bottom spacing • alter spacing above vehicle • alter visual weight of vehicle in canvas
The wheels, roofline, and body proportions must align consistently across all generated vehicles so the entire set looks like one professionally art-directed automotive campaign.
Every new vehicle must match: • identical camera height • identical lens perspective • identical framing • identical vehicle scale • identical crop margins • identical lighting direction • identical angle
The ONLY thing allowed to change between images is the actual vehicle model itself.
Vehicle: {vehicle}"""

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

    if prompt_template:
        prompt = prompt_template.replace("{vehicle}", vehicle)
    else:
        prompt = DEFAULT_PROMPT.replace("{vehicle}", vehicle)

    try:
        client = OpenAI(api_key=API_KEY)
        result = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            n=1,
            size="1024x1536",
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
