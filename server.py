from flask import Flask, request, jsonify, send_from_directory, send_file, session, redirect
from openai import OpenAI
import base64
import os
import re
import io
import csv
import json
import hmac
import time
import zipfile
import secrets
import threading
import rx_form
import urllib.request
import urllib.parse
import urllib.error
import socket
import ipaddress
from html import unescape as _html_unescape

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
# Lease Ad Generator is no longer second-password-protected, so its shared photo/parse
# endpoints (/carsxe-*, /carvector-*, /bulk-parse) are open past the primary login like
# the Sold/Review tools. The Deal Hub / Invoice / Desking DATA endpoints stay gated.
RESTRICTED_API = ("/deal-parse", "/deal-search", "/deals", "/contacts", "/published", "/verify-", "/invoices", "/desk-parse", "/desk-programs", "/copilot-kb")

# Aletheya Toolbox — a separate, non-Nova workspace with its OWN password gate.
# Override with TOOLBOX_PASSWORD in the host env (recommended — this repo is public).
TOOLBOX_PASSWORD = os.environ.get("TOOLBOX_PASSWORD") or "arvin"

# Nova Admins — the back-office deal ledger / agent-payroll tool. Its OWN gate
# (session["admin_ok"]), separate from the Nova workspace login. Override with
# NOVA_ADMIN_PASSWORD in the host env — DO set it: this repo is public, so the
# default below is readable, and this tool holds financial / commission data.
NOVA_ADMIN_PASSWORD = os.environ.get("NOVA_ADMIN_PASSWORD") or "ADMIN"
if not os.environ.get("NOVA_ADMIN_PASSWORD"):
    print("[security] NOVA_ADMIN_PASSWORD is not set — using 'ADMIN'. Set it in Railway (financial data).")

# Optional shared-secret token for headless writes to Nova Admins (seeding the live
# volume, the nightly Garage sync). When set, an X-Nova-Token header that matches is
# accepted in place of an admin browser session. No default — token auth is off unless set.
NOVA_ADMIN_TOKEN = os.environ.get("NOVA_ADMIN_TOKEN", "").strip()

# Tiny in-memory brute-force throttle: max attempts per IP per window.
_LOGIN_FAILS = {}
_LOGIN_MAX = 8
_LOGIN_WINDOW = 300   # seconds


def _client_ip():
    xff = request.headers.get("X-Forwarded-For", "")
    return (xff.split(",")[0].strip() if xff else (request.remote_addr or "?"))


def login_page(message="", next_path="/novauto"):
    msg = f'<p class="err">{message}</p>' if message else ""
    safe_next = next_path if next_path.startswith("/") else "/novauto"
    nxt = f'<input type="hidden" name="next" value="{safe_next}">'
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
    {nxt}
    <input type="password" name="password" placeholder="Password" autofocus autocomplete="current-password">
    <button type="submit">Enter</button>
    <p class="legal"><b>Confidential &amp; Proprietary.</b> This application and all concepts, designs, workflows, data, and content within are the exclusive property of <b>NovAuto</b> and are intended solely for authorized internal use by its personnel. Unauthorized access, use, copying, reproduction, distribution, or disclosure of any ideas or materials herein is strictly prohibited and may result in legal action.</p>
  </form>
</body></html>"""


def toolbox_login_page(message=""):
    msg = f'<p class="err">{message}</p>' if message else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Aletheya Toolbox</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#05080d; color:#fff;
    min-height:100vh; display:flex; align-items:center; justify-content:center;
    background-image: radial-gradient(70% 50% at 50% 35%, rgba(155,109,255,.28), rgba(8,16,30,0) 70%); }}
  .card {{ width:340px; max-width:90vw; background:#101319; border:1px solid #232733; border-radius:16px; padding:34px 28px; text-align:center; box-shadow:0 30px 80px rgba(0,0,0,.5); }}
  .brand {{ font-size:1.5rem; font-weight:800; letter-spacing:-.5px; margin-bottom:4px; }}
  .brand span {{ color:#a98bff; }}
  .sub {{ color:#6b7280; font-size:.72rem; letter-spacing:.12em; text-transform:uppercase; margin-bottom:24px; }}
  input {{ width:100%; background:#0a0d12; border:1px solid #2a2f3a; border-radius:9px; padding:13px 15px; color:#fff; font-size:.95rem; outline:none; }}
  input:focus {{ border-color:#a98bff; }}
  button {{ width:100%; margin-top:12px; padding:13px; border:none; border-radius:9px; background:#8a5cf0; color:#fff; font-weight:600; font-size:.95rem; cursor:pointer; }}
  button:hover {{ background:#7a4ce0; }}
  .err {{ color:#ff6b6b; font-size:.82rem; margin-bottom:12px; }}
  .legal {{ margin-top:20px; padding-top:16px; border-top:1px solid #1c2029; font-size:.66rem; line-height:1.5; color:#5a6472; text-align:left; }}
  .legal b {{ color:#8a94a3; font-weight:700; }}
</style></head>
<body>
  <form class="card" method="POST" action="/toolbox-login">
    <div class="brand">Aletheya <span>Toolbox</span></div>
    <div class="sub">Internal tools</div>
    {msg}
    <input type="password" name="password" placeholder="Password" autofocus autocomplete="current-password">
    <button type="submit">Enter</button>
    <p class="legal"><b>Confidential &amp; Proprietary.</b> This workspace and all content within are the exclusive property of <b>Aletheya</b> and intended solely for authorized internal use. Unauthorized access, use, or disclosure is strictly prohibited.</p>
  </form>
</body></html>"""


@app.route("/toolbox-login", methods=["GET", "POST"])
def toolbox_login():
    if request.method == "POST":
        ip = _client_ip() + ":tb"
        cnt, t0 = _LOGIN_FAILS.get(ip, (0, time.time()))
        if time.time() - t0 > _LOGIN_WINDOW:
            cnt, t0 = 0, time.time()
        if cnt >= _LOGIN_MAX:
            return toolbox_login_page("Too many attempts — wait a few minutes and try again."), 429
        if hmac.compare_digest(request.form.get("password", ""), TOOLBOX_PASSWORD):
            session["toolbox_ok"] = True
            _LOGIN_FAILS.pop(ip, None)
            return redirect("/toolbox")
        _LOGIN_FAILS[ip] = (cnt + 1, t0)
        return toolbox_login_page("Incorrect password — try again."), 401
    if session.get("toolbox_ok"):
        return redirect("/toolbox")
    return toolbox_login_page()


