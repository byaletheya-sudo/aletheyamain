from flask import Flask, request, jsonify, send_from_directory, send_file, session, redirect
from openai import OpenAI
import base64
import os
import re
import json
import hmac
import time
import secrets
import urllib.request
import urllib.parse
import urllib.error

app = Flask(__name__)

# Session signing key. NEVER hardcode a real one — this repo is public, and a known
# key lets anyone forge a "logged-in" cookie and skip the password entirely. Use the
# SECRET_KEY env var in production; otherwise fall back to a random per-process key
# (sessions simply won't survive a restart, which just means logging in again).
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# Harden the session cookie.
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,    # not readable by JS (an XSS can't steal the session)
    SESSION_COOKIE_SECURE=True,      # only sent over HTTPS (Railway/custom domains are HTTPS)
    SESSION_COOKIE_SAMESITE="Lax",   # basic CSRF mitigation
)

# Password gate for the whole app. Env-only in practice: the fallback is random, so
# the value that used to be committed here no longer opens the door. Set APP_PASSWORD
# in Railway → Variables.
APP_PASSWORD = os.environ.get("APP_PASSWORD") or secrets.token_urlsafe(24)
if not os.environ.get("APP_PASSWORD"):
    print("[security] APP_PASSWORD is not set — using a random password. Set it in Railway to log in.")

# Tiny in-memory brute-force throttle: max attempts per IP per window.
_LOGIN_FAILS = {}
_LOGIN_MAX = 8
_LOGIN_WINDOW = 300   # seconds


