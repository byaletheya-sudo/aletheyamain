# Nova Ad Generator — Feature Overview

_The internal marketing toolkit for Nova, built by Aletheya. Live at **nova.byaletheya.com** (password-protected). One Flask app + a single-page front end, deployed on Railway._

---

## What it is

A browser tool that turns vehicle + pricing info into ready-to-post, on-brand marketing images — no designer, no Photoshop. Three tools live in one app, each at its own clean URL:

| Tool | URL | What it does |
|---|---|---|
| **Lease Ad Generator** | `/lease` (and `/`) | Generates a lease ad; the car image is **created by AI** (gpt-image-1) on a transparent background and composited onto the Nova template. |
| **Sold Posts** | `/sold` | Builds Instagram "Just Sold" posts from your own uploaded photos. |
| **Lease Ad — TEST** | `/leasead-test` | Same lease ad, but pulls the **real factory photo** from the Vehicle Databases catalog instead of generating one. This is the most advanced tool. |

You move between them from the drawer menu; each has a real, bookmarkable URL and the browser back/forward buttons work.

---

## Tool 1 — Lease Ad Generator (`/lease`)

- Type the vehicle + an art-directed prompt; **gpt-image-1** renders the car on a transparent background for consistent, repeatable results.
- Editable pricing block: badge, headline, per-month, due-at-signing, term, phone, fine print.
- Composited onto the recreated **Nova template** with the NovAuto logo.
- **Background generator**: AI-generate a custom backdrop for the ad.
- **Photo upload + background removal**: drop in your own car photo; the background is removed in-browser.
- **Gallery**: generated cars are saved server-side and persist (Railway volume) so you can reuse them.
- Exports a **1080×1920** PNG, auto-downloaded.
- **Bulk import**: one ad per line (Tab/`|` delimited) → batch-generate.

## Tool 2 — Sold Posts (`/sold`)

- Instagram "Just Sold" layout built from **your uploaded photos** (one or two-photo hero layouts, 4:5 / square).
- **License-plate cover**: auto-detects the rear plate with a vision model and composites the Nova plate over it (drag / resize / rotate to fine-tune).
- **Photo enhancement** modal: Auto, Brightness, Contrast, Saturation, Warmth.
- Custom backdrop generator, badge pill, caption.
- Native **share sheet** support on mobile (send straight to Instagram).

## Tool 3 — Lease Ad — TEST (`/leasead-test`) ⭐

The flagship. Instead of generating a car, it fetches the **real manufacturer photo** from the Vehicle Databases API and builds the ad around it.

### Vehicle lookup (catalog-driven)
- **Cascading dropdowns**: Year → Make → Model → Trim, each populated **live from the real catalog**, so you can only pick values that exist. No typos, no guessing.
- Picking a model **auto-selects the first trim and auto-builds the ad** — one selection, done.
- All option lists are **cached in-process**, so repeats cost zero API calls.

### The real factory photo
- Pulls the per-color studio photo from the catalog, **removes the background** in-browser, and drops it onto the template.
- **Color picker**: choose any factory color the manufacturer offers — shown with the **real color name** (e.g. "Portimao Blue Metallic") and a **hex swatch**, pulled from the manufacturer's own color data. Where a make uses opaque color codes, it falls back to clean "Color 1 / 2 / 3" numbering.

### Smart trim handling
- **Trim cleanup**: turns raw catalog trims into clean ad copy automatically.
  - Merges the engine letter into the model: `430` + `i Convertible…` → headline **430i**.
  - Abbreviates drivetrain: `Rear Wheel Drive` → **RWD** (+ AWD / FWD / 4WD).
  - Normalizes verbose body types: BMW `Sports Activity Vehicle` → **SUV**.
  - **Never shows transmission** — every car we sell is automatic, so `Automatic` / `Manual` / `8-Speed` / `DCT` etc. are stripped.
  - Example: `i Convertible Rear Wheel Drive Automatic` → headline **430i**, subtitle **Convertible RWD**.

### Layout safety (auto-fit)
- **Dynamic font sizing**: the headline, subtitle, and terms lines shrink to fit the template automatically.
- **Intelligent truncation**: if something is still too long at the minimum size, it ellipsizes — a runaway trim can never break the 1080×1920 layout.

### Form, grouped for clarity
Three clean sections: **Vehicle** (year/make/model/trim/color) · **Deal** (per-month / DAS / term / badge) · **Ad Copy** (auto-filled headline + subtitle).

### Bulk import
- Paste many vehicles (Year | Make | Model | Trim | monthly | DAS | term | body | badge).
- Resumable, with a progress bar, per-row status, and a "do this for all" option when a trim needs a decision.
- Duplicate rows return instantly from cache.

---

## Shared platform features

- **Clean per-tool URLs** with deep-linking, history, and per-tool page titles.
- **Password gate** over the whole app (page + every API route).
- **Persistent gallery** via a Railway volume.
- **In-browser background removal** (`@imgly/background-removal`) — no server round-trip, no quality loss.
- **html2canvas** rendering so the downloaded PNG matches the live preview exactly.

## Security (hardened)

- Secrets are **env-only** (`SECRET_KEY`, `APP_PASSWORD`, `OPENAI_API_KEY`, `VDB_API_KEY`) — no secrets in the public repo.
- Session cookies: **HttpOnly + Secure + SameSite=Lax**.
- Login: **constant-time** password check, **per-IP brute-force throttle**, session reset on login.
- Response **security headers** (anti-clickjacking, no MIME-sniffing, referrer/permissions policy).

## Hosting & deploy

- Flask + waitress on Railway; deploys from GitHub `byaletheya-sudo/aletheyamain` on push.
- Custom domain `nova.byaletheya.com` via Railway Networking + a DNS CNAME.
- Companion **byaletheya.com landing page** (workspace chooser) → links into Nova Tools.

---

## Roadmap — requested, not yet built

These are the bigger visions captured for prioritization. Each is a meaningful build on its own.

### A. "Content production machine" — magical export experience
Turn click → wait → download into a studio:
- Generation **queue** with **progress animations**
- **Thumbnail gallery** of everything built this session
- **Download all** (zip)
- **Instant social share** / **AirDrop** to phone
- **Copy caption** + **copy hashtags** buttons

### B. Intelligent AI enhancements (useful, not gimmicky)
- **AI Trim Cleaner** — an LLM pass for the trims the rule-based cleaner can't fully tidy (the rule-based version already handles the common cases). e.g. `xDrive40i Sports Activity Vehicle` → `X5 xDrive40i SUV`.
- **AI Caption Generator** with selectable tone: **luxury**, **aggressive sales**, **meme**, **TikTok**. (A `/caption` endpoint already exists to build on.)

### C. Mobile-first experience
Most users are on **iPhone / iPad**. Make mobile feel like editing an Instagram story:
- **Full-screen preview**
- **Bottom-sheet controls**
- **Swipe between templates**

---

_Last updated as features ship. This file is the single source of truth for "what does this thing do?"_