def nova_admin_login_page(message=""):
    msg = f'<p class="err">{message}</p>' if message else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Nova Admins</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#05080d; color:#fff;
    min-height:100vh; display:flex; align-items:center; justify-content:center;
    background-image: radial-gradient(70% 50% at 50% 35%, rgba(52,211,153,.22), rgba(8,16,30,0) 70%); }}
  .card {{ width:340px; max-width:90vw; background:#101319; border:1px solid #232733; border-radius:16px; padding:34px 28px; text-align:center; box-shadow:0 30px 80px rgba(0,0,0,.5); }}
  .brand {{ font-size:1.5rem; font-weight:800; letter-spacing:-.5px; margin-bottom:4px; }}
  .brand span {{ color:#34d399; }}
  .sub {{ color:#6b7280; font-size:.72rem; letter-spacing:.12em; text-transform:uppercase; margin-bottom:24px; }}
  input {{ width:100%; background:#0a0d12; border:1px solid #2a2f3a; border-radius:9px; padding:13px 15px; color:#fff; font-size:.95rem; outline:none; }}
  input:focus {{ border-color:#34d399; }}
  button {{ width:100%; margin-top:12px; padding:13px; border:none; border-radius:9px; background:#1f9d6b; color:#fff; font-weight:600; font-size:.95rem; cursor:pointer; }}
  button:hover {{ background:#1b8a5e; }}
  .err {{ color:#ff6b6b; font-size:.82rem; margin-bottom:12px; }}
  .legal {{ margin-top:20px; padding-top:16px; border-top:1px solid #1c2029; font-size:.66rem; line-height:1.5; color:#5a6472; text-align:left; }}
  .legal b {{ color:#8a94a3; font-weight:700; }}
</style></head>
<body>
  <form class="card" method="POST" action="/nova-admins-login">
    <div class="brand">Nova <span>Admins</span></div>
    <div class="sub">Back office · Restricted</div>
    {msg}
    <input type="password" name="password" placeholder="Admin password" autofocus autocomplete="current-password">
    <button type="submit">Enter</button>
    <p class="legal"><b>Confidential &amp; Proprietary.</b> Financial, commission, and client records belonging to <b>NovAuto</b>, for authorized administrators only. Unauthorized access, use, or disclosure is strictly prohibited and may result in legal action.</p>
  </form>
</body></html>"""


@app.route("/nova-admins-login", methods=["GET", "POST"])
def nova_admins_login():
    if request.method == "POST":
        ip = _client_ip() + ":na"
        cnt, t0 = _LOGIN_FAILS.get(ip, (0, time.time()))
        if time.time() - t0 > _LOGIN_WINDOW:
            cnt, t0 = 0, time.time()
        if cnt >= _LOGIN_MAX:
            return nova_admin_login_page("Too many attempts — wait a few minutes and try again."), 429
        if hmac.compare_digest(request.form.get("password", ""), NOVA_ADMIN_PASSWORD):
            session["admin_ok"] = True
            _LOGIN_FAILS.pop(ip, None)
            return redirect("/nova-admins")
        _LOGIN_FAILS[ip] = (cnt + 1, t0)
        return nova_admin_login_page("Incorrect password — try again."), 401
    if session.get("admin_ok"):
        return redirect("/nova-admins")
    return nova_admin_login_page()


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
            nxt = request.args.get("next") or request.form.get("next") or "/novauto"
            if not nxt.startswith("/"):              # only allow local redirects
                nxt = "/novauto"
            return redirect(nxt)
        _LOGIN_FAILS[ip] = (cnt + 1, t0)
        return login_page("Incorrect password — try again.",
                          request.form.get("next", "/novauto")), 401
    return login_page(next_path=request.args.get("next", "/novauto"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/unlock", methods=["GET", "POST"])
def unlock():
    """Second-tier unlock for the restricted tools."""
    if request.method == "POST":
        if hmac.compare_digest((request.json or {}).get("password", ""), RESTRICTED_PASSWORD):
            session["restricted_ok"] = True
            return jsonify({"ok": True})
        return jsonify({"error": "Incorrect password."}), 401
    return jsonify({"unlocked": bool(session.get("restricted_ok"))})


# Paths anyone can reach without logging in: the public byAletheya home page,
# the login screen, and the brand asset the home page shows.
PUBLIC_PATHS = ("/", "/login", "/logo.png")

@app.before_request
def require_login():
    p = request.path
    if p in PUBLIC_PATHS:
        return None
    # The Aletheya Toolbox is its own workspace gated by its own password
    # (session["toolbox_ok"]) — completely independent of the Nova login.
    if p.startswith("/toolbox"):
        if p == "/toolbox-login":
            return None
        if session.get("toolbox_ok"):
            return None
        if request.method == "GET":
            return redirect("/toolbox-login")
        return jsonify({"error": "This area is locked.", "locked": True}), 403
    # Nova Admins is its own workspace gated by its own password (session["admin_ok"]).
    if p.startswith("/nova-admins"):
        if p == "/nova-admins-login":
            return None
        if session.get("admin_ok"):
            return None
        tok = request.headers.get("X-Nova-Token", "")
        if NOVA_ADMIN_TOKEN and tok and hmac.compare_digest(tok, NOVA_ADMIN_TOKEN):
            return None
        if request.method == "GET":
            return redirect("/nova-admins-login")
        return jsonify({"error": "This area is locked.", "locked": True}), 403
    # Everything else is the Nova workspace, gated by APP_PASSWORD.
    if session.get("ok"):
        return None
    # remember where they were headed so login can send them straight back
    if request.method == "GET":
        return redirect("/login?next=" + request.path)
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
_CARSXE_ALLOWED = set()     # exact image URLs the catalog returned (fast-path proxy allow)
_CARSXE_HOSTS = set()       # CDN hosts the catalog served from — learned so a URL still proxies
                            # after the exact-set is lost (server restart) or evicted
_CARSXE_CDN_ROOTS = ('carsxe.com', 'imagin.studio')   # seeded vendor CDNs so proxy works even before the first fetch post-restart
_CARSXE_IMG_CACHE = {}      # vehicle -> image response, so repeats never re-hit the catalog
_CARSXE_META_CACHE = {}     # vehicle -> colors + trims
_CARSXE_CANON_CACHE = {}    # vehicle -> canonical make/model/trim (name cleanup)
_CARSXE_PROXY_CACHE = {}    # image url -> data URL
_CARSXE_CACHE_MAX = 150     # keep the last ~150 of each (FIFO)


def _cache_put(cache, key, val):
    if key in cache:
        return
    if len(cache) >= _CARSXE_CACHE_MAX:
        cache.pop(next(iter(cache)))   # evict oldest
    cache[key] = val


def _carsxe_base_model(model):
    """Drop the powertrain word the model now carries for display (e.g. "Sorento Hybrid"
    -> "Sorento") so the image/colour catalog — which only knows the base model — still
    matches. Whole-word only, so "Mach-E" / "EV6" / "bZ4X" survive untouched."""
    q = re.sub(r"\b(?:plug[\s-]?in hybrid|plug[\s-]?in|hybrid|phev|electric|ev|bev)\b", " ", model or "", flags=re.I)
    q = re.sub(r"\s+", " ", q).strip()
    return q or (model or "")


def _carsxe_host(url):
    try:
        return urllib.parse.urlparse(url).netloc.lower().split(":")[0]
    except Exception:
        return ""


def _carsxe_remember(url):
    """Record a catalog image URL (and its CDN host) as safe to proxy."""
    if not url:
        return
    _CARSXE_ALLOWED.add(url)
    h = _carsxe_host(url)
    if h:
        _CARSXE_HOSTS.add(h)


def _carsxe_proxy_ok(url):
    """Proxy guard: exact URL we've seen, OR any URL on a CDN host the catalog has
    served from / a known vendor CDN. Host-based so a thumbnail still loads after the
    exact allow-set is lost to a restart or FIFO eviction (was a silent 'URL not allowed')."""
    if url in _CARSXE_ALLOWED:
        return True
    h = _carsxe_host(url)
    if not h:
        return False
    if h in _CARSXE_HOSTS:
        return True
    return any(h == r or h.endswith("." + r) for r in _CARSXE_CDN_ROOTS)


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


# The public byAletheya home page — the front door at byaletheya.com. Anyone can
# see it; the "Open Novauto" button links to /novauto, which is behind the login.
@app.route("/")
def home():
    return send_file(os.path.join(BASE_DIR, "home.html"))


# Each tool has its own clean URL. They all serve the same single-page app; the
# client reads the path on load to open the right view (and pushState keeps the
# URL in sync as you switch tools). Deep-linkable and bookmarkable.
# /novauto is the entry point reached from the home page.
@app.route("/novauto")
@app.route("/lease")
@app.route("/sold")
@app.route("/leasead-test")
@app.route("/deal-hub")
@app.route("/review-generator")
@app.route("/invoice")
@app.route("/quote")
@app.route("/desking")
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


def _nova_admin_serve(filename):
    """Serve a Nova Admins tool page with the shared dataset injected from the
    gitignored generated/nova_admins.json (kept out of this public repo)."""
    html = open(os.path.join(BASE_DIR, filename), encoding="utf-8").read()
    seed_path = os.path.join(GENERATED_DIR, "nova_admins.json")
    if os.path.exists(seed_path):
        try:
            with open(seed_path, encoding="utf-8") as f:
                html = html.replace("/*NOVA_SEED*/", "window.NOVA_SEED=" + f.read() + ";", 1)
        except Exception:
            pass
    return html


# Nova Admins is a SUITE: each tool is its own page under /nova-admins/*
# (all behind the same admin gate + sharing one data store).
@app.route("/nova-admins")
def nova_admins_page():
    """Tool 1: the deal ledger / agent payroll."""
    return _nova_admin_serve("nova_admins.html")


@app.route("/nova-admins/tasks")
def nova_admins_tasks_page():
    """Tool 2: the Linear-style task manager."""
    return _nova_admin_serve("nova_tasks.html")


@app.route("/nova-admins/notes")
def nova_admins_notes_page():
    """Tool 3: Notion-style notes."""
    return _nova_admin_serve("nova_notes.html")


@app.route("/nova-admins/parse-task", methods=["POST"])
def nova_admins_parse_task():
    """Turn natural language into one or more structured tasks (title, subtasks,
    assignee, due date, priority, labels, notes)."""
    if not API_KEY or API_KEY == "sk-your-key-here":
        return jsonify({"error": "OPENAI_API_KEY not configured on the server."}), 500
    body = request.json or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Say what needs doing."}), 400
    today = (body.get("today") or "").strip()
    task_schema = {
        "type": "object", "additionalProperties": False,
        "required": ["title", "status", "priority", "assignee", "due", "labels", "notes", "subtasks"],
        "properties": {
            "title": {"type": "string"},
            "status": {"type": "string", "enum": ["backlog", "todo", "inprogress", "done", ""]},
            "priority": {"type": "string", "enum": ["urgent", "high", "medium", "low", "none", ""]},
            "assignee": {"type": "string", "enum": ["nema", "arvin", "edgar", ""]},
            "due": {"type": "string"},
            "labels": {"type": "array", "items": {"type": "string"}},
            "notes": {"type": "string"},
            "subtasks": {"type": "array", "items": {"type": "string"}},
        },
    }
    schema = {
        "type": "object", "additionalProperties": False,
        "required": ["ok", "summary", "tasks"],
        "properties": {"ok": {"type": "boolean"}, "summary": {"type": "string"},
                       "tasks": {"type": "array", "items": task_schema}},
    }
    sys = (
        "You convert natural language into structured to-do tasks for Nova's back-office task board. "
        "Output STRICT JSON. Rules:\n"
        f"- Today is {today or 'unknown'} — resolve relative dates ('tomorrow', 'Friday', 'end of month', 'in 2 weeks') "
        "to YYYY-MM-DD in `due`; '' if no date mentioned.\n"
        "- One message may contain SEVERAL tasks — split them; but an enumeration of steps under one goal is ONE task "
        "with `subtasks` (short imperative strings).\n"
        "- title: short imperative ('Pay agents for June'). Put extra context/details in `notes`.\n"
        "- assignee: nema / arvin / edgar when a name (or 'me' = edgar) is mentioned, else ''.\n"
        "- priority: only if urgency is expressed ('asap'/'urgent' -> urgent; 'important' -> high; 'whenever/low prio' -> low), else ''.\n"
        "- status: 'todo' unless they say it's already started ('inprogress'), an idea/someday ('backlog'), or done.\n"
        "- labels: 1-2 short category tags ONLY if obvious (Payroll, Collections, Deals, Follow-up, Ops, Automation, Finance).\n"
        "- ok=false only if the message clearly isn't a task. summary = one short confirmation sentence."
    )
    try:
        client = OpenAI(api_key=API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": text}],
            response_format={"type": "json_schema", "json_schema": {"name": "tasks", "strict": True, "schema": schema}},
        )
        return jsonify(json.loads(resp.choices[0].message.content))
    except Exception as e:
        return jsonify({"error": "Couldn't parse that — " + str(e)[:160]}), 500


@app.route("/nova-admins/parse", methods=["POST"])
def nova_admins_parse():
    """Turn a natural-language / pasted deal into one structured Nova Admins deal."""
    if not API_KEY or API_KEY == "sk-your-key-here":
        return jsonify({"error": "OPENAI_API_KEY not configured on the server."}), 500
    body = request.json or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Type a deal to add."}), 400
    agents = [a for a in (body.get("agents") or []) if isinstance(a, dict) and a.get("id")][:60]
    today = (body.get("today") or "").strip()
    agent_list = "; ".join(f'{a.get("id")}={a.get("name")}' for a in agents) or "(none provided)"
    schema = {
        "type": "object", "additionalProperties": False,
        "required": ["client", "year", "make", "model", "vin", "dealer", "type", "term", "agentId",
                     "lead", "front", "back", "feeJason", "feeReferral", "pay", "wOffered", "wSold",
                     "fColl", "bColl", "aPaidF", "aPaidFd", "aPaidB", "aPaidBd", "date", "notes", "ok", "summary"],
        "properties": {
            "client": {"type": "string"}, "year": {"type": "string"}, "make": {"type": "string"},
            "model": {"type": "string"}, "vin": {"type": "string"}, "dealer": {"type": "string"},
            "type": {"type": "string", "enum": ["Lease", "Buy", ""]}, "term": {"type": "string"},
            "agentId": {"type": "string"}, "lead": {"type": "string", "enum": ["own", "nova", "referral", ""]},
            "front": {"type": "number"}, "back": {"type": "number"},
            "feeJason": {"type": "number"}, "feeReferral": {"type": "number"},
            "pay": {"type": "string", "enum": ["Stripe", "Zelle", "Cash", "Check", ""]},
            "wOffered": {"type": "boolean"}, "wSold": {"type": "boolean"},
            "fColl": {"type": "boolean"}, "bColl": {"type": "boolean"},
            "aPaidF": {"type": "boolean"}, "aPaidFd": {"type": "string"},
            "aPaidB": {"type": "boolean"}, "aPaidBd": {"type": "string"},
            "date": {"type": "string"}, "notes": {"type": "string"},
            "ok": {"type": "boolean"}, "summary": {"type": "string"},
        },
    }
    sys = (
        "You convert ONE natural-language or pasted car lease/finance deal into a structured deal for "
        "Nova's back-office ledger. Output STRICT JSON for the schema. Rules:\n"
        f"- Today is {today or 'unknown'}; dates are YYYY-MM-DD. If no deal date is given, use today.\n"
        "- client: customer name as 'First L.' (first name + last initial).\n"
        f"- agentId: match the salesperson to ONE of these agents and output its id (or '' if unknown): {agent_list}\n"
        "- lead: 'own' = agent's own lead/Agent-sourced; 'nova' = Nova Lead (FB/IG ads); 'referral' = referral.\n"
        "- type: Lease or Buy. term = months (string).\n"
        "- front = front gross (client/broker fee), back = back gross (dealer reserve). Numbers only — no $ or commas.\n"
        "- feeJason = fee shared with Jason if stated; feeReferral = a referral/shared fee OR a generic 'fees shared' "
        "lump. Do NOT include Stripe processing (its 3% is auto-computed from the payment method).\n"
        "- pay: Stripe / Zelle / Cash / Check.\n"
        "- wOffered/wSold = was warranty offered / sold.\n"
        "- fColl/bColl = was the front (client) / back (dealer) money collected by Nova. aPaidF/aPaidB = was the agent "
        "paid their front/back share (aPaidFd/aPaidBd = those pay dates if stated).\n"
        "- Unknown strings => '', unknown numbers => 0, unknown booleans => false.\n"
        "- ok=true if you found at least a client or a vehicle; false if this isn't a deal. "
        "summary = one short sentence describing what you logged."
    )
    try:
        client = OpenAI(api_key=API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": text}],
            response_format={"type": "json_schema", "json_schema": {"name": "deal", "strict": True, "schema": schema}},
        )
        return jsonify(json.loads(resp.choices[0].message.content))
    except Exception as e:
        return jsonify({"error": "Couldn't parse that — " + str(e)[:160]}), 500


NOVA_ADMIN_DB = lambda: os.path.join(GENERATED_DIR, "nova_admins.json")


def _nova_nightly_backup():
    """Daily dated snapshot of the Nova Admins data → generated/nova_admins_backups/,
    keeping the last 30 days. Runs one snapshot per calendar day, survives restarts."""
    import shutil
    while True:
        try:
            src = NOVA_ADMIN_DB()
            if os.path.exists(src):
                bdir = os.path.join(GENERATED_DIR, "nova_admins_backups")
                os.makedirs(bdir, exist_ok=True)
                dest = os.path.join(bdir, "nova_admins_" + time.strftime("%Y-%m-%d") + ".json")
                if not os.path.exists(dest):
                    shutil.copy2(src, dest)
                for old in sorted(f for f in os.listdir(bdir) if f.endswith(".json"))[:-30]:
                    try:
                        os.remove(os.path.join(bdir, old))
                    except Exception:
                        pass
        except Exception:
            pass
        time.sleep(6 * 3600)   # re-check every 6h → at most one snapshot per day


try:
    threading.Thread(target=_nova_nightly_backup, daemon=True).start()
except Exception:
    pass


# Serialize all writes to the shared store so concurrent edits can't interleave.
_NOVA_LOCK = threading.Lock()


def _nova_load():
    path = NOVA_ADMIN_DB()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"agents": [], "deals": [], "expenses": []}


def _nova_write(data):
    path = NOVA_ADMIN_DB()
    if os.path.exists(path):
        try:
            import shutil
            shutil.copy2(path, path + ".bak")
        except Exception:
            pass
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


@app.route("/nova-admins/data", methods=["GET"])
def nova_admins_data():
    """Serve the current shared dataset (agents/deals/expenses) for the live tool."""
    path = NOVA_ADMIN_DB()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return app.response_class(f.read(), mimetype="application/json")
        except Exception:
            pass
    return jsonify({"agents": [], "deals": [], "expenses": []})


@app.route("/nova-admins/save", methods=["POST"])
def nova_admins_save():
    """Replace the WHOLE dataset (used by Import / seeding). Full overwrite by design."""
    data = request.get_json(silent=True) or {}
    if not all(isinstance(data.get(k), list) for k in ("agents", "deals", "expenses")):
        return jsonify({"error": "Expected agents, deals and expenses arrays."}), 400
    if len(json.dumps(data)) > 12_000_000:
        return jsonify({"error": "Payload too large."}), 413
    try:
        with _NOVA_LOCK:
            # tasks/notes survive an Import from an older export that lacks them
            existing = _nova_load()
            clean = {"agents": data["agents"], "deals": data["deals"], "expenses": data["expenses"],
                     "tasks": data.get("tasks", existing.get("tasks", [])),
                     "notes": data.get("notes", existing.get("notes", []))}
            _nova_write(clean)
        return jsonify({"ok": True, "deals": len(clean["deals"]), "expenses": len(clean["expenses"])})
    except Exception as e:
        return jsonify({"error": str(e)[:160]}), 500


@app.route("/nova-admins/mutate", methods=["POST"])
def nova_admins_mutate():
    """Row-level write: upsert or delete ONE deal/agent/expense by id, merged into the
    shared store under a lock. Concurrent edits to different rows never clobber."""
    body = request.get_json(silent=True) or {}
    try:
        with _NOVA_LOCK:
            data = _nova_load()
            for coll, key in (("deals", "deal"), ("agents", "agent"), ("expenses", "expense"), ("tasks", "task"), ("notes", "note")):
                item = body.get(key)
                if isinstance(item, dict):
                    arr = data.setdefault(coll, [])
                    for i, x in enumerate(arr):
                        if x.get("id") == item.get("id"):
                            arr[i] = item
                            break
                    else:
                        arr.append(item)
                delk = "delete" + key[0].upper() + key[1:]
                if delk in body:
                    data[coll] = [x for x in data.get(coll, []) if x.get("id") != body[delk]]
            _nova_write(data)
            return jsonify({"ok": True, "deals": len(data.get("deals", []))})
    except Exception as e:
        return jsonify({"error": str(e)[:160]}), 500


@app.route("/toolbox")
def toolbox():
    return send_file(os.path.join(BASE_DIR, "toolbox.html"))


@app.route("/toolbox/pdf")
def toolbox_pdf_page():
    return send_file(os.path.join(BASE_DIR, "toolbox_pdf.html"))


@app.route("/toolbox/rx")
def toolbox_rx_page():
    return send_file(os.path.join(BASE_DIR, "toolbox_rx.html"))


# ---------------------------------------------------------------------------
# Aletheya Toolbox · PDF Filler
# Reads a fillable PDF (AcroForm) template, fills its named fields, and exports.
# Three ways in: type values, AI-parse pasted text, or batch from a spreadsheet.
# ---------------------------------------------------------------------------

def _pdf_field_info(reader):
    """Return a clean list of the template's form fields for the UI."""
    out = []
    fields = reader.get_fields() or {}
    for name, f in fields.items():
        ftype = f.get("/FT")
        kind = {"/Tx": "text", "/Btn": "checkbox", "/Ch": "choice", "/Sig": "signature"}.get(ftype, "text")
        info = {"name": name, "type": kind}
        # Checkbox/radio: surface the "on" state(s) so we know what value turns it on.
        states = f.get("/_States_")
        if states:
            info["states"] = [str(s) for s in states]
        # Dropdown / list options.
        opts = f.get("/Opt") or f.get("/_States_")
        if kind == "choice" and opts:
            info["options"] = [str(o[1]) if isinstance(o, (list, tuple)) else str(o) for o in opts]
        cur = f.get("/V")
        if cur is not None:
            info["value"] = str(cur)
        out.append(info)
    return out


def _fill_pdf(template_bytes, values):
    """Fill every page's form fields with `values` (name -> value) and return bytes."""
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(io.BytesIO(template_bytes))
    writer = PdfWriter()
    writer.append(reader)
    # Coerce booleans to the checkbox "on" state where we can detect it.
    fields = reader.get_fields() or {}
    clean = {}
    for k, v in values.items():
        if k not in fields:
            continue
        f = fields[k]
        if f.get("/FT") == "/Btn":
            states = [str(s) for s in (f.get("/_States_") or [])]
            on = next((s for s in states if s not in ("/Off", "Off")), "/Yes")
            if isinstance(v, bool):
                clean[k] = on if v else "/Off"
            elif str(v).strip().lower() in ("1", "true", "yes", "x", "on", "checked", "✓"):
                clean[k] = on
            elif str(v).strip().lower() in ("0", "false", "no", "off", "", "unchecked"):
                clean[k] = "/Off"
            else:
                clean[k] = str(v)
        else:
            clean[k] = "" if v is None else str(v)
    for page in writer.pages:
        try:
            writer.update_page_form_field_values(page, clean, auto_regenerate=False)
        except Exception:
            pass
    # Make viewers render the filled values without re-saving.
    try:
        writer.set_need_appearances_writer(True)
    except Exception:
        pass
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@app.route("/toolbox/pdf-fields", methods=["POST"])
def toolbox_pdf_fields():
    """Inspect an uploaded PDF template and return its fillable fields."""
    f = request.files.get("template")
    if not f:
        return jsonify({"error": "No PDF uploaded."}), 400
    try:
        from pypdf import PdfReader
        data = f.read()
        reader = PdfReader(io.BytesIO(data))
        fields = _pdf_field_info(reader)
    except Exception as e:
        return jsonify({"error": f"Couldn't read that PDF: {e}"}), 400
    if not fields:
        return jsonify({"fields": [], "message": "This PDF has no fillable form fields. Use a PDF with form fields (AcroForm) made in Acrobat or similar."})
    return jsonify({"fields": fields, "pages": len(reader.pages)})


@app.route("/toolbox/pdf-fill", methods=["POST"])
def toolbox_pdf_fill():
    """Fill a single PDF from a JSON map of field values and return the PDF."""
    f = request.files.get("template")
    if not f:
        return jsonify({"error": "No PDF uploaded."}), 400
    try:
        values = json.loads(request.form.get("values", "{}"))
    except Exception:
        return jsonify({"error": "Bad values payload."}), 400
    try:
        out = _fill_pdf(f.read(), values or {})
    except Exception as e:
        return jsonify({"error": f"Couldn't fill the PDF: {e}"}), 500
    name = (request.form.get("filename") or "filled").strip() or "filled"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return send_file(io.BytesIO(out), mimetype="application/pdf",
                     as_attachment=True, download_name=name)


@app.route("/toolbox/pdf-parse", methods=["POST"])
def toolbox_pdf_parse():
    """AI-map free-form pasted text onto the template's field names."""
    if not API_KEY or API_KEY == "sk-your-key-here":
        return jsonify({"error": "OPENAI_API_KEY not configured on the server."}), 500
    data = request.json or {}
    fields = data.get("fields") or []
    text = (data.get("text") or "").strip()
    if not fields:
        return jsonify({"error": "No template fields provided."}), 400
    if not text:
        return jsonify({"error": "Paste some text to parse."}), 400
    # Describe the fields so the model knows the exact keys to emit.
    lines = []
    for f in fields:
        d = f"- {f['name']} ({f.get('type','text')}"
        if f.get("options"):
            d += "; options: " + ", ".join(f["options"])
        elif f.get("states"):
            d += "; on-state: " + (f["states"][0] if f["states"] else "/Yes")
        d += ")"
        lines.append(d)
    field_list = "\n".join(lines)
    prompt = (
        "You map free-form information onto a fixed set of PDF form fields.\n"
        "Return ONLY a JSON object whose keys are EXACT field names from the list below.\n"
        "Only include a key when you can confidently determine its value from the text; "
        "omit fields you cannot fill. For checkboxes, use true/false. For dropdowns/choices, "
        "use one of the listed options verbatim. Do not invent data.\n\n"
        f"FIELDS:\n{field_list}\n\nTEXT:\n{text}"
    )
    try:
        client = OpenAI(api_key=API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        out = json.loads(resp.choices[0].message.content)
    except Exception as e:
        return jsonify({"error": f"AI parse failed: {e}"}), 500
    names = {f["name"] for f in fields}
    values = {k: v for k, v in out.items() if k in names}
    return jsonify({"values": values})


def _read_spreadsheet(file_storage):
    """Parse an uploaded CSV or XLSX into (headers, list-of-row-dicts)."""
    name = (file_storage.filename or "").lower()
    raw = file_storage.read()
    rows = []
    if name.endswith(".xlsx") or name.endswith(".xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        ws = wb.active
        grid = [[("" if c is None else c) for c in r] for r in ws.iter_rows(values_only=True)]
    else:
        text = raw.decode("utf-8-sig", "ignore")
        grid = list(csv.reader(io.StringIO(text)))
    grid = [r for r in grid if any(str(c).strip() for c in r)]
    if not grid:
        return [], []
    headers = [str(h).strip() for h in grid[0]]
    for r in grid[1:]:
        row = {headers[i]: (str(r[i]).strip() if i < len(r) and r[i] is not None else "")
               for i in range(len(headers))}
        rows.append(row)
    return headers, rows


@app.route("/toolbox/pdf-batch", methods=["POST"])
def toolbox_pdf_batch():
    """Fill the template once per spreadsheet row; return a zip of PDFs.

    Spreadsheet column headers are matched to PDF field names (exact, then
    case-insensitive). An optional 'filename' column names each output PDF.
    """
    tpl = request.files.get("template")
    sheet = request.files.get("sheet")
    if not tpl or not sheet:
        return jsonify({"error": "Upload both a PDF template and a spreadsheet."}), 400
    template_bytes = tpl.read()
    try:
        from pypdf import PdfReader
        field_names = list((PdfReader(io.BytesIO(template_bytes)).get_fields() or {}).keys())
    except Exception as e:
        return jsonify({"error": f"Couldn't read the PDF template: {e}"}), 400
    if not field_names:
        return jsonify({"error": "The PDF template has no fillable form fields."}), 400
    try:
        headers, rows = _read_spreadsheet(sheet)
    except Exception as e:
        return jsonify({"error": f"Couldn't read the spreadsheet: {e}"}), 400
    if not rows:
        return jsonify({"error": "The spreadsheet has no data rows."}), 400
    # Map headers -> field names (exact, else case-insensitive).
    lower = {fn.lower(): fn for fn in field_names}
    colmap = {}
    for h in headers:
        if h in field_names:
            colmap[h] = h
        elif h.lower() in lower:
            colmap[h] = lower[h.lower()]
    if not colmap:
        return jsonify({"error": "No spreadsheet columns matched the PDF field names. "
                                 "Make the column headers match the field names exactly. "
                                 f"PDF fields: {', '.join(field_names)}"}), 400
    base = (request.form.get("filename") or "filled").strip() or "filled"
    zbuf = io.BytesIO()
    used = set()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
        for i, row in enumerate(rows, 1):
            values = {colmap[h]: row[h] for h in colmap if row.get(h, "") != ""}
            try:
                pdf = _fill_pdf(template_bytes, values)
            except Exception:
                continue
            fn = (row.get("filename") or row.get("Filename") or f"{base}-{i}").strip()
            fn = re.sub(r"[^\w.\- ]+", "", fn) or f"{base}-{i}"
            if not fn.lower().endswith(".pdf"):
                fn += ".pdf"
            if fn in used:
                fn = f"{fn[:-4]}-{i}.pdf"
            used.add(fn)
            z.writestr(fn, pdf)
    zbuf.seek(0)
    return send_file(zbuf, mimetype="application/zip",
                     as_attachment=True, download_name=f"{base}-batch.zip")


# ---------------------------------------------------------------------------
# Aletheya Toolbox · RX Update (Medical / Psychiatric Update) generator
# ---------------------------------------------------------------------------

@app.route("/toolbox/doctors")
def toolbox_doctors():
    """The provider directory — used to populate the doctor picker."""
    out = []
    for i, d in enumerate(rx_form.DOCTORS):
        out.append({"index": i, "label": rx_form.doctor_label(d), **d})
    return jsonify({"doctors": out})


@app.route("/toolbox/rx-parse", methods=["POST"])
def toolbox_rx_parse():
    """Read a chart screenshot and/or pasted text into structured RX-Update data."""
    if not API_KEY or API_KEY == "sk-your-key-here":
        return jsonify({"error": "OPENAI_API_KEY not configured on the server."}), 500
    data = request.json or {}
    text = (data.get("text") or "").strip()
    images = data.get("images") or []          # list of data URLs
    instructions = (data.get("instructions") or "").strip()
    if not text and not images:
        return jsonify({"error": "Add a screenshot or some text to parse."}), 400

    sys = (
        "You extract patient data from an Adult Day Health Care chart (e.g. TurboADHC "
        "Plan of Care) for a Medical/Psychiatric Update fax. Return ONLY a JSON object "
        "with these keys:\n"
        '  patient_name (string, "First Last"),\n'
        "  dob (string, MM/DD/YYYY),\n"
        "  diagnoses (array of {name, icd}) — use the ICD-10 code exactly as shown,\n"
        "  medications (array of strings — full sig if shown, e.g. 'Aspirin 81 mg QD PO'),\n"
        "  significant_events (string, may be empty).\n"
        "Read carefully from the image(s) and text. Do not invent data — omit what you can't read. "
        "If the user gives instructions (e.g. remove or add a medication, fix a name), follow them."
    )
    user_content = []
    parts = []
    if text:
        parts.append("SOURCE TEXT:\n" + text)
    if instructions:
        parts.append("INSTRUCTIONS:\n" + instructions)
    if not parts:
        parts.append("Extract everything you can from the attached image(s).")
    user_content.append({"type": "text", "text": "\n\n".join(parts)})
    for url in images[:6]:
        if isinstance(url, str) and url.startswith("data:image"):
            user_content.append({"type": "image_url", "image_url": {"url": url}})

    try:
        client = OpenAI(api_key=API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "system", "content": sys},
                      {"role": "user", "content": user_content}],
            response_format={"type": "json_object"},
        )
        out = json.loads(resp.choices[0].message.content)
    except Exception as e:
        return jsonify({"error": f"AI parse failed: {e}"}), 500

    # Normalize shape.
    result = {
        "patient_name": str(out.get("patient_name") or "").strip(),
        "dob": str(out.get("dob") or "").strip(),
        "diagnoses": [],
        "medications": [],
        "significant_events": str(out.get("significant_events") or "").strip(),
    }
    for dx in (out.get("diagnoses") or []):
        if isinstance(dx, dict):
            name = str(dx.get("name") or dx.get("diagnosis") or "").strip()
            icd = str(dx.get("icd") or dx.get("icd_code") or dx.get("code") or "").strip()
        else:
            name, icd = str(dx).strip(), ""
        if name or icd:
            result["diagnoses"].append({"name": name, "icd": icd})
    for m in (out.get("medications") or []):
        m = (m if isinstance(m, str) else str(m.get("name", "")) if isinstance(m, dict) else str(m)).strip()
        if m:
            result["medications"].append(m)
    return jsonify(result)


@app.route("/toolbox/rx-export", methods=["POST"])
def toolbox_rx_export():
    """Render the RX Update to PDF or Word from the structured data."""
    data = request.json or {}
    fmt = (data.get("format") or "pdf").lower()
    payload = data.get("data") or {}
    try:
        if fmt == "docx":
            blob = rx_form.render_rx_docx(payload)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ext = ".docx"
        else:
            blob = rx_form.render_rx_pdf(payload)
            mime = "application/pdf"
            ext = ".pdf"
    except Exception as e:
        return jsonify({"error": f"Couldn't build the document: {e}"}), 500
    base = (data.get("filename") or "").strip()
    if not base:
        pn = (payload.get("patient_name") or "RX-Update").strip().replace(" ", "-")
        base = f"RX-Update-{pn}" if pn else "RX-Update"
    base = re.sub(r"[^\w.\-]+", "", base) or "RX-Update"
    if base.lower().endswith(ext):
        base = base[:-len(ext)]
    return send_file(io.BytesIO(blob), mimetype=mime, as_attachment=True, download_name=base + ext)


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


@app.route("/review-parse", methods=["POST"])
def review_parse():
    """Smart-fill: read a raw review pasted from Google/Yelp and pull out the reviewer
    name, star rating, source, and a clean version of the text for an Instagram graphic."""
    if not API_KEY or API_KEY == "sk-your-key-here":
        return jsonify({"error": "OPENAI_API_KEY not configured on the server."}), 500
    text = ((request.json or {}).get("text") or "").strip()
    if not text:
        return jsonify({"error": "Paste a review first."}), 400
    schema = {
        "type": "object", "additionalProperties": False,
        "required": ["name", "rating", "source", "review", "vehicle"],
        "properties": {
            "name": {"type": "string"},
            "rating": {"type": "integer"},
            "source": {"type": "string"},
            "review": {"type": "string"},
            "vehicle": {"type": "string"},
        },
    }
    system = (
        "You read a customer review copied from Google, Yelp, DealerRater, or Cars.com and structure "
        "it for a social-media testimonial graphic. Output: name (the reviewer's name or first name + "
        "last initial like 'John D.'; '' if unknown), rating (1-5 integer; if not stated, 5), source "
        "(Google / Yelp / DealerRater / Cars.com / '' if unknown), review (clean the text up for a "
        "post: fix obvious typos/caps, trim filler, keep it authentic and in the customer's voice, no "
        "longer than ~320 characters; do NOT invent content), and vehicle (the car they bought if "
        "mentioned, e.g. '2024 BMW X5'; else '')."
    )
    try:
        client = OpenAI(api_key=API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
            response_format={"type": "json_schema", "json_schema": {"name": "review", "strict": True, "schema": schema}},
        )
        out = json.loads(resp.choices[0].message.content)
        r = out.get("rating") or 5
        out["rating"] = max(1, min(5, int(r) if str(r).isdigit() else 5))
        return jsonify(out)
    except Exception as e:
        return jsonify({"error": f"Couldn't read that review: {e}"}), 502


@app.route("/reviews-parse", methods=["POST"])
def reviews_parse():
    """Bulk smart-fill: split a paste of SEVERAL reviews into a structured list, one
    object per review, for batch testimonial graphics."""
    if not API_KEY or API_KEY == "sk-your-key-here":
        return jsonify({"error": "OPENAI_API_KEY not configured on the server."}), 500
    text = ((request.json or {}).get("text") or "").strip()
    if not text:
        return jsonify({"error": "Paste some reviews first."}), 400
    review_obj = {
        "type": "object", "additionalProperties": False,
        "required": ["name", "rating", "source", "review", "vehicle"],
        "properties": {
            "name": {"type": "string"}, "rating": {"type": "integer"},
            "source": {"type": "string"}, "review": {"type": "string"}, "vehicle": {"type": "string"},
        },
    }
    schema = {"type": "object", "additionalProperties": False, "required": ["reviews"],
              "properties": {"reviews": {"type": "array", "items": review_obj}}}
    system = (
        "You read a block of text that contains ONE OR MORE customer reviews (copied from Google, Yelp, "
        "DealerRater, or Cars.com — possibly several stacked together) and split them into a list. For "
        "EACH distinct review output: name (reviewer's name or first name + last initial like 'John D.'; "
        "'' if unknown), rating (1-5 integer; 5 if not stated), source (Google / Yelp / DealerRater / "
        "Cars.com / '' if unknown), review (cleaned up for a post: fix typos/caps, trim filler, keep it "
        "authentic and in the customer's voice, ≤320 chars; do NOT invent content), and vehicle (the car "
        "if mentioned, e.g. '2024 BMW X5'; else ''). Do not merge separate reviews; do not fabricate reviews."
    )
    try:
        client = OpenAI(api_key=API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
            response_format={"type": "json_schema", "json_schema": {"name": "reviews", "strict": True, "schema": schema}},
        )
        out = json.loads(resp.choices[0].message.content)
        rows = out.get("reviews") or []
        for r in rows:
            v = r.get("rating") or 5
            r["rating"] = max(1, min(5, int(v) if str(v).isdigit() else 5))
        return jsonify({"reviews": rows})
    except Exception as e:
        return jsonify({"error": f"Couldn't read those reviews: {e}"}), 502


@app.route("/review-caption", methods=["POST"])
def review_caption():
    """Write an Instagram caption + hashtags for a customer-review repost."""
    if not API_KEY or API_KEY == "sk-your-key-here":
        return jsonify({"error": "OPENAI_API_KEY not configured on the server."}), 500
    d = request.json or {}
    review = (d.get("review") or "").strip()
    name = (d.get("name") or "").strip()
    rating = d.get("rating") or 5
    vehicle = (d.get("vehicle") or "").strip()
    source = (d.get("source") or "").strip()
    if not review:
        return jsonify({"error": "Add the review text first."}), 400
    prompt = (
        "Write a short, warm Instagram caption for a luxury car dealership, NovAuto, that is "
        "RESHARING a happy customer's review/testimonial.\n"
        f"Reviewer: {name or 'a happy customer'}. Rating: {rating}/5 stars"
        + (f" on their {vehicle}" if vehicle else "")
        + (f". Left on {source}" if source else "") + ".\n"
        f'The review: "{review}"\n'
        "Tone: grateful, celebratory, upscale, authentic. Thank the customer and warmly invite others in. "
        "1-3 short sentences with 1-2 tasteful emojis. Then a blank line, then a line of 8-12 relevant "
        "hashtags (mix brand, local car-buying/dealership, and review/testimonial tags). Do NOT wrap the "
        "caption in quotation marks. Vary the wording each time."
    )
    try:
        client = OpenAI(api_key=API_KEY)
        resp = client.responses.create(model="gpt-4.1-mini", input=prompt)
        text = (getattr(resp, "output_text", "") or "").strip()
        return jsonify({"caption": text})
    except Exception as e:
        info = classify_error(e)
        return jsonify({"error": info["detail"] or info["reason"], "reason": info["reason"]}), info["status"]


def _carsxe_dataurl(url, tries=3, timeout=20):
    """Fetch an image and return it as a data URL. The photo CDN can be slow and some
    hosts reject bare requests, so send browser-like headers and retry before giving up."""
    last = None
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*,*/*;q=0.8",
        "Referer": "https://api.carsxe.com/",
    }
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                ctype = r.headers.get("Content-Type", "image/png")
                b = r.read()
            return f"data:{ctype};base64," + base64.b64encode(b).decode()
        except Exception as e:
            last = e
    raise last


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
    model = _carsxe_base_model(data.get("model", "").strip())   # "Sorento Hybrid" -> "Sorento" for the catalog
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


def _carsxe_canon(make, model, year, trim):
    """Resolve messy make/model/trim against CarsXE /v1/ymm 'bestMatch' so the Deal
    Hub can snap a dealer's free-text car to the manufacturer's official spelling.
    Returns {found, make, model, trim, name, keys} — '' for any field it can't read.
    'keys' lists the bestMatch field names so we can adjust the field-picking if
    CarsXE names things differently than expected."""
    params = {"key": CARSXE_API_KEY, "make": make, "model": model, "format": "json"}
    if year:
        params["year"] = year
    if trim:
        params["trim"] = trim
    url = "https://api.carsxe.com/v1/ymm?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as e:
        return {"found": False, "error": str(e)[:140]}
    best = body.get("bestMatch") or body.get("data") or {}
    if not isinstance(best, dict):
        best = {}
    attrs = best.get("attributes") if isinstance(best.get("attributes"), dict) else {}

    def pick(*names):
        for src in (best, attrs):
            for n in names:
                v = src.get(n)
                if isinstance(v, str) and v.strip():
                    return v.strip()
                if isinstance(v, (int, float)):
                    return str(v)
        return ""

    keys = list(best.keys())[:30] + (["attributes." + k for k in list(attrs.keys())[:25]] if attrs else [])
    try:
        raw = json.dumps(best, default=str)[:2000]
    except Exception:
        raw = str(best)[:2000]
    return {
        "found": bool(best),
        "make": pick("make", "make_name", "manufacturer", "brand"),
        "model": pick("model", "model_name"),
        "trim": pick("trim", "trim_name", "trim_level", "trim_description", "style", "style_name"),
        "name": pick("name", "full_name", "vehicle", "description", "vehicle_name"),
        "keys": keys,
        "body_keys": list(body.keys())[:20],   # where the canonical fields actually live, for diagnosis
        "raw": raw,                            # the full bestMatch object so we can see real field names/values
    }


@app.route("/carsxe-canon", methods=["POST"])
def carsxe_canon():
    """Batch name-cleanup: snap each {year,make,model,trim} to CarsXE's official
    spelling. Bounded + cached so one request can't run forever or re-hit the API."""
    if not CARSXE_API_KEY:
        return jsonify({"error": "CARSXE_API_KEY is not set on the server."}), 500
    data = request.json or {}
    cars = data.get("cars") or []
    if not isinstance(cars, list) or not cars:
        return jsonify({"results": []})
    capped = len(cars) > 40
    out = []
    for c in cars[:40]:
        make = (c.get("make") or "").strip()
        model = (c.get("model") or "").strip()
        year = str(c.get("year") or "").strip()
        trim = (c.get("trim") or "").strip()
        if not (make and model):
            out.append({"in": c, "found": False})
            continue
        mkey = "|".join([year, make.lower(), model.lower(), trim.lower()])
        res = _CARSXE_CANON_CACHE.get(mkey)
        if res is None:
            res = _carsxe_canon(make, model, year, trim)
            if res.get("found"):
                _cache_put(_CARSXE_CANON_CACHE, mkey, res)
        out.append({"in": c, **res})
    return jsonify({"results": out, "capped": capped})


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
    nocache = bool(data.get("nocache"))              # "get new batch" -> skip the cache, re-query
    if not (make and model):
        return jsonify({"error": "Pick a make and model first."}), 400

    # The model now carries the powertrain for display (e.g. "Sorento Hybrid"), but the
    # image catalog only knows the base model — strip it for the lookup so a hybrid still
    # finds photos.
    q_model = _carsxe_base_model(model)

    key = "|".join([year, make.lower(), q_model.lower(), trim.lower(), color])
    cached = _CARSXE_IMG_CACHE.get(key)
    if cached is not None and not nocache:
        for o in cached.get("options", []):           # keep proxy allow-list warm
            _carsxe_remember(o["url"]); _carsxe_remember(o.get("thumb"))
        return jsonify({**cached, "cached": True})

    base = {"key": CARSXE_API_KEY, "make": make, "model": q_model,
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
        return jsonify({"error": f"Catalog error {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}"}), 502
    except Exception as e:
        return jsonify({"error": f"Catalog request failed: {e}"}), 502

    if not imgs:
        return jsonify({"found": False, "message": body.get("error") or "No images returned by the catalog."})
    for im in imgs:
        _carsxe_remember(im["link"]); _carsxe_remember(im.get("thumbnailLink"))
    options = [{"url": im["link"], "thumb": im.get("thumbnailLink") or im["link"],
                "w": im.get("width"), "h": im.get("height"),
                "transparent": str(im.get("mime", "")).endswith("png")}
               for im in imgs]
    # load the first image that actually downloads (a single slow one shouldn't kill the request);
    # whichever loads becomes image_data, and we float it to the front of the options.
    first, first_url, err = None, None, None
    for im in imgs[:3]:
        try:
            first = _carsxe_dataurl(im["link"]); first_url = im["link"]; break
        except Exception as e:
            err = e
    if first is None:
        return jsonify({"error": f"Couldn't load a catalog image (the photo CDN was slow) — try again: {err}"}), 502
    if first_url and options and options[0]["url"] != first_url:
        options.sort(key=lambda o: 0 if o["url"] == first_url else 1)
    payload = {"found": True, "success": True, "image_data": first,
               "image_url": first_url, "options": options}
    _cache_put(_CARSXE_IMG_CACHE, key, payload)
    return jsonify(payload)


@app.route("/carsxe-proxy", methods=["POST"])
def carsxe_proxy():
    """Proxy a specific catalog image (only catalog/vendor-CDN URLs — no open SSRF)."""
    url = (request.json or {}).get("url", "").strip()
    if not _carsxe_proxy_ok(url):
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
        "POWERTRAIN ('Hybrid', 'PHEV', 'Plug-in', 'Electric', 'EV') is part of the MODEL, not the trim — "
        "append it to the model so it shows on the ad (e.g. 'Kia Sorento Hybrid LX' -> model 'Sorento Hybrid', "
        "trim 'LX'; 'RAV4 Hybrid XLE' -> model 'RAV4 Hybrid', trim 'XLE'). Omit plain 'Gas' (it's the default). "
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
DEAL_FIELDS = ["year", "make", "model", "trim", "package", "msrp", "orig_mo", "das", "term",
               "miles", "tax_in_mo", "broker_fee", "dealer", "notes", "source",
               "active_from", "active_to", "special", "deal_type", "apr", "incentives"]


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


def _default_year(d):
    """Most of our cars are new leases — if a year isn't stated, assume the current model year."""
    if not str(d.get("year") or "").strip():
        d["year"] = "2026"
    return d


def _strip_tax(d):
    """We NEVER keep tax-included figures. Any tax_in_mo is backed out to a pre-tax
    orig_mo (÷1.0975) and cleared — a hard guarantee on top of the model's own instruction."""
    try:
        t = d.get("tax_in_mo")
        if t not in (None, "", "0"):
            tv = float(str(t).replace("$", "").replace(",", "").strip())
            if tv:
                if not d.get("orig_mo"):
                    d["orig_mo"] = str(round(tv / 1.0975, 2))
                d["tax_in_mo"] = ""
    except Exception:
        pass
    return d


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
    # rules used to be a separate field; now the AI also picks adjustments out of the
    # paste itself. Still honored if a caller passes it explicitly.
    rules = (body.get("rules") or "").strip()
    makes = [m for m in (body.get("makes") or []) if isinstance(m, str) and m.strip()][:80]
    today = (body.get("today") or "").strip()
    images = [im for im in (body.get("images") or []) if isinstance(im, str) and im.startswith("data:image")][:8]
    if not text and not images:
        return jsonify({"error": "Paste some deals or attach a flyer first."}), 400
    date_rule = (
        f"- Today is {today}. If a line/list states a validity window ('good through 5/31', "
        "'May specials', 'valid until 6/15', 'expires EOM'), output active_from / active_to as "
        "YYYY-MM-DD. 'May specials' => first..last day of that May. If only an end is given, set "
        "active_to and leave active_from ''. Leave BOTH '' if no dates are mentioned.\n"
    ) if today else ""
    make_rule = (
        "- NORMALIZE 'make' to EXACTLY one entry (matching case) from this canonical list: "
        + ", ".join(makes) + ". Map shorthand/synonyms to it: 'Chevy'->'Chevrolet', "
        "'VW'->'Volkswagen', 'Mercedes'/'Benz'/'MB'->'Mercedes-Benz', 'Range Rover'->'Land Rover', "
        "'Alfa'->'Alfa Romeo'. If a make truly isn't in the list, output your best clean guess.\n"
        "- Clean the 'model' to its standard spelling/casing ('k5'->'K5', 'corolla cross'->'Corolla Cross').\n"
        "- Use the manufacturer's STANDARD spacing for alphanumeric model codes and be CONSISTENT — "
        "always write a given model the same way (e.g. 'IS 350', 'RX 350', 'GLC 300', 'F-150'); never "
        "emit the same vehicle two different ways ('IS 350' on one line, 'IS350' on the next).\n"
    ) if makes else ""
    props = {k: {"type": "string"} for k in DEAL_FIELDS}
    schema = {
        "type": "object", "additionalProperties": False,
        "required": ["kind", "contact", "contact_phone", "contact_email", "deals", "adjust"],
        "properties": {
            "kind": {"type": "string", "enum": ["deals", "adjust"]},
            "contact": {"type": "string"},
            "contact_phone": {"type": "string"},
            "contact_email": {"type": "string"},
            "deals": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": DEAL_FIELDS, "properties": props}},
            "adjust": {
                "type": "object", "additionalProperties": False,
                "required": ["match", "ops", "remove_tax_pct"],
                "properties": {
                    "match": {
                        "type": "object", "additionalProperties": False,
                        "required": ["contact", "year", "make", "model", "trim"],
                        "properties": {k: {"type": "string"} for k in ["contact", "year", "make", "model", "trim"]}},
                    "ops": {
                        "type": "array",
                        "items": {
                            "type": "object", "additionalProperties": False,
                            "required": ["field", "op", "value"],
                            "properties": {
                                "field": {"type": "string", "enum": ["monthly", "das", "broker_fee", "term", "miles", "msrp", "apr"]},
                                "op": {"type": "string", "enum": ["add", "mult", "set"]},
                                "value": {"type": "string"}}}},
                    "remove_tax_pct": {"type": "string"}}},
        },
    }
    system = (
        "You read messy car lease/finance text. FIRST classify it with 'kind':\n"
        "- 'adjust' = an INSTRUCTION to change deals ALREADY saved, with NO new vehicle listings "
        "(e.g. 'decrease all GLA 250 das by $1000', 'lower Diana Santa Monica's monthlies $15', "
        "'Mike: 9.75% tax included'). Output an 'adjust' object and leave 'deals' empty.\n"
        "- 'deals' = an actual list/flyer of one or more vehicles. Output 'deals' and leave "
        "'adjust' empty (match all '', ops []).\n"
        "ADJUST object: 'match' selects WHICH saved deals to change — set any of contact / year / "
        "make / model / trim that the instruction names, leave the rest '' (all-'' = EVERY deal). "
        "'ops' is a list of {field, op, value}: field is monthly|das|broker_fee|term|miles|msrp|apr "
        "(use 'monthly' for the payment, 'das' for down/DAS, 'apr' for finance rate); op is 'add' "
        "(value SIGNED, '-1000' to decrease, '20' to "
        "add), 'mult' (multiply), or 'set' (replace). remove_tax_pct = a tax rate to back OUT of "
        "the monthly when they say tax-included ('9.75% tax included'->'9.75'; plain 'tax included' "
        "with no rate -> '9.75'; else '').\n"
        "  A bare brand name is a MAKE, not a model: 'update all Toyota deals ...' -> match:{make:'Toyota'} (NOT model).\n"
        "  e.g. 'decrease all GLA 250 das by $1000' -> match:{model:'GLA 250'}, ops:[{field:'das',op:'add',value:'-1000'}].\n"
        "  e.g. 'add $500 to every Toyota broker fee' -> match:{make:'Toyota'}, ops:[{field:'broker_fee',op:'add',value:'500'}].\n"
        "  e.g. 'lower Diana's monthlies $15' -> match:{contact:'Diana'}, ops:[{field:'monthly',op:'add',value:'-15'}].\n"
        "For EACH vehicle (kind='deals') output: year, make, model, trim, package (equipment "
        "PACKAGES / options — see rule below), msrp, orig_mo (base "
        "monthly payment), das (due at signing / cash to dealer), term (months), miles (annual "
        "mileage), tax_in_mo (monthly WITH tax, if quoted that way), broker_fee, dealer, notes "
        "(loyalty / conquest / credit tier / any other terms), source (short label for where it "
        "came from), active_from / active_to (validity window, only if stated), special (a "
        "short tag like 'Loaner', '1 of 1', or 'Demo' ONLY if the deal is a loaner / courtesy / "
        "demo / service-loaner / one-off special; else ''), deal_type ('finance' if it's a "
        "incentives (a comma-separated list of QUALIFYING rebates the customer must qualify for: "
        "'Loyalty', 'Conquest', 'AAA', 'College Grad', 'Military', 'First Responder', etc. — use the "
        "canonical name ('AAA', never 'Triple A'), never list the same one twice, and keep these OUT "
        "of notes), deal_type ('finance' if it's a "
        "FINANCE/purchase/loan deal — mentions APR, % financing, 'finance', months-to-own, down "
        "payment — otherwise 'lease'), and apr (the finance APR as a number like '4.9', only for "
        "finance deals; else '').\n"
        "  For a FINANCE deal: orig_mo = the monthly payment, das = the DOWN PAYMENT (cash up "
        "front), term = months, apr = the rate; miles is usually '' (no mileage cap on a purchase).\n"
        "ALSO output top-level 'contact': the single person/broker/dealer the paste is from "
        "(sender at top, signature, or 'from X'). If unsure, ''. Put that name in each row's "
        "'dealer' field too. Also output 'contact_phone' and 'contact_email' if a phone number or "
        "email for that contact appears anywhere in the text (else '').\n"
        "RULES:\n"
        "- If a vehicle's YEAR isn't stated, use '2026' (most of our cars are new leases).\n"
        "- PACKAGES / OPTIONS are NOT part of the car. Keep equipment packages and options "
        "('Convenience Package', 'Premium Package', 'Technology Package', 'Cold Weather Package', "
        "'Shadowline', etc.) in 'package' and OUT of model and trim. model+trim identify the actual "
        "vehicle; trim is the variant/trim level (e.g. 'M Sport', 'xDrive', 'GT-Line', 'Luxury'). "
        "e.g. '2026 BMW 330i Convenience Package' -> make 'BMW', model '330i', trim '', package "
        "'Convenience Package'.\n"
        "- POWERTRAIN ('Hybrid', 'PHEV', 'Plug-in', 'Plug-in Hybrid', 'Electric', 'EV') is part of "
        "the MODEL, not the trim or package — append it to the model so it shows on the ad (clients "
        "must see it's a hybrid). e.g. 'Kia Sorento Hybrid LX' -> model 'Sorento Hybrid', trim 'LX'; "
        "'RAV4 Hybrid XLE' -> model 'RAV4 Hybrid', trim 'XLE'; 'NX 450h+ Luxury' -> model 'NX 450h+', "
        "trim 'Luxury'. OMIT a plain 'Gas' entirely (it's the default): 'RX 350 Gas Premium' -> model "
        "'RX 350', trim 'Premium'. Never put a powertrain word in 'package'.\n"
        "- EXPAND abbreviated trim levels to the full standard name and stay CONSISTENT: 'PREM'->"
        "'Premium', 'Prem Plus'/'PREM+'->'Premium Plus', 'LUX'->'Luxury', 'Ult Lux'->'Ultra Luxury', "
        "'Ltd'->'Limited', 'Plat'->'Platinum', 'Pref'->'Preferred', 'F-Sport'->'F Sport'.\n"
        + make_rule + date_rule +
        "- GLOBAL header terms (e.g. '$2000 Down, 36 Month, 10k Miles, $1000 BF') apply to EVERY "
        "line below — copy them into each row.\n"
        "- ONE car with MULTIPLE cash-down options: if a SINGLE vehicle is quoted as a matrix of "
        "cash-down -> monthly choices at the SAME term/miles (e.g. '$3,500 down=$820/mo, $4,500=$773, "
        "$5,500=$734', often shown side by side), output ONLY ONE deal for that car — the option with "
        "the LOWEST monthly payment (usually the highest cash down). Put that monthly in orig_mo and "
        "its matching cash-down in das. Do NOT create a separate deal per down option (we let the user "
        "re-slide the down on our side).\n"
        "- Different TERMS or different annual MILES for the SAME car ARE separate offers — output a "
        "SEPARATE deal for EACH (e.g. one car shown as '39mo 7500 due $2197/m' AND '24mo 7500 due "
        "$2412/m' = TWO deals). Only the cash-down matrix above (same term, different downs) collapses "
        "to one.\n"
        "- Inline ADJUSTMENT instructions mixed into a deal list ('subtract $15 from each "
        "monthly', 'add my $500 fee') — do the arithmetic on every row; never treat as a vehicle.\n"
        "- PER-IMAGE instructions: attached images are labeled 'Screenshot 1', 'Screenshot 2', … in "
        "order. The text may target them individually ('for the first screenshot add $40 to each "
        "monthly', 'screenshot 2: add a $1000 broker fee', 'second one is from Roji'). Apply each "
        "such instruction ONLY to the deals from that screenshot.\n"
        "- TAX — two OPPOSITE cases, never confuse them:\n"
        "  (a) PLUS tax ('475+ tax', '$475 plus tax', '475 + tax', '475 +tax'): the number is "
        "ALREADY the PRE-TAX payment (tax is added on top, separately). KEEP it as-is in orig_mo. "
        "Do NOT divide.\n"
        "  (b) TAX-INCLUDED ('tax in', 'tax included', 'w/ tax', 'with tax', 'incl tax', 'taxes in'): "
        "the number INCLUDES tax. Back it out — divide by 1.0975 (our 9.75%; or 1+rate/100 if a "
        "different rate is given) — and put the PRE-TAX result in orig_mo.\n"
        "  Either way leave tax_in_mo '' and never mention tax in notes. (We NEVER store a "
        "tax-included number; '+ tax' is NOT tax-included.)\n"
        "- Normalize shorthand to plain numbers (no $ or commas): '3k'->3000, '7.5k'->7500, "
        "'$51k MSRP'->51000, '$289'->289. '13/7500' means term=13, miles=7500.\n"
        "- Leave a field '' if it isn't present.\n"
        f"EXTRA ADJUSTMENT RULES (if any) TO APPLY TO EVERY ROW: {rules or '(none)'}"
    )
    if images:
        # vision: read the deals straight off a flyer screenshot / PDF page(s)
        model = "gpt-4.1"
        user_content = [{"type": "text", "text": text or "Read EVERY car deal from these flyer image(s) and structure them. Capture each vehicle, price, term, miles/down, dealer/contact, and any dates."}]
        for n, im in enumerate(images, 1):
            user_content.append({"type": "text", "text": f"--- Screenshot {n} ---"})
            user_content.append({"type": "image_url", "image_url": {"url": im}})
    else:
        model = "gpt-4.1-mini"
        user_content = text
    try:
        client = OpenAI(api_key=API_KEY)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_content}],
            response_format={"type": "json_schema", "json_schema": {"name": "deals", "strict": True, "schema": schema}},
        )
        out = json.loads(resp.choices[0].message.content)
        deals = [_derive_zero_down(_strip_tax(_default_year(d))) for d in out.get("deals", [])]
        return jsonify({
            "kind": out.get("kind") or "deals",
            "deals": deals,
            "contact": (out.get("contact") or "").strip(),
            "contact_phone": (out.get("contact_phone") or "").strip(),
            "contact_email": (out.get("contact_email") or "").strip(),
            "adjust": out.get("adjust") or {},
        })
    except Exception as e:
        return jsonify({"error": f"Couldn't parse those deals: {e}"}), 502


@app.route("/desk-parse", methods=["POST"])
def desk_parse():
    """Read a dealer lease/finance RATE SHEET (pasted text or a screenshot) into the
    structured program inputs the Desking calculator needs: MSRP, residual, money
    factor / APR, term, miles, acquisition fee, rebates, fees. Picks ONE primary
    program when several term/mileage rows are listed."""
    if not API_KEY or API_KEY == "sk-your-key-here":
        return jsonify({"error": "OPENAI_API_KEY not configured on the server."}), 500
    body = request.json or {}
    text = (body.get("text") or "").strip()
    images = [im for im in (body.get("images") or []) if isinstance(im, str) and im.startswith("data:image")][:6]
    if not text and not images:
        return jsonify({"error": "Paste a rate sheet or attach a screenshot first."}), 400
    fields = ["vehicle", "deal_type", "msrp", "selling_price", "residual_pct",
              "residual_amount", "money_factor", "apr", "term", "miles",
              "acq_fee", "rebate", "fees", "down", "tax_pct", "notes"]
    term_keys = ["term", "residual_pct", "money_factor", "miles"]
    schema = {
        "type": "object", "additionalProperties": False,
        "required": fields + ["terms"],
        "properties": {
            **{k: {"type": "string"} for k in fields if k != "deal_type"},
            "deal_type": {"type": "string", "enum": ["lease", "finance"]},
            "terms": {
                "type": "array",
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": term_keys,
                    "properties": {k: {"type": "string"} for k in term_keys},
                },
            },
        },
    }
    system = (
        "You read a car dealer's LEASE/FINANCE RATE SHEET or program bulletin (the monthly "
        "captive-lender numbers a dealer uses to structure a deal) and extract the inputs a "
        "desking calculator needs. Output ONE program object.\n"
        "FIELDS:\n"
        "- vehicle: 'Year Make Model Trim' if present (e.g. '2026 Toyota RAV4 XLE'); else as much as given.\n"
        "- deal_type: 'lease' if it quotes residual/money factor/MF/lease rate; 'finance' if it quotes "
        "APR/financing/purchase. Default 'lease' when ambiguous but a residual or money factor appears.\n"
        "- msrp: the MSRP / sticker (plain number, no $ or commas).\n"
        "- selling_price: the selling/sale/cap-cost/dealer price ONLY if explicitly given. Rate sheets "
        "usually DON'T have it — leave '' if absent (do NOT guess it from MSRP).\n"
        "- residual_pct: the residual as a percent number ('60', '62.5'). If the sheet gives a residual "
        "DOLLAR amount instead, put that in residual_amount and leave residual_pct '' (we'll compute it).\n"
        "- residual_amount: residual VALUE in dollars if given as a dollar figure; else ''.\n"
        "- money_factor: the lease money factor as a decimal ('0.00150'). If only a lease RATE / lease "
        "APR percent is given, CONVERT it to a money factor by dividing by 2400 ('3.6%' -> '0.00150') "
        "and output that. Else ''.\n"
        "- apr: finance APR as a number ('5.9') for finance deals; else ''.\n"
        "- term: months ('36'). If several terms are listed, PICK 36 if present, otherwise the most "
        "standard / first one.\n"
        "- miles: annual mileage for a lease ('10000'); if several, match the term you picked, preferring "
        "10000 then 12000 then 7500; else ''.\n"
        "- acq_fee: acquisition / bank fee ('650'); else ''.\n"
        "- rebate: total customer rebates / incentives / lease cash as a number; else ''.\n"
        "- fees: doc / other dealer fees as a number; else ''.\n"
        "- down: stated cap-cost-reduction / down payment if any; else ''.\n"
        "- tax_pct: sales-tax rate ONLY if the sheet states one; else '' (caller defaults 9.75).\n"
        "- notes: anything important that doesn't fit (credit tier, region/zone, validity dates, "
        "loyalty/conquest requirement, multiple-term summary). Keep it short; else ''.\n"
        "- terms: if the sheet lists MULTIPLE TERMS (e.g. 24 / 36 / 39 / 48 month) each with their OWN "
        "residual and money factor, output one row PER TERM in this array: {term, residual_pct, "
        "money_factor, miles}. Use the same conversions (residual as %, money factor as a small decimal, "
        "lease-rate% ÷ 2400 -> MF). Use the PRIMARY mileage row for each term (prefer 10k, then 12k, then "
        "7.5k). If a term residual is given only in dollars, convert to % using MSRP. If the sheet shows "
        "only one term (no real curve), output terms = [] (empty). Still fill the single residual_pct / "
        "money_factor / term fields above with the primary (36-month) row.\n"
        "RULES: normalize shorthand to plain numbers ('51k'->51000, '$3,500'->3500, '.0012 MF'->0.0012). "
        "A money factor is a small decimal like 0.00120; never confuse it with APR percent. Leave any "
        "field '' if it isn't present. Output numbers only (no $, %, commas) except 'vehicle' and 'notes'."
    )
    if images:
        model = "gpt-4.1"
        user_content = [{"type": "text", "text": text or "Read the lease/finance program off this rate sheet and extract the desking inputs."}]
        for n, im in enumerate(images, 1):
            user_content.append({"type": "text", "text": f"--- Sheet {n} ---"})
            user_content.append({"type": "image_url", "image_url": {"url": im}})
    else:
        model = "gpt-4.1-mini"
        user_content = text
    try:
        client = OpenAI(api_key=API_KEY)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_content}],
            response_format={"type": "json_schema", "json_schema": {"name": "program", "strict": True, "schema": schema}},
        )
        out = json.loads(resp.choices[0].message.content)
        prog = {k: (out.get(k) or "").strip() if isinstance(out.get(k), str) else out.get(k) for k in fields}
        rows = out.get("terms") if isinstance(out.get("terms"), list) else []
        prog["terms"] = [
            {"term": (r.get("term") or "").strip(), "resid": (r.get("residual_pct") or "").strip(),
             "mf": (r.get("money_factor") or "").strip(), "miles": (r.get("miles") or "").strip()}
            for r in rows if isinstance(r, dict) and (r.get("term") or "").strip()
        ]
        return jsonify({"program": prog})
    except Exception as e:
        return jsonify({"error": f"Couldn't read that rate sheet: {e}"}), 502


LIVE_DEALS_URL = "https://novautousa.com/deals"
_LIVE_DEALS_CACHE = {"at": 0.0, "text": "", "count": 0}

# ---- Concierge Copilot knowledge base (the NovAuto sales guide, etc.) ----
# Two private sources, NEITHER in the public repo:
#   1) COPILOT_KB env var on Railway  ← set it once, no in-app upload needed (preferred)
#   2) the volume file written by the in-app 📚 editor (overrides the env var if used)
COPILOT_KB_FILE = os.path.join(GENERATED_DIR, "copilot_kb.txt")
_COPILOT_KB_CACHE = {"at": 0.0, "text": None}


def _load_copilot_kb(max_age=60):
    now = time.time()
    if _COPILOT_KB_CACHE["text"] is not None and (now - _COPILOT_KB_CACHE["at"] < max_age):
        return _COPILOT_KB_CACHE["text"]
    text = ""
    try:                                                  # in-app editor file wins if present
        with open(COPILOT_KB_FILE, encoding="utf-8") as f:
            text = f.read().strip()
    except Exception:
        text = ""
    if not text:                                          # else the Railway env var
        text = (os.environ.get("COPILOT_KB") or "").strip()
    _COPILOT_KB_CACHE.update(at=now, text=text)
    return text


@app.route("/copilot-kb", methods=["GET", "POST"])
def copilot_kb():
    """Admin (restricted) read/write of the copilot knowledge base. The text lives on
    the volume only — never in the public repo. Injected into the copilot's prompt."""
    if request.method == "POST":
        text = ((request.json or {}).get("text") or "").strip()
        try:
            with open(COPILOT_KB_FILE, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        _COPILOT_KB_CACHE.update(at=0.0, text=None)        # bust cache
        return jsonify({"ok": True, "chars": len(text)})
    return jsonify({"text": _load_copilot_kb(max_age=0)})


def _fetch_live_deals_text(max_age=300):
    """Fetch & cache the live novautousa.com/deals as a compact text block the Broker
    Copilot can read. Cached ~5 min; on failure, returns any stale cache. -> (text, count)."""
    now = time.time()
    if _LIVE_DEALS_CACHE["text"] and (now - _LIVE_DEALS_CACHE["at"] < max_age):
        return _LIVE_DEALS_CACHE["text"], _LIVE_DEALS_CACHE["count"]
    try:
        req = urllib.request.Request(LIVE_DEALS_URL, headers={"User-Agent": "Mozilla/5.0 (NovaCopilot)"})
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read(3_000_000).decode("utf-8", "ignore")
        rows = _extract_inertia_deals(body) or []
        lines = []
        for d in rows:
            veh = " ".join(x for x in [d.get("year", ""), d.get("make", ""), d.get("model", ""), d.get("trim", "")] if x).strip()
            parts = [veh] if veh else []
            if d.get("monthly"):
                parts.append("$" + str(d["monthly"]) + "/mo")
            if d.get("das"):
                parts.append("$" + str(d["das"]) + " due at signing")
            if d.get("term"):
                parts.append(str(d["term"]) + "mo")
            if d.get("slug"):
                parts.append("page: https://novautousa.com/deals/" + urllib.parse.quote(d["slug"], safe=""))
            if parts:
                lines.append("• " + " · ".join(parts))
        text = "\n".join(lines)
        if text:
            _LIVE_DEALS_CACHE.update(at=now, text=text, count=len(lines))
        return text, len(lines)
    except Exception:
        return _LIVE_DEALS_CACHE["text"], _LIVE_DEALS_CACHE["count"]


@app.route("/broker-chat", methods=["POST"])
def broker_chat():
    """Concierge Copilot — a conversational assistant for NovAuto's agents, available
    on every page. Multi-turn; the client sends the running message history. Login-gated
    (every route is) but NOT behind the restricted password, so any agent can use it."""
    if not API_KEY or API_KEY == "sk-your-key-here":
        return jsonify({"error": "OPENAI_API_KEY not configured on the server."}), 500
    body = request.json or {}
    raw = body.get("messages") or []
    clean = []
    for m in raw[-20:]:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            clean.append({"role": role, "content": content[:4000]})
    if not clean or clean[-1]["role"] != "user":
        return jsonify({"error": "Ask a question first."}), 400
    system = (
        "You are 'Concierge Copilot', the in-house AI assistant for NovAuto — a California auto "
        "LEASE & FINANCE concierge that sources and negotiates new cars for clients. "
        "You help NovAuto's concierge agents do their job. Be warm, sharp, and concise — like a seasoned "
        "finance manager mentoring a newer agent. Plain language, short paragraphs, bullets when useful. "
        "Avoid long essays; get to the point and offer to go deeper.\n"
        "You can help with: lease & finance math (money factor, residual, capitalized cost, depreciation + "
        "rent charge, due at signing, APR, amortization), explaining those to clients simply, structuring and "
        "presenting deals, objection handling and talk tracks, lease vs finance, mileage/term tradeoffs, and how "
        "to use the NovAuto toolkit — Deal Hub (live deal board), Desking (deal calculator with a down×term grid, "
        "mileage→residual, a saved program library, and AI rate-sheet parsing), Lease Ad & Sold Posts (marketing "
        "graphics), Review Generator, Invoice Generator, and Deal Proposal.\n"
        "VOICE RULES: ALWAYS call the buyer a 'client', NEVER a 'customer'. The brand motto is "
        "\"Friends Don't Let Friends Overpay.\" Professional but friendly.\n"
        "MATH YOU KNOW: monthly money factor ≈ APR ÷ 2400. Lease monthly = depreciation [(adjusted cap − "
        "residual) ÷ term] + rent charge [(adjusted cap + residual) × money factor], then add CA sales tax on the "
        "payment. Residual is a % of MSRP. More miles/year → lower residual → higher payment. Down payment / "
        "rebates reduce the cap cost. Due at signing = down + first payment + broker fee. Finance: tax the selling "
        "price, finance it, standard amortization. Show the formula and a worked number when it helps.\n"
        "BALLPARK QUICK-REFERENCE (Nova rules of thumb): $1,000 cap reduction ≈ $30/mo less on 36mo (≈ $42/mo on "
        "24mo); $500 cap reduction ≈ $15/mo less on 36mo; every 1% residual drop ≈ $15–20/mo more; a down-payment "
        "change ÷ term = the monthly change ($1k less down ÷ 36 ≈ +$28/mo); MF × 2400 = APR; LA tax: ×1.0975 to add, "
        "÷1.0975 to remove. Every number we give a client is a TRUE OUT-THE-DOOR number — tax, DMV, fees, first "
        "payment, and the Nova concierge fee all included; quote ONE clean DAS and ONE clean monthly.\n"
        "BALLPARK ESTIMATES: If an agent asks roughly what a car leases/finances for and it's NOT pre-negotiated "
        "(not in our live deals), give a useful BALLPARK by (a) using similar cars from our live deals as comps, (b) "
        "applying the rules of thumb above, and (c) your general market knowledge for that segment. ALWAYS label it "
        "as a 'rough ballpark, not a locked quote', state your assumptions (term / miles / DAS), and tell them to "
        "confirm the real number in Desking or by sourcing through Nema. Give a sensible monthly RANGE, not false "
        "precision. Never present an estimate as a firm price.\n"
        "LIVE DEALS: You DO have real-time read access to the deals published on novautousa.com/deals — they're "
        "given to you below. Use them whenever an agent asks what's live / advertised / the best or cheapest deal / "
        "a specific car / what's under a price. Quote the exact advertised monthly, due-at-signing, and term, and "
        "say it's the current advertised number. If a car they ask about isn't in the live list, say it's not "
        "currently advertised on the site.\n"
        "DEAL PAGE LINKS: each live deal below includes its 'page:' link on novautousa.com. When you reference or "
        "recommend a specific live car, ALWAYS include that page link so the agent can send it to the client — this "
        "is Nova's own marketing page (NOT the dealer's listing), so it's safe to share. (The guide's 'never send "
        "the car link' rule is about hiding the DEALER's listing/VIN, not Nova's own site.) Use the exact URL given; "
        "never invent a link.\n"
        "LIMITS: You do NOT know raw manufacturer programs (residual %, money factor, incentives) or a specific "
        "client's file — for those, point them to the Desking program library or the Deal Hub. Never INVENT a "
        "residual %, money factor, or incentive amount. Ask a brief clarifying question if a request is ambiguous. "
        "Keep general guidance only on legal/tax matters.\n"
        "ACTION BUTTONS: when your answer naturally leads the agent to USE a tool, end your message with ONE final "
        "line in EXACTLY this format and nothing after it: [[ACTIONS: key1, key2]] — using only these keys: "
        "desk (open the Desking calculator), quote (build a Deal Proposal), invoice (build an Invoice), deals (open "
        "the Deal Hub), ads (make a lease ad), sold (make a sold post), review (make a review post). Include 1–3 of "
        "the MOST relevant keys (e.g. someone closing a deal → 'quote, invoice'; pricing a car → 'desk'). If no tool "
        "is relevant, OMIT the line entirely. Never mention or explain this line; just append it when useful.\n"
        "DEAL HAND-OFF: when you include a quote/invoice/desk action AND a specific vehicle or deal is in play, ALSO "
        "append ONE more final line in EXACTLY this format (after the ACTIONS line): [[DEAL: {json}]] — a compact "
        "JSON object with any of these STRING fields you actually know from the conversation or live deals: vehicle "
        "('2026 Toyota RAV4 XLE'), dealType ('lease' or 'finance'), monthly, term, das (due at signing or down), "
        "miles, msrp, apr, color, vin, client (the client's first name), notes. Use live-deal numbers for an "
        "advertised car, or your ballpark for an estimate. OMIT fields you don't know — never invent a VIN or MSRP. "
        "This pre-fills the tool for the agent. If no specific car is in play, omit the DEAL line. Never explain it."
    )
    kb = _load_copilot_kb()
    if kb:
        system += ("\n\n=== NOVAUTO PLAYBOOK / SALES GUIDE (internal knowledge — treat as authoritative; "
                   "follow its process, terminology, scripts, and policies when answering) ===\n" + kb[:16000])
    deals_text, deals_n = _fetch_live_deals_text()
    if deals_text:
        system += ("\n\n=== LIVE DEALS on novautousa.com/deals right now (" + str(deals_n) +
                   " vehicles, refreshed within ~5 min) — these are the current client-facing advertised "
                   "numbers ===\n" + deals_text[:7000])
    else:
        system += ("\n\n(Live deals from novautousa.com/deals are momentarily unavailable — if asked about live "
                   "deals, say so and suggest checking the Deal Hub.)")
    try:
        client = OpenAI(api_key=API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "system", "content": system}] + clean,
            temperature=0.5, max_tokens=700,
        )
        reply = (resp.choices[0].message.content or "").strip()
        actions, deal = [], {}
        allowed = {"desk", "quote", "proposal", "invoice", "deals", "ads", "sold", "review"}
        deal_fields = {"vehicle", "dealType", "monthly", "term", "das", "miles", "msrp", "apr", "color", "vin", "client", "notes"}
        # optional [[DEAL: {json}]] → pre-fill payload for the tools
        dm = re.search(r'\[\[\s*DEAL\s*:\s*(\{.*?\})\s*\]\]', reply, re.I | re.S)
        if dm:
            try:
                d = json.loads(dm.group(1))
                if isinstance(d, dict):
                    deal = {k: str(v).strip()[:120] for k, v in d.items()
                            if k in deal_fields and v not in (None, "") and str(v).strip()}
            except Exception:
                deal = {}
        # optional [[ACTIONS: ...]] → smart buttons
        am = re.search(r'\[\[\s*ACTIONS?\s*:\s*([^\]]+)\]\]', reply, re.I)
        if am:
            for k in re.split(r'[,\s]+', am.group(1).strip().lower()):
                if k in allowed and k not in actions:
                    actions.append(k)
        starts = [x.start() for x in (am, dm) if x]
        if starts:
            reply = reply[:min(starts)].rstrip()          # strip the markers from the visible text
        return jsonify({"reply": reply, "actions": actions, "deal": deal})
    except Exception as e:
        return jsonify({"error": f"Couldn't reach the assistant: {e}"}), 502


@app.route("/deal-search", methods=["POST"])
def deal_search():
    """Natural-language filter over the deal list. Given a query and the candidate
    vehicles, an LLM returns the indices that match, best-first."""
    if not API_KEY or API_KEY == "sk-your-key-here":
        return jsonify({"error": "OPENAI_API_KEY not configured on the server."}), 500
    body = request.json or {}
    query = (body.get("query") or "").strip()
    cars = body.get("cars") or []
    if not query or not isinstance(cars, list) or not cars:
        return jsonify({"match": []})
    cars = cars[:400]
    lines = []
    for i, c in enumerate(cars):
        lines.append(
            f"{i}: {c.get('year','')} {c.get('make','')} {c.get('model','')} {c.get('trim','')} "
            f"| type={c.get('type','lease')} mo={c.get('monthly','')} eff={c.get('zero','')} "
            f"down={c.get('das','')} apr={c.get('apr','')} term={c.get('term','')} miles={c.get('miles','')}"
        )
    schema = {
        "type": "object", "additionalProperties": False, "required": ["match"],
        "properties": {"match": {"type": "array", "items": {"type": "integer"}}},
    }
    system = (
        "You are a search filter for a car deal list. Given a natural-language query and a "
        "numbered list of vehicles (type lease|finance, monthly payment, effective monthly, "
        "down/DAS, apr, term months, annual miles), return 'match': the indices of vehicles that "
        "satisfy the query, MOST relevant / best first. Handle lease vs finance ('finance deals', "
        "'lease only'), APR limits ('under 5% apr'). Understand body styles (SUV, sedan, coupe, "
        "truck, wagon), fuel "
        "type (EV / hybrid) from model knowledge, brands and sub-brands ('AMG'=Mercedes-AMG, "
        "'M'/'M3'=BMW M, 'Type R'=Honda, etc.), and numeric limits ('under $500/mo' -> monthly<=500, "
        "'0 down' favors low DAS, 'cheap'/'best' -> lowest 0-down effective). Only use indices from "
        "the list. If nothing matches, return an empty array."
    )
    user = "QUERY: " + query + "\n\nVEHICLES:\n" + "\n".join(lines)
    try:
        client = OpenAI(api_key=API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_schema", "json_schema": {"name": "search", "strict": True, "schema": schema}},
        )
        idx = json.loads(resp.choices[0].message.content).get("match", [])
        keys = [cars[i].get("key") for i in idx if isinstance(i, int) and 0 <= i < len(cars)]
        return jsonify({"keys": keys})
    except Exception as e:
        return jsonify({"error": f"Search failed: {e}"}), 502


@app.route("/deals", methods=["GET", "POST"])
def deals():
    if request.method == "POST":
        incoming = (request.json or {}).get("deals", [])
        if not isinstance(incoming, list):
            return jsonify({"error": "Bad payload."}), 400
        _save_deals(incoming)
        return jsonify({"ok": True, "count": len(incoming)})
    return jsonify({"deals": _load_deals()})


CONTACTS_FILE = os.path.join(GENERATED_DIR, "contacts.json")


@app.route("/contacts", methods=["GET", "POST"])
def contacts():
    if request.method == "POST":
        incoming = (request.json or {}).get("contacts", [])
        if not isinstance(incoming, list):
            return jsonify({"error": "Bad payload."}), 400
        try:
            with open(CONTACTS_FILE, "w") as f:
                json.dump(incoming, f, indent=1)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        return jsonify({"ok": True, "count": len(incoming)})
    try:
        with open(CONTACTS_FILE) as f:
            data = json.load(f)
            return jsonify({"contacts": data if isinstance(data, list) else []})
    except Exception:
        return jsonify({"contacts": []})


PUBLISHED_FILE = os.path.join(GENERATED_DIR, "published.json")


@app.route("/published", methods=["GET", "POST"])
def published():
    """The 'live site' snapshot: best deal per car at the moment the user last pushed.
    The hub diffs current bests against this to flag better / new / expired deals."""
    if request.method == "POST":
        data = request.json or {}
        try:
            with open(PUBLISHED_FILE, "w") as f:
                json.dump(data, f, indent=1)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        return jsonify({"ok": True})
    try:
        with open(PUBLISHED_FILE) as f:
            d = json.load(f)
            return jsonify(d if isinstance(d, dict) else {"snapshot": {}, "at": ""})
    except Exception:
        return jsonify({"snapshot": {}, "at": ""})


INVOICES_FILE = os.path.join(GENERATED_DIR, "invoices.json")


@app.route("/invoices", methods=["GET", "POST"])
def invoices():
    """Saved customer invoices + the auto-increment counter. The client owns the
    list and number; the server just persists it (volume-backed)."""
    if request.method == "POST":
        data = request.json or {}
        rows = data.get("invoices")
        store = {"invoices": rows if isinstance(rows, list) else [],
                 "counter": int(data.get("counter") or 0)}
        try:
            with open(INVOICES_FILE, "w") as f:
                json.dump(store, f, indent=1)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        return jsonify({"ok": True, "count": len(store["invoices"])})
    try:
        with open(INVOICES_FILE) as f:
            d = json.load(f)
            return jsonify({"invoices": d.get("invoices", []), "counter": int(d.get("counter") or 0)})
    except Exception:
        return jsonify({"invoices": [], "counter": 0})


PROGRAMS_FILE = os.path.join(GENERATED_DIR, "programs.json")


@app.route("/desk-programs", methods=["GET", "POST"])
def desk_programs():
    """The Desking program library — saved manufacturer programs (residual, money
    factor, term, fees …) keyed by vehicle. The client owns the list; the server
    just persists it (volume-backed), same as deals/invoices."""
    if request.method == "POST":
        data = request.json or {}
        rows = data.get("programs")
        store = {"programs": rows if isinstance(rows, list) else []}
        try:
            with open(PROGRAMS_FILE, "w") as f:
                json.dump(store, f, indent=1)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        return jsonify({"ok": True, "count": len(store["programs"])})
    try:
        with open(PROGRAMS_FILE) as f:
            d = json.load(f)
            return jsonify({"programs": d.get("programs", [])})
    except Exception:
        return jsonify({"programs": []})


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


# ---- Verify live site: fetch the public deals page so we can reconcile it ----
def _host_is_public(host):
    """True only if every address the host resolves to is a public IP — blocks
    SSRF to localhost / private networks / link-local / cloud metadata."""
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False
    for info in infos:
        try:
            addr = ipaddress.ip_address(info[4][0])
        except Exception:
            return False
        if (addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_reserved or addr.is_multicast or addr.is_unspecified):
            return False
    return bool(infos)


def _extract_inertia_deals(body):
    """The Nova site is an Inertia.js app: the full deal dataset is embedded as
    JSON in the root element's data-page="..." attribute. Pull it straight out as
    structured rows (year/make/model/trim/monthly/das/term) so we don't have to
    AI-parse scraped text. Returns None if the payload isn't present/parseable."""
    m = re.search(r'data-page="([^"]*)"', body)
    if not m:
        return None
    try:
        data = json.loads(_html_unescape(m.group(1)))
    except Exception:
        return None
    cars = None
    try:
        cars = data["props"]["car_data"]["cars"]
    except Exception:
        cars = None
    if not isinstance(cars, list):                       # fall back to a generic search
        found = []
        def walk(o):
            if found:
                return
            if (isinstance(o, list) and o and isinstance(o[0], dict)
                    and ({"deal", "deals"} & set(o[0].keys()))
                    and ({"title", "year", "car_trim"} & set(o[0].keys()))):
                found.append(o); return
            if isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(data)
        cars = found[0] if found else None
    if not isinstance(cars, list):
        return None

    def _mo(d):
        try:
            return float(str(d.get("monthly_payment") or 1e9).replace(",", ""))
        except Exception:
            return 1e9

    rows = []
    for c in cars:
        if not isinstance(c, dict):
            continue
        deal = c.get("deal")
        deals = [d for d in (c.get("deals") or []) if isinstance(d, dict)]
        if not isinstance(deal, dict) and deals:
            deal = sorted(deals, key=_mo)[0]             # cheapest advertised
        if not isinstance(deal, dict):
            continue                                     # listed car with no live deal — skip
        make = model = ""
        try:
            cm = c["car_trim"]["car_model"]
            model = cm.get("name") or ""
            make = (cm.get("car_make") or {}).get("name") or ""
        except Exception:
            pass
        year, title = c.get("year") or "", str(c.get("title") or "")
        if not (make and model) and title:               # parse "2026 Toyota Corolla"
            parts = title.split()
            if parts and parts[0].isdigit():
                year = year or parts[0]; parts = parts[1:]
            if parts:
                make = make or parts[0]
            if len(parts) > 1:
                model = model or " ".join(parts[1:])
        rows.append({
            "year": str(year or ""), "make": make, "model": model,
            "trim": c.get("subtitle") or "",
            "monthly": str(deal.get("monthly_payment") or ""),
            "das": str(deal.get("down_payment") or ""),
            "term": str(deal.get("lease_term_months") or ""),
            "slug": str(c.get("slug") or ""),
        })
    return rows or None


def _html_to_text(h):
    """Crude HTML -> readable text: drop scripts/styles, turn block tags into
    line breaks, strip the rest, decode entities, collapse whitespace."""
    h = re.sub(r'(?is)<(script|style|noscript|head|svg)[^>]*>.*?</\1>', ' ', h)
    h = re.sub(r'(?i)<br\s*/?>', '\n', h)
    h = re.sub(r'(?i)</(p|div|li|tr|h[1-6]|section|article)>', '\n', h)
    h = re.sub(r'(?s)<[^>]+>', ' ', h)
    h = _html_unescape(h)
    h = re.sub(r'[ \t ]+', ' ', h)
    h = re.sub(r'\n[ \t]*\n+', '\n', h)
    return h.strip()


@app.route("/verify-fetch", methods=["POST"])
def verify_fetch():
    """Fetch the client-facing deals page (server-side, so no CORS) and return its
    readable text for the Deal Hub to reconcile against. SSRF-guarded."""
    url = (request.json or {}).get("url", "").strip()
    if not url:
        return jsonify({"error": "Enter the live site URL first."}), 400
    if not re.match(r'^https?://', url, re.I):
        url = "https://" + url
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return jsonify({"error": "That doesn't look like a valid web address."}), 400
    if not _host_is_public(parsed.hostname):
        return jsonify({"error": "That address can't be fetched (private or unreachable host)."}), 400
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (NovaVerify)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            ctype = (r.headers.get_content_type() or "").lower()
            raw = r.read(3_000_000)            # cap at ~3 MB
    except urllib.error.HTTPError as e:
        return jsonify({"error": f"The site returned HTTP {e.code}."}), 502
    except Exception as e:
        return jsonify({"error": f"Couldn't reach the site: {e}"}), 502
    body = raw.decode("utf-8", "ignore")
    rows = _extract_inertia_deals(body)                  # the Nova site embeds its deals as JSON
    if rows:
        return jsonify({"found": True, "rows": rows, "count": len(rows), "source": "live-data", "url": url})
    text = _html_to_text(body) if ("html" in ctype or "<" in body[:300]) else body
    if not text.strip():
        return jsonify({"found": False, "message": "The page loaded but had no readable text (it may be image-only or JS-rendered — use Paste instead)."})
    return jsonify({"found": True, "text": text[:60000], "url": url})


if __name__ == "__main__":
    from waitress import serve
    port = int(os.environ.get("PORT", 5050))
    if not API_KEY or API_KEY == "sk-your-key-here":
        print("WARNING: No API key set. Set OPENAI_API_KEY (env) or add it to .env.")
    print(f"Image generator running at http://localhost:{port}")
    serve(app, host="0.0.0.0", port=port, channel_timeout=300)