def _client_ip():
    xff = request.headers.get("X-Forwarded-For", "")
    return (xff.split(",")[0].strip() if xff else (request.remote_addr or "?"))


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
  .legal {{ margin-top:20px; padding-top:16px; border-top:1px solid #1c2029; font-size:.66rem; line-height:1.5; color:#5a6472; text-align:left; }}
  .legal b {{ color:#8a94a3; font-weight:700; }}
</style></head>
<body>
  <form class="card" method="POST" action="/login">
    <div class="brand"><span>nova</span>.byAletheya</div>
    <div class="sub">nova.byaletheya.com</div>
    {msg}
    <input type="password" name="password" placeholder="Password" autofocus autocomplete="current-password">
    <button type="submit">Enter</button>
    <p class="legal"><b>Confidential &amp; Proprietary.</b> This application and all concepts, designs, workflows, data, and content within are the exclusive property of <b>Nova Auto Pros</b> and are intended solely for authorized internal use by its personnel. Unauthorized access, use, copying, reproduction, distribution, or disclosure of any ideas or materials herein is strictly prohibited and may result in legal action.</p>
  </form>
</body></html>"""


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = _client_ip()
        cnt, t0 = _LOGIN_FAILS.get(ip, (0, time.time()))
        if time.time() - t0 > _LOGIN_WINDOW:        # reset the window
            cnt, t0 = 0, time.time()
        if cnt >= _LOGIN_MAX:                        # too many tries -> back off
            return login_page("Too many attempts — wait a few minutes and try again."), 429
        # constant-time compare avoids leaking the password via timing
        if hmac.compare_digest(request.form.get("password", ""), APP_PASSWORD):
            session.clear()                          # new session id on login (anti-fixation)
            session["ok"] = True
            _LOGIN_FAILS.pop(ip, None)
            return redirect("/")
        _LOGIN_FAILS[ip] = (cnt + 1, t0)
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


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"            # no MIME sniffing
    resp.headers["X-Frame-Options"] = "DENY"                       # no clickjacking/embedding
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return resp

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

# CarsXE (image source). Set CARSXE_API_KEY in the host env.
CARSXE_API_KEY = os.environ.get("CARSXE_API_KEY", "").strip()
_CARSXE_ALLOWED = set()     # image URLs CarsXE returned to us (the only ones we'll proxy)
_CARSXE_IMG_CACHE = {}      # vehicle -> image response, so repeats never re-hit CarsXE
_CARSXE_META_CACHE = {}     # vehicle -> colors + trims
_CARSXE_PROXY_CACHE = {}    # image url -> data URL
_CARSXE_CACHE_MAX = 150     # keep the last ~150 of each (FIFO)


def _cache_put(cache, key, val):
    if key in cache:
        return
    if len(cache) >= _CARSXE_CACHE_MAX:
        cache.pop(next(iter(cache)))   # evict oldest
    cache[key] = val

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


# Each tool has its own clean URL. They all serve the same single-page app; the
# client reads the path on load to open the right view (and pushState keeps the
# URL in sync as you switch tools). Deep-linkable and bookmarkable.
@app.route("/")
@app.route("/lease")
@app.route("/sold")
@app.route("/leasead-test")
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


@app.route("/bg-economy.png")
def bg_economy():
    return send_file(os.path.join(BASE_DIR, "bg-economy.png"))


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


def vdb_label(url):
    """Turn a photo URL into a readable color label (manufacturer-agnostic).
    Some makes (e.g. Mercedes) name the file by color — 'selenite-grey.jpg' —
    while others (e.g. BMW) use an opaque code — 'ext-34305F3031.jpg'. Return a
    clean name when there is one, else '' so the caller can number it instead."""
    seg = url.rstrip("/").split("/")[-1]
    seg = re.sub(r"\.\w+$", "", seg)                          # drop extension
    seg = re.sub(r"^manufaktur[-_]", "", seg, flags=re.I)     # MB prefix
    seg = seg.replace("-", " ").replace("_", " ").strip()
    seg = re.sub(r"^(ext(erior)?|int(erior)?)\s+", "", seg, flags=re.I).strip()  # drop ext/int tag
    if not seg or re.search(r"\d{3,}", seg):                  # code-like -> not a real name
        return ""
    return seg.title()


# --- forgiving make/model resolution (the catalog wants exact strings) ---
MAKE_ALIASES = {
    "mercedes": "Mercedes-Benz", "mercedes benz": "Mercedes-Benz", "merc": "Mercedes-Benz", "benz": "Mercedes-Benz",
    "chevy": "Chevrolet", "chevrolet": "Chevrolet", "vw": "Volkswagen", "volkswagon": "Volkswagen",
    "land rover": "Land Rover", "range rover": "Land Rover", "rover": "Land Rover",
    "alfa": "Alfa Romeo", "mini": "MINI", "mini cooper": "MINI", "rolls": "Rolls-Royce", "rolls royce": "Rolls-Royce",
}
MAKE_UPPER = {"bmw", "gmc", "ram", "gm"}


def norm_make(m):
    low = re.sub(r"\s+", " ", m.strip().lower())
    if low in MAKE_ALIASES:
        return MAKE_ALIASES[low]
    if low in MAKE_UPPER:
        return low.upper()
    return m.strip().title()


def dedup(seq):
    seen, out = set(), []
    for x in seq:
        k = x.lower()
        if x and k not in seen:
            seen.add(k); out.append(x)
    return out


def model_spellings(model):
    """Best-first spellings to try directly. As-typed first (the user usually
    enters it the way the catalog spells it — 'X5', 'K5', 'GLC 300'), then the
    spaced variant as a fallback for glued inputs like 'GLC300' -> 'GLC 300'.
    Capped at 2 so a direct lookup never costs more than two media calls."""
    m = model.strip()
    spaced = re.sub(r"([A-Za-z])(\d)", r"\1 \2", m)
    nospace = re.sub(r"\s+", "", m)
    return dedup([m, spaced, nospace])[:2]


def _vdb_get(path):
    req = urllib.request.Request("https://api.vehicledatabases.com" + path,
                                 headers={"x-authkey": VDB_API_KEY})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            code = getattr(r, "status", 200)
            raw = r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        code = e.code
        raw = e.read().decode("utf-8", "ignore")
    try:
        body = json.loads(raw)
    except Exception:
        body = {}
    return code, body, raw


# --- catalog-driven resolution (the proven approach) -----------------------
# The media API stores make/model/trim under its OWN canonical spellings, which
# rarely match what a user types. So instead of guessing spellings, we ask VDB
# for the exact list of valid values (its "options" endpoints), then snap the
# user's free text onto the closest entry in that real list — locally when it's
# obvious, GPT when it isn't. This is how the main Novauto app does it.
_VDB_OPT_CACHE = {}      # in-process cache so we don't re-buy the same option list
_VDB_COLOR_CACHE = {}    # exterior_colors (names + hex) per vehicle, cached
_VDB_RESULT_CACHE = {}   # full resolved lookups, so duplicate rows skip the network
_VDB_RESULT_MAX = 300    # bound memory (image data is base64) with simple FIFO eviction


def _result_key(year, make, model, trim, use_trim):
    """Normalized cache key so 'GLC300' and 'GLC 300' (etc.) share one entry."""
    return "|".join([year, _nrm(make), _nrm(model), _nrm(trim) if use_trim else "", "T" if use_trim else "F"])


def _result_cache_put(key, payload):
    if key in _VDB_RESULT_CACHE:
        return
    if len(_VDB_RESULT_CACHE) >= _VDB_RESULT_MAX:
        _VDB_RESULT_CACHE.pop(next(iter(_VDB_RESULT_CACHE)))   # evict oldest
    _VDB_RESULT_CACHE[key] = payload


def _vdb_options(path):
    """GET a vehicle-media options endpoint -> list of canonical strings (cached)."""
    if path in _VDB_OPT_CACHE:
        return _VDB_OPT_CACHE[path]
    try:
        code, body, raw = _vdb_get(path)
    except Exception:
        return []
    data = body.get("data") or []
    opts = [x.strip() for x in data if isinstance(x, str) and x.strip()]
    if opts:
        _VDB_OPT_CACHE[path] = opts   # only cache real hits (don't cache rate-limits)
    return opts


def _nrm(s):
    """Aggressive normalize for matching: lowercase, alphanumerics only."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _gpt_pick(user_text, options, kind="value"):
    """Let the model choose the single closest entry from a fixed list (enum-locked
    so it can't invent a value). Returns None if unavailable."""
    if not options or not API_KEY or API_KEY == "sk-your-key-here":
        return None
    try:
        client = OpenAI(api_key=API_KEY)
        schema = {
            "type": "object", "additionalProperties": False, "required": [kind],
            "properties": {kind: {
                "type": "string", "enum": options,
                "description": f"The {kind} from the list that best matches the input. "
                               "If there's no exact match, choose the closest by meaning or wording.",
            }},
        }
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "You are an automotive data analyst. Map the user's "
                 "vehicle description onto the single closest option from the allowed list. Always pick from the list."},
                {"role": "user", "content": f"Vehicle input: {user_text!r}\n"
                 f"Choose the {kind} that best matches, using only the allowed list."},
            ],
            response_format={"type": "json_schema",
                             "json_schema": {"name": "pick", "strict": True, "schema": schema}},
        )
        return json.loads(resp.choices[0].message.content).get(kind)
    except Exception:
        return None


def _resolve(user_text, options, kind="value"):
    """Snap free text onto the closest canonical option. Local match first
    (free, instant), GPT fallback for the genuinely ambiguous cases."""
    if not options:
        return None
    nu = _nrm(user_text)
    if not nu:
        return None
    # 1) exact (normalized) — "GLC300" == "GLC 300", "mercedes-benz" == "Mercedes-Benz"
    for o in options:
        if _nrm(o) == nu:
            return o
    # 2) containment — "GLC300" inside "GLC 300 4MATIC SUV"; prefer the most specific
    cont = [o for o in options if nu in _nrm(o) or _nrm(o) in nu]
    if len(cont) == 1:
        return cont[0]
    # 3) anything ambiguous (0 or >1 candidates) -> let GPT choose from the real list
    pool = cont if len(cont) > 1 else options
    return _gpt_pick(user_text, pool, kind) or (cont[0] if cont else None)


def _vdb_colors(year, make, model, trim):
    """Manufacturer exterior color names + hex (from advanced-vin-decode), cached.
    Lets the picker show real names/swatches even when a photo's filename is just
    an opaque code. Needs a trim; returns [] if unavailable."""
    if not trim:
        return []
    enc = lambda s: urllib.parse.quote(s, safe="")
    path = f"/advanced-vin-decode/v2/{enc(year)}/{enc(make)}/{enc(model)}/{enc(trim)}"
    if path in _VDB_COLOR_CACHE:
        return _VDB_COLOR_CACHE[path]
    try:
        code, body, raw = _vdb_get(path)
    except Exception:
        return []
    out = []
    for c in ((body.get("data") or {}).get("exterior_colors") or []):
        name = (c.get("description") or c.get("generic_name") or "").strip()
        if not name:
            continue
        out.append({
            "name": name.title() if name.islower() else name,
            "key": _nrm(name),
            "hex": (c.get("hex_value") or "").strip(),
        })
    if out:
        _VDB_COLOR_CACHE[path] = out
    return out


def _label_photos(photos, color_meta):
    """Build {url,label,hex} options. Real manufacturer name when the photo's
    filename slug matches a known color, else the readable filename, else
    'Color N'. (exterior/interior shots use coded filenames, so they fall
    through to numbering; per-color images carry real name slugs.)"""
    opts = []
    for i, u in enumerate(photos):
        fn = re.sub(r"\.\w+$", "", u.rstrip("/").split("/")[-1])
        fn = re.sub(r"^(ext|int|colors?)[-_]", "", fn, flags=re.I)
        key = _nrm(fn)
        match = None
        if key and not re.search(r"\d{3,}", fn):       # only name-like filenames can match
            for c in color_meta:
                if c["key"] and (c["key"] == key or key in c["key"] or c["key"] in key):
                    match = c
                    break
        if match:
            opts.append({"url": u, "label": match["name"], "hex": match["hex"]})
        else:
            opts.append({"url": u, "label": (vdb_label(u) or f"Color {i + 1}"), "hex": ""})
    return opts


@app.route("/vdb-proxy", methods=["POST"])
def vdb_proxy():
    """Proxy a specific Vehicle Databases image URL (so a chosen color is same-origin
    and can be background-removed)."""
    url = (request.json or {}).get("url", "").strip()
    if not url:
        return jsonify({"error": "Missing url."}), 400
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if not (host.endswith("digitaloceanspaces.com") or host.endswith("vehicledatabases.com")):
        return jsonify({"error": "URL not allowed."}), 400
    try:
        ireq = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(ireq, timeout=30) as r:
            ctype = r.headers.get("Content-Type", "image/jpeg")
            b = r.read()
        return jsonify({"success": True, "image_data": f"data:{ctype};base64," + base64.b64encode(b).decode()})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


def _carsxe_dataurl(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        ctype = r.headers.get("Content-Type", "image/png")
        b = r.read()
    return f"data:{ctype};base64," + base64.b64encode(b).decode()


def _rgb_to_hex(rgb):
    """'226,5,0' -> '#e20500'. Returns '' if it can't parse."""
    try:
        parts = [max(0, min(255, int(float(x)))) for x in str(rgb).split(",")[:3]]
        if len(parts) == 3:
            return "#%02x%02x%02x" % tuple(parts)
    except Exception:
        pass
    return ""


@app.route("/carsxe-meta", methods=["POST"])
def carsxe_meta():
    """CarsXE colors + trims for a vehicle (the /v1/ymm endpoint). Returns the
    exterior color list (name + hex) and the available trims, so we can rebuild
    the color picker and trim suggestions without Vehicle Databases."""
    if not CARSXE_API_KEY:
        return jsonify({"error": "CARSXE_API_KEY is not set on the server."}), 500
    data = request.json or {}
    make = data.get("make", "").strip()
    model = data.get("model", "").strip()
    year = str(data.get("year", "")).strip()
    trim = data.get("trim", "").strip()
    if not (make and model):
        return jsonify({"colors": [], "trims": []})
    mkey = "|".join([year, make.lower(), model.lower(), trim.lower()])
    cached = _CARSXE_META_CACHE.get(mkey)
    if cached is not None:
        return jsonify({**cached, "cached": True})
    params = {"key": CARSXE_API_KEY, "make": make, "model": model, "allTrimOptions": "1", "format": "json"}
    if year:
        params["year"] = year
    if trim:
        params["trim"] = trim
    url = "https://api.carsxe.com/v1/ymm?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as e:
        return jsonify({"colors": [], "trims": [], "note": f"meta lookup failed: {e}"})

    best = body.get("bestMatch") or {}
    ext = ((best.get("color") or {}).get("exterior")) or []
    colors = []
    for c in ext:
        name = (c.get("name") or "").strip()
        if name:
            colors.append({"name": name, "hex": _rgb_to_hex(c.get("rgb", ""))})

    trims = []
    for t in (body.get("trimOptions") or []):
        nm = t if isinstance(t, str) else (t.get("trim") or t.get("name") or "")
        nm = (nm or "").strip()
        if nm and nm not in trims:
            trims.append(nm)
    payload = {"colors": colors, "trims": trims}
    if colors or trims:
        _cache_put(_CARSXE_META_CACHE, mkey, payload)
    return jsonify(payload)


@app.route("/carsxe-image", methods=["POST"])
def carsxe_image():
    """TRIAL: pull a vehicle photo from CarsXE's /images endpoint (make/model based,
    transparent by default) so we can compare its image quality against Vehicle
    Databases. Returns the full set of results so the user can pick the best one."""
    if not CARSXE_API_KEY:
        return jsonify({"error": "CARSXE_API_KEY is not set on the server. Add it in Railway → Variables."}), 500
    data = request.json or {}
    make = data.get("make", "").strip()
    model = data.get("model", "").strip()
    year = str(data.get("year", "")).strip()
    trim = data.get("trim", "").strip()
    color = data.get("color", "").strip().lower()    # CarsXE expects a lowercase basic colour
    if not (make and model):
        return jsonify({"error": "Pick a make and model first."}), 400

    key = "|".join([year, make.lower(), model.lower(), trim.lower(), color])
    cached = _CARSXE_IMG_CACHE.get(key)
    if cached is not None:
        for o in cached.get("options", []):           # keep proxy allow-list warm
            _CARSXE_ALLOWED.add(o["url"])
        return jsonify({**cached, "cached": True})

    params = {"key": CARSXE_API_KEY, "make": make, "model": model,
              "transparent": "true", "size": "Large", "format": "json"}
    if year:
        params["year"] = year
    if trim:
        params["trim"] = trim
    if color:
        params["color"] = color
    url = "https://api.carsxe.com/images?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        return jsonify({"error": f"CarsXE error {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}"}), 502
    except Exception as e:
        return jsonify({"error": f"CarsXE request failed: {e}"}), 502

    imgs = [im for im in (body.get("images") or []) if im.get("link")]
    if not imgs:
        return jsonify({"found": False, "message": body.get("error") or "No images returned by CarsXE."})
    for im in imgs:
        _CARSXE_ALLOWED.add(im["link"])
    options = [{"url": im["link"], "thumb": im.get("thumbnailLink") or im["link"],
                "w": im.get("width"), "h": im.get("height"),
                "transparent": str(im.get("mime", "")).endswith("png")}
               for im in imgs]
    try:
        first = _carsxe_dataurl(imgs[0]["link"])
    except Exception as e:
        return jsonify({"error": f"Couldn't load the CarsXE image: {e}"}), 502
    payload = {"found": True, "success": True, "image_data": first,
               "image_url": imgs[0]["link"], "options": options}
    _cache_put(_CARSXE_IMG_CACHE, key, payload)
    return jsonify(payload)


@app.route("/carsxe-proxy", methods=["POST"])
def carsxe_proxy():
    """Proxy a specific CarsXE image (only URLs CarsXE itself returned — no open SSRF)."""
    url = (request.json or {}).get("url", "").strip()
    if url not in _CARSXE_ALLOWED:
        return jsonify({"error": "URL not allowed."}), 400
    cached = _CARSXE_PROXY_CACHE.get(url)
    if cached is not None:
        return jsonify({"success": True, "image_data": cached, "cached": True})
    try:
        d = _carsxe_dataurl(url)
        _cache_put(_CARSXE_PROXY_CACHE, url, d)
        return jsonify({"success": True, "image_data": d})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/bulk-parse", methods=["POST"])
def bulk_parse():
    """Smart bulk: an LLM turns ANY pasted text (list, email, spreadsheet dump)
    into structured ad rows the user can review and download."""
    if not API_KEY or API_KEY == "sk-your-key-here":
        return jsonify({"error": "OPENAI_API_KEY not configured on the server."}), 500
    text = (request.json or {}).get("text", "").strip()
    if not text:
        return jsonify({"error": "Paste some vehicles first."}), 400
    schema = {
        "type": "object", "additionalProperties": False, "required": ["rows"],
        "properties": {"rows": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["year", "make", "model", "trim", "deal_type", "monthly", "das", "down", "apr", "term", "badge"],
            "properties": {
                "year": {"type": "string"}, "make": {"type": "string"}, "model": {"type": "string"},
                "trim": {"type": "string"},
                "deal_type": {"type": "string", "enum": ["lease", "finance", "onepay"]},
                "monthly": {"type": "string"}, "das": {"type": "string"}, "down": {"type": "string"},
                "apr": {"type": "string"}, "term": {"type": "string"}, "badge": {"type": "string"},
            }}}},
    }
    system = (
        "You extract vehicle lease/finance offers from messy pasted text into ad rows. "
        "For each vehicle fill: year; make (FULL make, e.g. 'Mercedes-Benz', 'BMW'); model; trim; "
        "deal_type (lease | finance | onepay); monthly (monthly payment); das (due-at-signing, lease); "
        "down (down payment, finance); apr (finance APR percent); term (months); badge (promo label if any). "
        "Use '' for anything not present. Numbers only — no $, no commas. If it says one-pay/single-pay, "
        "deal_type=onepay and put the up-front total in das. Default deal_type=lease when unclear."
    )
    try:
        client = OpenAI(api_key=API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
            response_format={"type": "json_schema", "json_schema": {"name": "bulk", "strict": True, "schema": schema}},
        )
        rows = json.loads(resp.choices[0].message.content).get("rows", [])
        return jsonify({"rows": rows})
    except Exception as e:
        return jsonify({"error": f"Couldn't parse that: {e}"}), 502


