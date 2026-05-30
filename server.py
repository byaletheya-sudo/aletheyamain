from flask import Flask, request, jsonify, send_from_directory, send_file, session, redirect
from openai import OpenAI
import base64
import os
import re
import json
import urllib.request
import urllib.parse
import urllib.error

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "nova-aletheya-3f9a2c7e-change-in-prod")

# Simple password gate for the whole app (page + API). Override via APP_PASSWORD env.
APP_PASSWORD = os.environ.get("APP_PASSWORD", "novaagents")


def login_page(message=""):
    msg = f'<p class="err">{message}</p>' if message else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>nova.byAletheya</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#05080d; color:#fff;
    min-height:100vh; display:flex; align-items:center; justify-content:center;
    background-image: radial-gradient(70% 50% at 50% 35%, rgba(52,118,222,.30), rgba(8,16,30,0) 70%); }}
  .card {{ width:340px; max-width:90vw; background:#101319; border:1px solid #232733; border-radius:16px; padding:34px 28px; text-align:center; box-shadow:0 30px 80px rgba(0,0,0,.5); }}
  .brand {{ font-size:1.5rem; font-weight:800; letter-spacing:-.5px; margin-bottom:4px; }}
  .brand span {{ color:#4a9eff; }}
  .sub {{ color:#6b7280; font-size:.72rem; letter-spacing:.12em; text-transform:uppercase; margin-bottom:24px; }}
  input {{ width:100%; background:#0a0d12; border:1px solid #2a2f3a; border-radius:9px; padding:13px 15px; color:#fff; font-size:.95rem; outline:none; }}
  input:focus {{ border-color:#4a9eff; }}
  button {{ width:100%; margin-top:12px; padding:13px; border:none; border-radius:9px; background:#3a8eef; color:#fff; font-weight:600; font-size:.95rem; cursor:pointer; }}
  button:hover {{ background:#327fe0; }}
  .err {{ color:#ff6b6b; font-size:.82rem; margin-bottom:12px; }}
</style></head>
<body>
  <form class="card" method="POST" action="/login">
    <div class="brand"><span>nova</span>.byAletheya</div>
    <div class="sub">nova.byaletheya.com</div>
    {msg}
    <input type="password" name="password" placeholder="Password" autofocus autocomplete="current-password">
    <button type="submit">Enter</button>
  </form>
</body></html>"""


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password", "") == APP_PASSWORD:
            session["ok"] = True
            return redirect("/")
        return login_page("Incorrect password — try again."), 401
    return login_page()


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.before_request
def require_login():
    if request.path == "/login":
        return None
    if session.get("ok"):
        return None
    return redirect("/login")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Saved cars live here. Set GENERATED_DIR to a persistent disk/volume path on the
# host so the gallery survives restarts & redeploys (the default app dir is ephemeral).
GENERATED_DIR = os.environ.get("GENERATED_DIR", "").strip() or os.path.join(BASE_DIR, "generated")
os.makedirs(GENERATED_DIR, exist_ok=True)


def load_api_key():
    # Prefer an environment variable (used in deployment); fall back to a local .env file.
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        return key
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENAI_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return ""


API_KEY = load_api_key()

# Vehicle Databases (vehicle image API) — set VDB_API_KEY in the host env to enable the TEST tool.
VDB_API_KEY = os.environ.get("VDB_API_KEY", "").strip()

# Art-directed render rules: locked framing/scale/lighting for a consistent campaign look,
# rendered on a TRANSPARENT background so each car drops cleanly onto the ad template.
RENDER_RULES = (
    "MANDATORY CONSISTENCY RULES — NEVER CHANGE:\n"
    "• Vehicle centered in frame • Front 3/4 angle • Facing slightly left • Entire vehicle "
    "visible with identical spacing around the car in every image • Landscape 3:2 wide aspect ratio "
    "• Fully transparent background (PNG alpha) — no background fill, no backdrop, no scenery "
    "• No floor • No shadows • No reflections • No gradients • No environment "
    "• Car windows fully opaque dark tinted black glass • Cool cinematic showroom lighting "
    "• Photorealistic ultra-high-resolution rendering • Sharp edges with clean cutout separation "
    "from the transparent background\n"
    "CRITICAL SCALE & FRAMING LOCK:\n"
    "The vehicle MUST occupy the EXACT SAME percentage of the frame in every image.\n"
    "DO NOT: • zoom in or out • change focal length • change camera distance • alter crop "
    "• alter perspective • alter wheel positioning • alter roof height within frame • alter "
    "tire-to-bottom spacing • alter spacing above vehicle • alter visual weight of vehicle in canvas\n"
    "The wheels, roofline, and body proportions must align consistently across all generated "
    "vehicles so the entire set looks like one professionally art-directed automotive campaign.\n"
    "Keep identical camera height, lens perspective, framing, vehicle scale, crop margins, "
    "lighting direction, and angle for every vehicle.\n"
    "Render the image only — no text, watermarks, or captions anywhere in the image."
)


def research_vehicle(client, vehicle, bodystyle):
    """Look up the real, current design of this exact model year on the web so the
    image model renders THIS year's car (not an outdated training-data version).
    Best-effort: returns "" on any failure so generation still proceeds."""
    query = (
        f"I need an accurate visual reference for the {vehicle}"
        + (f" ({bodystyle})" if bodystyle else "")
        + ".\n"
        "STEP 1: Search the web and determine which GENERATION of this model is sold BRAND-NEW for "
        "that exact model year. Identify the generation name / chassis code and the year that "
        "generation (or its facelift) was introduced. Many models were recently redesigned, and older "
        "generations dominate image search — you MUST use the CURRENT/NEWEST generation for this model "
        "year and IGNORE every previous generation, even if older photos are more common.\n"
        "STEP 2: In 130-170 words, describe ONLY the exterior of THAT current generation so an "
        "illustrator can draw it accurately. Start by stating the generation code and its years in "
        "production, then describe: front grille shape and pattern, headlight and daytime-running-light "
        "signature, front bumper and air intakes, overall body proportions and roofline, side character "
        "lines, wheel design, and badge placement. Explicitly call out what makes THIS generation look "
        "different from the previous one. Be factual and specific — no pricing, no interior, no fluff."
    )
    last_err = None
    for tool_type in ("web_search", "web_search_preview"):
        try:
            resp = client.responses.create(
                model="gpt-4.1",
                tools=[{"type": tool_type}],
                input=query,
            )
            text = (getattr(resp, "output_text", "") or "").strip()
            if text:
                return text
        except Exception as e:
            last_err = e
            continue
    if last_err:
        print(f"[research] skipped ({last_err})")
    return ""


def classify_error(e):
    """Turn an OpenAI/SDK exception into a clear, human reason + the raw detail.
    `fatal` means there's no point continuing a bulk run (key/quota/access issues)."""
    name = type(e).__name__
    status = getattr(e, "status_code", None)
    code = getattr(e, "code", None)
    detail = str(getattr(e, "message", "") or e)
    low = f"{code} {detail}".lower()

    if "insufficient_quota" in low or "exceeded your current quota" in low or "billing" in low:
        reason, fatal = ("You're out of OpenAI credits/quota — add billing or credits to the "
                         "OpenAI account.", True)
    elif status == 401 or name == "AuthenticationError" or "api key" in low:
        reason, fatal = ("Invalid or missing OpenAI API key on the server.", True)
    elif status == 403 or name == "PermissionDeniedError" or ("verified" in low and "organization" in low):
        reason, fatal = ("This OpenAI account can't use the image model yet (gpt-image-1 may "
                         "require organization verification).", True)
    elif status == 429 or name == "RateLimitError":
        reason, fatal = ("Hit the OpenAI rate limit — wait a moment and try again.", False)
    elif status == 400 or name == "BadRequestError":
        reason, fatal = ("Request was rejected (possibly content policy or an invalid prompt).", False)
    elif name in ("APIConnectionError", "APITimeoutError"):
        reason, fatal = ("Couldn't reach OpenAI (network/timeout) — check the connection and retry.", False)
    elif status and status >= 500:
        reason, fatal = ("OpenAI had a server error — try again shortly.", False)
    else:
        reason, fatal = ("Image generation failed.", False)

    return {"reason": reason, "detail": detail, "fatal": fatal,
            "code": code, "status": status or 500}


def build_image_prompt(vehicle, bodystyle, color, reference):
    head = f"Render a single studio product photo of this exact vehicle: {vehicle}.\n"
    if bodystyle:
        head += (f"Body style: {bodystyle} — match the silhouette, roofline, doors, and "
                 f"proportions to this body style.\n")
    head += f"Exterior paint color: {color or 'the standard factory color for this model'}.\n"
    if reference:
        head += ("\nAUTHORITATIVE REAL-WORLD REFERENCE (from current sources). Render the CURRENT/NEWEST "
                 "generation of this model for this model year EXACTLY as described — never an older "
                 f"generation, even if older designs are more familiar:\n{reference}\n")
    return head + "\n" + RENDER_RULES


def car_slug(vehicle, bodystyle, color):
    """Deterministic identity for a car image: same vehicle+body+color -> same file.
    Lowercased so matching is case-insensitive across platforms."""
    key = " ".join(p for p in (vehicle, bodystyle, color) if p).lower()
    return re.sub(r'[^\w\s-]', '', key).strip().replace(' ', '_')[:90]


@app.route("/")
def index():
    return send_file(os.path.join(BASE_DIR, "index.html"))


@app.route("/logo.png")
def logo():
    return send_file(os.path.join(BASE_DIR, "logo.png"))


@app.route("/background.png")
def background():
    return send_file(os.path.join(BASE_DIR, "background.png"))


@app.route("/sold-bg.png")
def sold_bg():
    return send_file(os.path.join(BASE_DIR, "sold-bg.png"))


@app.route("/nova-plate.png")
def nova_plate():
    return send_file(os.path.join(BASE_DIR, "nova-plate.png"))


@app.route("/status")
def status():
    return jsonify({"has_key": bool(API_KEY and API_KEY != "sk-your-key-here")})


@app.route("/generate", methods=["POST"])
def generate():
    data = request.json
    vehicle = data.get("vehicle", "").strip()
    bodystyle = data.get("bodystyle", "").strip()
    color = data.get("color", "").strip()
    prompt_template = data.get("prompt_template", "").strip()
    do_research = data.get("research", True)
    force = bool(data.get("force", False))

    if not API_KEY or API_KEY == "sk-your-key-here":
        return jsonify({"error": "OPENAI_API_KEY not configured on the server."}), 500

    if not vehicle:
        return jsonify({"error": "Missing vehicle name."}), 400

    # Deterministic identity: same vehicle + body style + color -> same file.
    filename = f"{car_slug(vehicle, bodystyle, color)}.png"
    filepath = os.path.join(GENERATED_DIR, filename)

    # FAIL-SAFE: if this exact car was already generated, reuse it (no API call).
    if not force and os.path.exists(filepath):
        return jsonify({
            "success": True,
            "filename": filename,
            "vehicle": vehicle,
            "already_existed": True,
        })

    try:
        client = OpenAI(api_key=API_KEY)

        # STEP 1 — look up the real, current design online (so a brand-new model year
        # is rendered correctly instead of an outdated training-data version).
        reference = research_vehicle(client, vehicle, bodystyle) if do_research else ""

        # STEP 2 — build the image prompt (optional custom override still supported).
        if prompt_template:
            prompt = (prompt_template
                      .replace("{vehicle}", vehicle)
                      .replace("{bodystyle}", bodystyle or "as per the actual production model")
                      .replace("{color}", color or "the standard factory color for this model"))
            if reference:
                prompt += ("\n\nAUTHORITATIVE REAL-WORLD REFERENCE (match this exact model year):\n"
                           + reference)
        else:
            prompt = build_image_prompt(vehicle, bodystyle, color, reference)

        result = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            n=1,
            size="1536x1024",
            quality="high",
            background="transparent",
            output_format="png",
        )

        image_b64 = result.data[0].b64_json
        image_bytes = base64.b64decode(image_b64)

        with open(filepath, "wb") as f:
            f.write(image_bytes)

        return jsonify({
            "success": True,
            "filename": filename,
            "vehicle": vehicle,
            "already_existed": False,
            "referenced": bool(reference),
            "reference": reference,
        })

    except Exception as e:
        info = classify_error(e)
        print(f"[generate] error: {info['reason']} | {info['detail']}")
        return jsonify({
            "error": info["detail"] or info["reason"],
            "reason": info["reason"],
            "fatal": info["fatal"],
            "code": info["code"],
        }), info["status"]


@app.route("/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(GENERATED_DIR, filename)


@app.route("/images")
def list_images():
    files = sorted(os.listdir(GENERATED_DIR), reverse=True)
    # exclude generated backgrounds (bg_*) from the car gallery
    files = [f for f in files if f.endswith(".png") and not f.startswith("bg_")]
    return jsonify(files)


BG_PROMPTS = {
    "studio": (
        "A premium empty studio backdrop for a vertical 9:16 poster. Deep navy-to-black "
        "gradient walls, a soft cool-blue glow rising from the bottom-center like stage "
        "lighting, a subtle glossy reflective floor along the bottom, faint sharp geometric "
        "panel seams on the side walls, dark, cinematic, high-end, minimal. Keep the upper-"
        "middle area darker and clear for overlaying content. Absolutely no text, no logos, "
        "no people, no cars, no products."
    ),
    "nova": (
        "A premium vertical 9:16 poster backdrop in a bold geometric brand style. Dark navy "
        "background with large angular triangular facets and paneling, crisp electric-blue "
        "edge glow and accents, a cool-blue light beam rising from the bottom-center, a subtle "
        "reflective floor, cinematic and modern. Keep the center clear and darker for overlaying "
        "content. Absolutely no text, no logos, no people, no cars, no products."
    ),
}


def bg_prompt(style):
    base = BG_PROMPTS.get(style, BG_PROMPTS["studio"])
    variants = ("", " cooler tones", " a tighter light beam", " a softer haze",
                " a wider glow", " deeper shadows", " faint volumetric fog", " a brighter floor reflection")
    return base + " Variation:" + variants[os.urandom(1)[0] % len(variants)] + "."


@app.route("/caption", methods=["POST"])
def caption():
    if not API_KEY or API_KEY == "sk-your-key-here":
        return jsonify({"error": "OPENAI_API_KEY not configured on the server."}), 500
    data = request.json or {}
    vehicle = data.get("vehicle", "").strip()
    badge = data.get("badge", "").strip()
    if not vehicle:
        return jsonify({"error": "Add a make/model first."}), 400
    try:
        client = OpenAI(api_key=API_KEY)
        prompt = (
            "Write a short, punchy Instagram caption for a luxury car dealership called Nova Auto.\n"
            f"Context: {badge or 'SOLD'} — {vehicle}.\n"
            "Tone: upscale, celebratory, confident, concise. 1-2 sentences, then a new line with "
            "4-7 relevant hashtags. Include 1-2 tasteful emojis. No quotation marks around the caption. "
            "Vary the wording each time and keep it authentic to a high-end dealership."
        )
        resp = client.responses.create(model="gpt-4.1-mini", input=prompt)
        text = (getattr(resp, "output_text", "") or "").strip()
        return jsonify({"success": True, "caption": text})
    except Exception as e:
        info = classify_error(e)
        print(f"[caption] error: {info['reason']} | {info['detail']}")
        return jsonify({"error": info["detail"] or info["reason"], "reason": info["reason"]}), info["status"]


@app.route("/vdb-image", methods=["POST"])
def vdb_image():
    """TEST tool: fetch the real factory photo from Vehicle Databases' vehicle image API
    (by year/make/model[/trim]) and proxy the first exterior image back as a data URL so
    the client can background-remove it without CORS issues."""
    if not VDB_API_KEY:
        return jsonify({"error": "VDB_API_KEY is not set on the server. Add it in Railway → Variables."}), 500
    data = request.json or {}
    year = str(data.get("year", "")).strip()
    make = data.get("make", "").strip()
    model = data.get("model", "").strip()
    trim = data.get("trim", "").strip()
    if not (year and make and model):
        return jsonify({"error": "Enter year, make, and model."}), 400

    def enc(s):
        return urllib.parse.quote(s, safe="")

    paths = []
    if trim:
        paths.append(f"/vehicle-media/v2/{enc(year)}/{enc(make)}/{enc(model)}/{enc(trim)}")
    paths.append(f"/vehicle-media/v2/{enc(year)}/{enc(make)}/{enc(model)}")   # fallback without trim

    last_err = None
    for p in paths:
        try:
            req = urllib.request.Request("https://api.vehicledatabases.com" + p,
                                         headers={"x-authkey": VDB_API_KEY})
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8", "ignore"))
            images = (body.get("data") or {}).get("images") or {}
            exterior = images.get("exterior") or []
            if not exterior:
                last_err = "no exterior images"
                continue
            img_url = exterior[0]
            ireq = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(ireq, timeout=30) as iresp:
                ctype = iresp.headers.get("Content-Type", "image/jpeg")
                img_bytes = iresp.read()
            b64 = base64.b64encode(img_bytes).decode()
            return jsonify({
                "success": True,
                "image_data": f"data:{ctype};base64,{b64}",
                "exterior": exterior,
                "used_trim": (p == paths[0] and bool(trim)),
            })
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return jsonify({"error": "Invalid Vehicle Databases API key.", "reason": "Invalid VDB key"}), 401
            last_err = f"HTTP {e.code}"
            continue
        except Exception as e:
            last_err = str(e)
            continue
    return jsonify({"error": f"No factory image found for that vehicle ({last_err or 'no records'})."}), 404


@app.route("/detect-plate", methods=["POST"])
def detect_plate():
    """Use a vision model to locate the rear license plate. Returns its 4 corners as
    fractions of width/height — we composite the real Nova plate there, so the model
    only DETECTS (never draws), avoiding any logo garbling."""
    if not API_KEY or API_KEY == "sk-your-key-here":
        return jsonify({"error": "OPENAI_API_KEY not configured on the server."}), 500
    image_data = (request.json or {}).get("image_data", "")
    if not image_data:
        return jsonify({"error": "Missing image."}), 400
    if "," not in image_data:
        image_data = "data:image/png;base64," + image_data
    try:
        client = OpenAI(api_key=API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": [
                {"type": "text", "text":
                    "Find the rear LICENSE PLATE in this car photo. Respond with ONLY strict JSON: "
                    '{"found": true|false, "corners": [[x,y],[x,y],[x,y],[x,y]]} where corners are the '
                    "plate's TOP-LEFT, TOP-RIGHT, BOTTOM-RIGHT, BOTTOM-LEFT as decimal fractions (0-1) of "
                    "image width and height. Tightly bound the plate itself (not the frame). If there is no "
                    "visible plate, return {\"found\": false}."},
                {"type": "image_url", "image_url": {"url": image_data}},
            ]}],
            response_format={"type": "json_object"},
            max_tokens=300,
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        return jsonify({"found": bool(data.get("found")), "corners": data.get("corners")})
    except Exception as e:
        info = classify_error(e)
        print(f"[detect-plate] error: {info['reason']} | {info['detail']}")
        return jsonify({"error": info["detail"] or info["reason"], "reason": info["reason"]}), info["status"]


@app.route("/plate-cover", methods=["POST"])
def plate_cover():
    """Masked inpaint: receive a photo + a mask (transparent where the agent brushed the
    plate) and ask gpt-image-1 to replace ONLY that area with a Nova dealer plate."""
    if not API_KEY or API_KEY == "sk-your-key-here":
        return jsonify({"error": "OPENAI_API_KEY not configured on the server."}), 500
    data = request.json or {}
    image_data = data.get("image_data", "")
    mask_data = data.get("mask_data", "")
    size = data.get("size", "1024x1024")
    if size not in ("1024x1024", "1536x1024", "1024x1536"):
        size = "1024x1024"
    if not image_data or not mask_data:
        return jsonify({"error": "Missing image or mask."}), 400

    def decode(d):
        return base64.b64decode(d.split(",", 1)[1] if "," in d else d)

    try:
        img_bytes = decode(image_data)
        mask_bytes = decode(mask_data)
        # the real Nova plate, sent as a REFERENCE image so GPT reproduces the actual
        # plate instead of inventing one from a text description
        with open(os.path.join(BASE_DIR, "nova-plate.png"), "rb") as f:
            plate_bytes = f.read()
        client = OpenAI(api_key=API_KEY)
        result = client.images.edit(
            model="gpt-image-1",
            image=[
                ("photo.png", img_bytes, "image/png"),
                ("nova-plate.png", plate_bytes, "image/png"),
            ],
            mask=("mask.png", mask_bytes, "image/png"),
            prompt=(
                "The FIRST image is a photo of a car. The SECOND image is the official Nova Auto dealer "
                "license plate. In the masked area of the FIRST image, place the Nova plate from the "
                "second image so it replaces the existing plate. Reproduce the Nova plate's logo, "
                "wordmark and layout faithfully, and match the car's plate position, angle, perspective, "
                "size, lighting and subtle reflections so it looks completely real and factory-mounted. "
                "Do NOT change anything else in the photo — keep the car, paint, background, reflections "
                "and lighting pixel-identical outside the masked area."
            ),
            size=size,
        )
        out_b64 = result.data[0].b64_json
        return jsonify({"success": True, "image_data": "data:image/png;base64," + out_b64})
    except Exception as e:
        info = classify_error(e)
        print(f"[plate] error: {info['reason']} | {info['detail']}")
        return jsonify({"error": info["detail"] or info["reason"], "reason": info["reason"]}), info["status"]


@app.route("/generate-background", methods=["POST"])
def generate_background():
    if not API_KEY or API_KEY == "sk-your-key-here":
        return jsonify({"error": "OPENAI_API_KEY not configured on the server."}), 500
    style = (request.json or {}).get("style", "studio")
    try:
        client = OpenAI(api_key=API_KEY)
        result = client.images.generate(
            model="gpt-image-1",
            prompt=bg_prompt(style),
            n=1,
            size="1024x1536",
            quality="high",
            output_format="png",
        )
        image_bytes = base64.b64decode(result.data[0].b64_json)
        filename = f"bg_{style}_{os.urandom(4).hex()}.png"
        with open(os.path.join(GENERATED_DIR, filename), "wb") as f:
            f.write(image_bytes)
        return jsonify({"success": True, "filename": filename})
    except Exception as e:
        info = classify_error(e)
        print(f"[background] error: {info['reason']} | {info['detail']}")
        return jsonify({"error": info["detail"] or info["reason"], "reason": info["reason"]}), info["status"]


@app.route("/delete", methods=["POST"])
def delete_image():
    name = (request.json or {}).get("filename", "")
    # path-safety: only allow deleting a plain .png inside GENERATED_DIR
    name = os.path.basename(name)
    if not name.endswith(".png"):
        return jsonify({"error": "Invalid filename."}), 400
    path = os.path.join(GENERATED_DIR, name)
    if os.path.exists(path):
        os.remove(path)
        return jsonify({"success": True, "deleted": name})
    return jsonify({"error": "File not found."}), 404


@app.route("/upload", methods=["POST"])
def upload_image():
    """Save a (background-removed) car image so it joins the gallery and persists."""
    data = request.json or {}
    image_data = data.get("image_data", "")
    vehicle = data.get("vehicle", "").strip()
    if not image_data:
        return jsonify({"error": "Missing image data."}), 400
    try:
        if "," in image_data:                      # strip a data: URL prefix if present
            image_data = image_data.split(",", 1)[1]
        image_bytes = base64.b64decode(image_data)
        base = car_slug(vehicle, "", "") or "uploaded_car"
        filename = f"{base}.png"
        with open(os.path.join(GENERATED_DIR, filename), "wb") as f:
            f.write(image_bytes)
        return jsonify({"success": True, "filename": filename})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    from waitress import serve
    port = int(os.environ.get("PORT", 5050))
    if not API_KEY or API_KEY == "sk-your-key-here":
        print("WARNING: No API key set. Set OPENAI_API_KEY (env) or add it to .env.")
    print(f"Image generator running at http://localhost:{port}")
    serve(app, host="0.0.0.0", port=port, channel_timeout=300)
