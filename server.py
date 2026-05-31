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

# Second-tier gate for the restricted tools (Lease Ad — TEST + Deal Hub). Override
# with RESTRICTED_PASSWORD in Railway (recommended — this repo is public).
RESTRICTED_PASSWORD = os.environ.get("RESTRICTED_PASSWORD") or "notforyou"
RESTRICTED_API = ("/carsxe-", "/carvector-", "/bulk-parse", "/deal-parse", "/deals")

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


@app.route("/unlock", methods=["GET", "POST"])
def unlock():
    """Second-tier unlock for the restricted tools."""
    if request.method == "POST":
        if hmac.compare_digest((request.json or {}).get("password", ""), RESTRICTED_PASSWORD):
            session["restricted_ok"] = True
            return jsonify({"ok": True})
        return jsonify({"error": "Incorrect password."}), 401
    return jsonify({"unlocked": bool(session.get("restricted_ok"))})


@app.before_request
def require_login():
    if request.path == "/login":
        return None
    if session.get("ok"):
        return None
    return redirect("/login")


@app.before_request
def gate_restricted():
    # block the restricted tools' data endpoints until the second password is entered
    if session.get("restricted_ok"):
        return None
    p = request.path
    if any(p.startswith(pre) for pre in RESTRICTED_API):
        return jsonify({"error": "This area is locked.", "locked": True}), 403


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


# the catalog (image source). Set CARSXE_API_KEY in the host env.
CARSXE_API_KEY = os.environ.get("CARSXE_API_KEY", "").strip()
_CARSXE_ALLOWED = set()     # image URLs the catalog returned to us (the only ones we'll proxy)
_CARSXE_IMG_CACHE = {}      # vehicle -> image response, so repeats never re-hit the catalog
_CARSXE_META_CACHE = {}     # vehicle -> colors + trims
_CARSXE_PROXY_CACHE = {}    # image url -> data URL
_CARSXE_CACHE_MAX = 150     # keep the last ~150 of each (FIFO)


def _cache_put(cache, key, val):
    if key in cache:
        return
    if len(cache) >= _CARSXE_CACHE_MAX:
        cache.pop(next(iter(cache)))   # evict oldest
    cache[key] = val


# CarVector (trial image source). Set CARVECTOR_API_KEY in the host env.
CARVECTOR_API_KEY = os.environ.get("CARVECTOR_API_KEY", "").strip()
_CARVECTOR_ALLOWED = set()
_CARVECTOR_CACHE = {}

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
@app.route("/deal-hub")
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


def _carsxe_ymm(make, model, year, trim):
    """One /v1/ymm lookup -> (colors, trims). Empty lists on any failure."""
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
    except Exception:
        return [], []
    best = body.get("bestMatch") or body.get("data") or {}
    cands = []
    col = best.get("color") or best.get("colors") or {}
    if isinstance(col, dict):
        cands.append(col.get("exterior"))
    elif isinstance(col, list):
        cands.append(col)
    cands += [best.get("exterior_colors"), body.get("colors"), body.get("exterior_colors")]
    ext = next((c for c in cands if isinstance(c, list) and c), [])
    colors, seen = [], set()
    for c in ext:
        if not isinstance(c, dict):
            continue
        name = (c.get("name") or c.get("color_name") or c.get("description") or "").strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            colors.append({"name": name, "hex": _rgb_to_hex(c.get("rgb") or c.get("rgb_value") or "")})
    trims = []
    for t in (body.get("trimOptions") or best.get("trimOptions") or []):
        nm = t if isinstance(t, str) else (t.get("trim") or t.get("name") or "")
        nm = (nm or "").strip()
        if nm and nm not in trims:
            trims.append(nm)
    return colors, trims


