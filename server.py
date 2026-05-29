from flask import Flask, request, jsonify, send_file
from openai import OpenAI
import base64
import os
import re
import time

app = Flask(__name__)

API_KEY = os.environ.get("OPENAI_API_KEY", "")
client = OpenAI(api_key=API_KEY) if API_KEY else None

DEFAULT_PROMPT = (
    "You are my automotive image generator. I will provide vehicle models one at a time.\n"
    "STEP 1 — REFERENCE FIRST (do this before every image): Before generating, briefly "
    "describe the real vehicle's defining visual features — grille shape and pattern, "
    "headlight design, body proportions, roofline (SUV vs. coupe/sloped), wheel style, "
    "and badge placement. If you have web access, look it up to confirm; if not, state "
    "the known factory design. Use this description as the blueprint so the rendered car "
    "accurately matches the real model. Then wait — show me the description and the image together.\n"
    "STEP 2 — GENERATE: Render the vehicle. Every image must match the EXACT SAME "
    "composition, framing, lighting, scale, and perspective as the FIRST generated image. "
    "Never change the visual style between vehicles. After each image, stop and wait. "
    'When I say "next," do Step 1 then Step 2 for the next car.\n'
    "MANDATORY CONSISTENCY RULES — NEVER CHANGE:\n"
    "• Vehicle centered in frame • Front 3/4 angle • Facing slightly left • Entire vehicle "
    "visible with identical spacing around the car in every image • Portrait 4:5 aspect ratio "
    "• Pure solid white background only • No floor • No shadows • No reflections • No gradients "
    "• No environment or scenery • Car windows fully opaque dark tinted black glass • Cool "
    "cinematic showroom lighting • Photorealistic ultra-high-resolution rendering • Sharp edges "
    "with clean cutout separation from background\n"
    "CRITICAL SCALE & FRAMING LOCK:\n"
    "The vehicle MUST occupy the EXACT SAME percentage of the frame as the previous image.\n"
    "DO NOT: • zoom in or out • change focal length • change camera distance • alter crop "
    "• alter perspective • alter wheel positioning • alter roof height within frame • alter "
    "tire-to-bottom spacing • alter spacing above vehicle • alter visual weight of vehicle in canvas\n"
    "The wheels, roofline, and body proportions must align consistently across all generated "
    "vehicles so the entire set looks like one professionally art-directed automotive campaign.\n"
    "Every new vehicle must match: • identical camera height • identical lens perspective "
    "• identical framing • identical vehicle scale • identical crop margins • identical "
    "lighting direction • identical angle\n"
    "The ONLY thing allowed to change between images is the actual vehicle model itself.\n"
    "Vehicle: {vehicle}"
)


def sanitize_filename(name):
    return re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')[:80]


@app.route("/")
def index():
    return send_file("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    if not client:
        return jsonify({"error": "OPENAI_API_KEY not configured on the server."}), 500

    data = request.json
    vehicle = data.get("vehicle", "").strip()
    if not vehicle:
        return jsonify({"error": "Missing vehicle name."}), 400

    prompt = DEFAULT_PROMPT.replace("{vehicle}", vehicle)

    try:
        result = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            n=1,
            size="1024x1536",
            quality="high",
        )

        image_b64 = result.data[0].b64_json
        filename = f"{sanitize_filename(vehicle)}_{int(time.time())}.png"

        return jsonify({
            "filename": filename,
            "image_data": image_b64,
            "vehicle": vehicle,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"Image generator running at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