@app.route("/remove-bg", methods=["POST"])
def remove_bg():
    """Deterministic background removal for studio/factory photos. The catalog
    cars sit on a near-white seamless backdrop, so we flood-fill the backdrop
    (only the region connected to the image border) to transparent and feather
    the edge. It never alters the car — pure pixel ops, no AI regeneration — so
    the factory photo comes back identical, just cut out."""
    data = request.json or {}
    src = (data.get("image_data") or "").strip()
    if not src:
        return jsonify({"error": "Missing image_data."}), 400
    try:
        import io
        import numpy as np
        from PIL import Image, ImageFilter
    except Exception as e:
        return jsonify({"error": f"Background remover not installed on server: {e}"}), 500
    try:
        raw = base64.b64decode(src.split(",", 1)[1] if "," in src else src)
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        arr = np.asarray(im).astype(np.int16)
        h, w = arr.shape[:2]

        # backdrop colour = median of the four corners (studio shots are uniform)
        c = 8
        corners = np.concatenate([
            arr[:c, :c].reshape(-1, 3), arr[:c, -c:].reshape(-1, 3),
            arr[-c:, :c].reshape(-1, 3), arr[-c:, -c:].reshape(-1, 3),
        ])
        bg = np.median(corners, axis=0)
        dist = np.sqrt(((arr - bg) ** 2).sum(axis=2))     # distance from backdrop colour
        tol = float(data.get("tol", 32))
        near = dist < tol

        # keep only the backdrop *connected to the border*, so white parts of the
        # car (headlights, a white body) are never punched out. Morphological
        # reconstruction by iterative 4-neighbour dilation, masked by `near`.
        reach = np.zeros((h, w), bool)
        reach[0, :] |= near[0, :]; reach[-1, :] |= near[-1, :]
        reach[:, 0] |= near[:, 0]; reach[:, -1] |= near[:, -1]
        for _ in range(6000):
            d = reach.copy()
            d[1:, :] |= reach[:-1, :]; d[:-1, :] |= reach[1:, :]
            d[:, 1:] |= reach[:, :-1]; d[:, :-1] |= reach[:, 1:]
            d &= near
            if np.array_equal(d, reach):
                break
            reach = d

        alpha = np.where(reach, 0, 255).astype(np.uint8)
        a_img = Image.fromarray(alpha, "L").filter(ImageFilter.GaussianBlur(float(data.get("feather", 1.0))))
        out = im.convert("RGBA")
        out.putalpha(a_img)
        buf = io.BytesIO()
        out.save(buf, "PNG")
        return jsonify({"image_data": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()})
    except Exception as e:
        return jsonify({"error": f"Background removal failed: {e}"}), 500