@app.route("/carsxe-meta", methods=["POST"])
def carsxe_meta():
    """Manufacturer exterior colors + trims for a vehicle. Falls back (drop trim,
    then recent prior years) when the exact year has no colour data, so the colour
    picker reliably shows the factory colours."""
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

    # exact -> drop trim -> recent prior years (color data lags for brand-new years)
    candidates = [(year, trim)]
    if trim:
        candidates.append((year, ""))
    try:
        yr = int(year)
        for back in (1, 2, 3):
            candidates.append((str(yr - back), ""))
    except Exception:
        pass

    colors, trims, tried = [], [], set()
    for (y, tr) in candidates:
        if (y, tr) in tried:
            continue
        tried.add((y, tr))
        c, t = _carsxe_ymm(make, model, y, tr)
        if t and not trims:
            trims = t
        if c:
            colors = c
            break

    payload = {"colors": colors, "trims": trims}
    if colors or trims:
        _cache_put(_CARSXE_META_CACHE, mkey, payload)
    return jsonify(payload)


@app.route("/carsxe-image", methods=["POST"])
def carsxe_image():
    """TRIAL: pull a vehicle photo from the catalog's /images endpoint (make/model based,
    transparent by default) so we can compare its image quality against Vehicle
    Databases. Returns the full set of results so the user can pick the best one."""
    if not CARSXE_API_KEY:
        return jsonify({"error": "CARSXE_API_KEY is not set on the server. Add it in Railway → Variables."}), 500
    data = request.json or {}
    make = data.get("make", "").strip()
    model = data.get("model", "").strip()
    year = str(data.get("year", "")).strip()
    trim = data.get("trim", "").strip()
    color = data.get("color", "").strip().lower()    # the catalog expects a lowercase basic colour
    if not (make and model):
        return jsonify({"error": "Pick a make and model first."}), 400

    key = "|".join([year, make.lower(), model.lower(), trim.lower(), color])
    cached = _CARSXE_IMG_CACHE.get(key)
    if cached is not None:
        for o in cached.get("options", []):           # keep proxy allow-list warm
            _CARSXE_ALLOWED.add(o["url"])
        return jsonify({**cached, "cached": True})

    base = {"key": CARSXE_API_KEY, "make": make, "model": model,
            "transparent": "true", "size": "Large", "format": "json"}
    if year:
        base["year"] = year
    if trim:
        base["trim"] = trim
    if color:
        base["color"] = color

    # Best-first attempts: ask for exterior-only studio shots (needs year+trim),
    # then fall back to the unfiltered set so we always return something.
    attempts = []
    if year and trim:
        attempts.append({**base, "photoType": "exterior"})
    attempts.append(base)

    imgs, body = [], {}
    try:
        for p in attempts:
            url = "https://api.carsxe.com/images?" + urllib.parse.urlencode(p)
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.loads(r.read().decode("utf-8", "ignore"))
            imgs = [im for im in (body.get("images") or []) if im.get("link")]
            if imgs:
                break
    except urllib.error.HTTPError as e:
        return jsonify({"error": f"the catalog error {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}"}), 502
    except Exception as e:
        return jsonify({"error": f"the catalog request failed: {e}"}), 502

    if not imgs:
        return jsonify({"found": False, "message": body.get("error") or "No images returned by the catalog."})
    for im in imgs:
        _CARSXE_ALLOWED.add(im["link"])
    options = [{"url": im["link"], "thumb": im.get("thumbnailLink") or im["link"],
                "w": im.get("width"), "h": im.get("height"),
                "transparent": str(im.get("mime", "")).endswith("png")}
               for im in imgs]
    try:
        first = _carsxe_dataurl(imgs[0]["link"])
    except Exception as e:
        return jsonify({"error": f"Couldn't load the the catalog image: {e}"}), 502
    payload = {"found": True, "success": True, "image_data": first,
               "image_url": imgs[0]["link"], "options": options}
    _cache_put(_CARSXE_IMG_CACHE, key, payload)
    return jsonify(payload)


@app.route("/carsxe-proxy", methods=["POST"])
def carsxe_proxy():
    """Proxy a specific the catalog image (only URLs the catalog itself returned — no open SSRF)."""
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


def _carvector_get(path):
    req = urllib.request.Request("https://api.carvector.io" + path,
                                 headers={"Authorization": f"Bearer {CARVECTOR_API_KEY}", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


@app.route("/carvector-image", methods=["POST"])
def carvector_image():
    """TRIAL: CarVector returns one illustration per vehicle via a 2-step flow
    (search year/make/model -> get id -> fetch detail -> image_url). We gather a
    few matching rows (trims/submodels) so the user has a small set to pick from."""
    if not CARVECTOR_API_KEY:
        return jsonify({"error": "CARVECTOR_API_KEY is not set on the server. Add it in Railway → Variables."}), 500
    data = request.json or {}
    make = data.get("make", "").strip()
    model = data.get("model", "").strip()
    year = str(data.get("year", "")).strip()
    if not (make and model):
        return jsonify({"error": "Pick a make and model first."}), 400

    key = "|".join([year, make.lower(), model.lower()])
    cached = _CARVECTOR_CACHE.get(key)
    if cached is not None:
        _CARVECTOR_ALLOWED.update(o["url"] for o in cached.get("options", []))
        return jsonify({**cached, "cached": True})

    # try exact (year+make+model), then drop the year (specs DBs lag on new years),
    # then make+model only — first non-empty wins. Keep diagnostics for the UI.
    attempts = []
    if year:
        attempts.append({"make": make, "model": model, "year": year, "limit": "8"})
    attempts.append({"make": make, "model": model, "limit": "8"})

    results, tried = [], []
    try:
        for qs in attempts:
            search = _carvector_get("/v1/vehicles?" + urllib.parse.urlencode(qs))
            rs = search.get("results") or search.get("data") or search.get("vehicles") or []
            tried.append({"q": {k: v for k, v in qs.items() if k != "limit"}, "count": len(rs)})
            if rs:
                results = rs
                break
    except urllib.error.HTTPError as e:
        return jsonify({"error": f"CarVector error {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}"}), 502
    except Exception as e:
        return jsonify({"error": f"CarVector request failed: {e}"}), 502

    if not results:
        return jsonify({"found": False, "message": "No vehicle found in CarVector.", "tried": tried})

    options, seen = [], set()
    for v in results[:5]:                       # cap detail calls (each one is a request)
        vid = v.get("id")
        if not vid:
            continue
        try:
            detail = _carvector_get("/v1/vehicles/" + urllib.parse.quote(str(vid)))
        except Exception:
            continue
        img = detail.get("image_url")
        if img and img not in seen:
            seen.add(img)
            label = " ".join(str(x) for x in [detail.get("year"), detail.get("trim") or detail.get("submodel") or detail.get("body_class")] if x)
            options.append({"url": img, "thumb": img, "label": label or "Illustration"})
    if not options:
        return jsonify({"found": False, "message": "CarVector has no image for that vehicle (image plans only)."})

    _CARVECTOR_ALLOWED.update(o["url"] for o in options)
    try:
        first = _carsxe_dataurl(options[0]["url"])
    except Exception as e:
        return jsonify({"error": f"Couldn't load the CarVector image: {e}"}), 502
    payload = {"found": True, "image_data": first, "image_url": options[0]["url"], "options": options}
    _cache_put(_CARVECTOR_CACHE, key, payload)
    return jsonify(payload)


@app.route("/carvector-proxy", methods=["POST"])
def carvector_proxy():
    url = (request.json or {}).get("url", "").strip()
    if url not in _CARVECTOR_ALLOWED:
        return jsonify({"error": "URL not allowed."}), 400
    try:
        return jsonify({"success": True, "image_data": _carsxe_dataurl(url)})
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


# ----------------------- Deal Hub -----------------------
DEALS_FILE = os.path.join(GENERATED_DIR, "deals.json")
DEAL_FIELDS = ["year", "make", "model", "trim", "msrp", "orig_mo", "das", "term",
               "miles", "tax_in_mo", "broker_fee", "dealer", "notes", "source"]


def _load_deals():
    try:
        with open(DEALS_FILE) as f:
            d = json.load(f)
            return d if isinstance(d, list) else []
    except Exception:
        return []


def _save_deals(deals):
    with open(DEALS_FILE, "w") as f:
        json.dump(deals, f, indent=1)


def _derive_zero_down(d):
    """0-Down Mo = Orig Mo + DAS / Term (the dealer-sheet convention)."""
    try:
        mo = float(d.get("orig_mo") or 0)
        das = float(d.get("das") or 0)
        term = float(d.get("term") or 0)
        if mo and term:
            d["zero_down_mo"] = str(round(mo + das / term, 2))
    except Exception:
        pass
    return d


@app.route("/deal-parse", methods=["POST"])
def deal_parse():
    """Read messy pasted deal text into structured rows, applying the user's
    plain-English adjustment rules (math) and propagating global header terms."""
    if not API_KEY or API_KEY == "sk-your-key-here":
        return jsonify({"error": "OPENAI_API_KEY not configured on the server."}), 500
    body = request.json or {}
    text = (body.get("text") or "").strip()
    rules = (body.get("rules") or "").strip()
    if not text:
        return jsonify({"error": "Paste some deals first."}), 400
    props = {k: {"type": "string"} for k in DEAL_FIELDS}
    schema = {
        "type": "object", "additionalProperties": False, "required": ["deals"],
        "properties": {"deals": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": DEAL_FIELDS, "properties": props}}},
    }
    system = (
        "You convert messy car lease/finance deal text into structured rows. For EACH "
        "vehicle output: year, make, model, trim, msrp, orig_mo (base monthly payment), "
        "das (due at signing / cash to dealer), term (months), miles (annual mileage), "
        "tax_in_mo (monthly WITH tax, if that's how it's quoted), broker_fee, dealer, "
        "notes (loyalty / conquest / credit tier / tax handling / any other terms), and "
        "source (a short label for where the deal came from — dealer, flyer title, or sender).\n"
        "RULES:\n"
        "- A list usually has GLOBAL header terms (e.g. '$2000 Down, 36 Month, 10k Miles, "
        "$1000 BF', or 'Diana Santa Monica, 1k fee included') that apply to EVERY line below "
        "— copy them into each row.\n"
        "- Normalize shorthand to plain numbers (no $ or commas): '3k'->3000, '7.5k'->7500, "
        "'$51k MSRP'->51000, '$289'->289. '13/7500' means term=13, miles=7500.\n"
        "- A payment quoted 'tax inc'/'tax in' goes in tax_in_mo; otherwise orig_mo.\n"
        "- After extracting, APPLY the user's adjustment rules below and do the arithmetic.\n"
        "- Leave a field '' if it isn't present.\n"
        f"ADJUSTMENT RULES TO APPLY TO EVERY ROW: {rules or '(none)'}"
    )
    try:
        client = OpenAI(api_key=API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
            response_format={"type": "json_schema", "json_schema": {"name": "deals", "strict": True, "schema": schema}},
        )
        deals = json.loads(resp.choices[0].message.content).get("deals", [])
        deals = [_derive_zero_down(d) for d in deals]
        return jsonify({"deals": deals})
    except Exception as e:
        return jsonify({"error": f"Couldn't parse those deals: {e}"}), 502


@app.route("/deals", methods=["GET", "POST"])
def deals():
    if request.method == "POST":
        incoming = (request.json or {}).get("deals", [])
        if not isinstance(incoming, list):
            return jsonify({"error": "Bad payload."}), 400
        _save_deals(incoming)
        return jsonify({"ok": True, "count": len(incoming)})
    return jsonify({"deals": _load_deals()})


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