@app.route("/vdb-options", methods=["POST"])
def vdb_options_route():
    """Cascading dropdown source: return VDB's real make/model/trim lists so the
    user picks exact catalog values (the final photo call then hits on the first
    try — no guessing, no GPT, no wasted credits). Lists are cached in-process,
    and quota/no-record messages are surfaced verbatim."""
    if not VDB_API_KEY:
        return jsonify({"error": "VDB_API_KEY is not set on the server. Add it in Railway → Variables."}), 500
    data = request.json or {}
    level = (data.get("level") or "").strip()
    year = str(data.get("year", "")).strip()
    make = (data.get("make") or "").strip()
    model = (data.get("model") or "").strip()
    enc = lambda s: urllib.parse.quote(s, safe="")

    if level == "make" and year:
        path = f"/vehicle-media/options/v3/make/{enc(year)}"
    elif level == "model" and year and make:
        path = f"/vehicle-media/options/v3/model/{enc(year)}/{enc(make)}"
    elif level == "trim" and year and make and model:
        path = f"/vehicle-media/options/v3/trim/{enc(year)}/{enc(make)}/{enc(model)}"
    else:
        return jsonify({"error": "Missing parameters for that level."}), 400

    if path in _VDB_OPT_CACHE:                      # already paid for this list
        return jsonify({"options": _VDB_OPT_CACHE[path], "cached": True})

    try:
        code, body, raw = _vdb_get(path)
    except Exception as e:
        return jsonify({"error": str(e)}), 502
    if code == 401:
        return jsonify({"error": "Invalid Vehicle Databases API key.", "reason": "Invalid VDB key"}), 401

    opts = [x.strip() for x in (body.get("data") or []) if isinstance(x, str) and x.strip()]
    if opts:
        _VDB_OPT_CACHE[path] = opts
        return jsonify({"options": opts})
    # empty -> surface VDB's own reason (quota exhausted, no records, etc.)
    msg = body.get("message") or body.get("status") or (raw[:200] if raw else f"HTTP {code}")
    return jsonify({"options": [], "vdb_status": code, "vdb_message": msg, "requested": path})


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
    skip_trim = bool(data.get("skip_trim", False))
    if not (year and make and model):
        return jsonify({"error": "Enter year, make, and model."}), 400

    def enc(s):
        return urllib.parse.quote(s, safe="")

    use_trim = bool(trim) and not skip_trim

    # Duplicate rows (common in bulk imports) return instantly — no VDB, no GPT,
    # no image fetch. Keyed on normalized fields so spelling variants share a hit.
    cache_key = _result_key(year, make, model, trim, use_trim)
    cached = _VDB_RESULT_CACHE.get(cache_key)
    if cached is not None:
        return jsonify({**cached, "cached": True})

    tried = set()   # remember media paths we've already fetched (don't pay twice)

    def fetch_media(mk, md, tr):
        """Hit vehicle-media/v2 for these exact strings. Returns
        (photos, exterior, colors, body, code, raw, path) or None if already tried."""
        path = f"/vehicle-media/v2/{enc(year)}/{enc(mk)}/{enc(md)}" + (f"/{enc(tr)}" if tr else "")
        if path in tried:
            return None
        tried.add(path)
        code, body, raw = _vdb_get(path)
        imgs = ((body.get("data") or {}).get("images") or {})
        ext = imgs.get("exterior") or []
        col = imgs.get("colors") or []
        # Prefer the per-color set (colors[]): one studio shot per factory color,
        # filenames carry real color names. exterior[] is angle shots with coded
        # filenames — only used when there's no per-color set.
        photos = col or ext or (imgs.get("interior") or [])
        return photos, ext, col, body, code, raw, path

    def respond(res, mk, md, tr):
        """Build the success payload (proxying the first photo) from a fetch result."""
        photos, ext, col, body, code, raw, path = res
        img_url = photos[0]
        # Enrich the picker with manufacturer color names + hex (one cached extra
        # call) only when there's actually a color set to label.
        color_meta = _vdb_colors(year, mk, md, tr) if (tr and len(photos) > 1) else []
        options = _label_photos(photos, color_meta)
        ireq = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(ireq, timeout=30) as iresp:
            ctype = iresp.headers.get("Content-Type", "image/jpeg")
            img_bytes = iresp.read()
        b64 = base64.b64encode(img_bytes).decode()
        d = body.get("data") or {}
        payload = {
            "found": True, "success": True,
            "image_data": f"data:{ctype};base64,{b64}",
            "image_url": img_url, "source": ("colors" if col else ("exterior" if ext else "interior")),
            "options": options, "used_trim": use_trim,
            "resolved_make": mk, "resolved_model": md, "resolved_trim": tr,
            "matched_make": d.get("make"), "matched_model": d.get("model"), "matched_trim": d.get("trim"),
            "matched_path": path,
        }
        _result_cache_put(cache_key, payload)
        return jsonify(payload)

    try:
        last = None   # (code, body, raw, path) of the most recent miss, for diagnostics

        # FAST PATH — optimistic. Most inputs are close enough that a direct fetch
        # with a normalized make + the canonical 'spaced' model hits on the first
        # call: no options lookups, no GPT. Costs at most 2 media calls.
        make_fast = norm_make(make)
        for md in model_spellings(model):
            res = fetch_media(make_fast, md, trim if use_trim else None)
            if res is None:
                continue
            photos, ext, col, body, code, raw, path = res
            if code == 401:
                return jsonify({"error": "Invalid Vehicle Databases API key.", "reason": "Invalid VDB key"}), 401
            last = (code, body, raw, path)
            if photos:
                return respond(res, make_fast, md, trim if use_trim else None)

        # SLOW PATH — only when the optimistic fetch missed. Snap each field onto
        # VDB's real catalog (options endpoints + local/GPT match), then fetch once.
        makes = _vdb_options(f"/vehicle-media/options/v3/make/{enc(year)}")
        make_c = _resolve(make, makes, "make") or make_fast
        models = _vdb_options(f"/vehicle-media/options/v3/model/{enc(year)}/{enc(make_c)}")
        model_c = _resolve(model, models, "model") or model.strip()

        trim_c = None
        avail_trims = []
        if use_trim:
            avail_trims = _vdb_options(f"/vehicle-media/options/v3/trim/{enc(year)}/{enc(make_c)}/{enc(model_c)}")
            trim_c = _resolve(trim, avail_trims, "trim")
            if not trim_c:
                # trim genuinely isn't in the catalog -> ask the user, with the real list.
                return jsonify({
                    "found": False, "trim_not_found": True,
                    "resolved_make": make_c, "resolved_model": model_c,
                    "available_trims": avail_trims,
                    "vdb_message": "Trim not found in catalog.",
                    "requested": f"{year} {make_c} {model_c} {trim}",
                })

        res = fetch_media(make_c, model_c, trim_c if use_trim else None)
        if res is not None:
            photos, ext, col, body, code, raw, path = res
            if code == 401:
                return jsonify({"error": "Invalid Vehicle Databases API key.", "reason": "Invalid VDB key"}), 401
            last = (code, body, raw, path)
            if photos:
                return respond(res, make_c, model_c, trim_c if use_trim else None)

        code, body, raw, path = last if last else (None, {}, "", None)
        msg = body.get("message") or body.get("status") or (raw[:200] if raw else f"HTTP {code}")
        return jsonify({
            "found": False, "trim_not_found": use_trim,
            "resolved_make": make_c, "resolved_model": model_c, "resolved_trim": trim_c,
            "available_trims": avail_trims,
            "vdb_status": code, "vdb_message": msg, "requested": path,
        })
    except Exception as e:
        return jsonify({"error": f"Vehicle Databases lookup failed: {e}"}), 502


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
