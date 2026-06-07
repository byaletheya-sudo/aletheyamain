"""Aletheya Toolbox · Medical / Psychiatric Update ("RX Update") generator.

The original form is an image-only scan, so we recreate it cleanly and render to
PDF (reportlab) or Word (python-docx) from one structured data dict.

DOCTORS is the provider directory extracted from the clinic's MD list — picking
one fills the Primary Physician section, the "Dear Dr." line, and the fax target.
"""
import io
import os

_BASE = os.path.dirname(os.path.abspath(__file__))
RX_TEMPLATE = os.path.join(_BASE, "toolbox_templates", "rx_update_template.pdf")

# --- Field map for the fillable template (field names are opaque, mapped by position) ---
RX_PDF = {
    "doctor_name": "text_61kklc",   # physician table row1: Name
    "doctor_addr1": "text_63yalm",  # row1: Address (street)
    "doctor_phone": "text_64wqeq",  # row1: Phone
    "doctor_addr2": "text_66naye",  # row2: Address (city, state zip)
    "doctor_fax": "text_65qowa",    # row2: Phone slot -> Fax
    "assess_date": "text_68sjov",   # "...team on ___"
    "patient_name": "text_66zdiz",
    "dob": "text_67dpqx",
    "sig1": "text_69cvyv",          # significant events, line 1 (right of label)
    "sig2": "text_70ysvw",          # significant events, line 2 (full width)
    "date_top": "text_59legf",      # RN "Date"
    "date_md": "text_60deru",       # MD-signature "Date" (left blank per request)
}
# Diagnoses, column-major (down col 1, then col 2, then col 3) — 24 cells.
RX_DX = [
    "text_2ttsg", "text_3rzsp", "text_4ppkg", "text_5pyda", "text_6gait", "text_7je", "text_8gspl", "text_9kdil",
    "text_10umnd", "text_11lzyp", "text_12kptr", "text_13onxo", "text_14wris", "text_15salf", "text_16dnlb", "text_17mzri",
    "text_18evbc", "text_19ymht", "text_20drkd", "text_21ullg", "text_22lrsc", "text_23irld", "text_24wgbc", "text_25eegq",
]
# Medications, column-major — 33 cells.
RX_MED = [
    "text_26upyn", "text_27ktgu", "text_28ooaj", "text_29cwiq", "text_30lunj", "text_31egmz", "text_32iqun", "text_33wlyw", "text_34inzs", "text_35acqi", "text_36ybeg",
    "text_37maci", "text_38pmpz", "text_39vgxf", "text_40skwe", "text_41njza", "text_42tabv", "text_43gbge", "text_44onfy", "text_45qwoy", "text_46abfa", "text_47zphg",
    "text_48bvdw", "text_49odzu", "text_50osal", "text_51vcia", "text_52gekn", "text_53hufi", "text_54qesw", "text_55uosl", "text_56tyrt", "text_57lpbz", "text_58dagc",
]

# Provider directory. Picking one auto-fills the physician section.
DOCTORS = [
    {"first": "Sora", "last": "Lee", "prefix": "", "specialty": "", "company": "Lee Renal Care",
     "addr1": "18370 Burbank Blvd.", "addr2": "Suite 211", "city": "Tarzana", "state": "CA", "zip": "91356",
     "phone": "(747) 201-7444", "fax": "(818) 421-4256", "npi": "1891939237"},
    {"first": "Gemelia", "last": "Aguilera", "prefix": "", "specialty": "MD", "company": "",
     "addr1": "3325 Wilshire Blvd.", "addr2": "Suite 208", "city": "Los Angeles", "state": "CA", "zip": "90010",
     "phone": "(213) 465-2643", "fax": "(213) 232-4944", "npi": "1972616100"},
    {"first": "Kamran", "last": "Kamrava", "prefix": "Dr.", "specialty": "", "company": "",
     "addr1": "6915 Reseda Blvd", "addr2": "", "city": "Reseda", "state": "CA", "zip": "91335",
     "phone": "(818) 343-2121", "fax": "(818) 705-1622", "npi": "1053483800"},
    {"first": "Nicola", "last": "Azar", "prefix": "", "specialty": "MD", "company": "",
     "addr1": "1000 Newbury Rd Ste 265", "addr2": "", "city": "Thousand Oaks", "state": "CA", "zip": "91320",
     "phone": "(818) 914-4366", "fax": "(818) 914-4230", "npi": "1922259787"},
    {"first": "Peiman", "last": "Berdjis", "prefix": "", "specialty": "NP", "company": "",
     "addr1": "6222 Wilshire Blvd Suite 303", "addr2": "", "city": "Los Angeles", "state": "CA", "zip": "90048",
     "phone": "(323) 525-1999", "fax": "(323) 525-1991", "npi": "1326150590"},
    {"first": "Sameh", "last": "Shenouda", "prefix": "Dr.", "specialty": "Nephrologist", "company": "",
     "addr1": "7963 Van Nuys Blvd", "addr2": "#101", "city": "Panorama City", "state": "CA", "zip": "91402",
     "phone": "(818) 988-9818", "fax": "(818) 988-9828", "npi": "1487936902"},
    {"first": "Katherine", "last": "Guardado", "prefix": "", "specialty": "", "company": "",
     "addr1": "18250 Roscoe Blvd Ste 200", "addr2": "", "city": "Northridge", "state": "CA", "zip": "91325",
     "phone": "(818) 721-4800", "fax": "(818) 721-4825", "npi": "1821516535"},
]


def doctor_label(d):
    name = " ".join(x for x in [d.get("first", ""), d.get("last", "")] if x).strip()
    if d.get("specialty"):
        name += f", {d['specialty']}"
    where = d.get("city", "")
    return f"{name}" + (f" — {where}" if where else "")


def doctor_address(d):
    line1 = ", ".join(x for x in [d.get("addr1", ""), d.get("addr2", "")] if x)
    csz = f"{d.get('city','')}, {d.get('state','')} {d.get('zip','')}".strip().strip(",")
    return ", ".join(x for x in [line1, csz] if x).strip().strip(",")


def doctor_name(d):
    n = " ".join(x for x in [d.get("first", ""), d.get("last", "")] if x).strip()
    if d.get("specialty"):
        n += f", {d['specialty']}"
    return n


def doctor_street(d):
    """Street portion only (line 1 + line 2)."""
    return ", ".join(x for x in [d.get("addr1", ""), d.get("addr2", "")] if x).strip().strip(",")


def doctor_csz(d):
    """City, ST ZIP."""
    cs = f"{d.get('city','')}, {d.get('state','')}".strip().strip(",")
    return f"{cs} {d.get('zip','')}".strip()


def dx_text(dx):
    """ICD code first, then the diagnosis title — e.g. 'I10  Essential Primary Hypertension'."""
    icd = (dx.get("icd") or "").strip()
    name = (dx.get("name") or "").strip()
    return (f"{icd}  {name}").strip() if icd else name


def _wrap2(text, first_len=46):
    """Split a string onto two lines at a word boundary (for the 2-line events area)."""
    text = (text or "").strip()
    if len(text) <= first_len:
        return text, ""
    cut = text.rfind(" ", 0, first_len)
    if cut <= 0:
        cut = first_len
    return text[:cut].strip(), text[cut:].strip()


# Static clinic header info (from the form).
CLINIC = {
    "name": "Mountainview Adhc",
    "addr1": "23751 Roscoe Blvd",
    "addr2": "West Hills  CA  913043041",
    "phone": "Phone: (818) 312-0663",
    "fax": "Fax: (818) 716-8030",
    "fax_number": "(818) 716-8030",
    "rn": "Arvin Fekri, RN",
}

DISCLAIMER = (
    "Your patient is currently on one or more of the following treatments: Nursing, PT, OT, "
    "Maintenance, SW, ST, Psych, RD counseling and personal care. All Skilled Treatment care "
    "plans are designed to address mainly chronic issues. If any acute issues arise, we will "
    "ensure to refer them back to you for your immediate attention. In addition, if you wish to "
    "see your clients at your office on a regular basis, please call our Social Work Department "
    "and they will gladly assist you with your needs."
)


def _g(d, *keys, default=""):
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return default


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def render_rx_pdf(data):
    """Fill the real fillable RX-Update template (pixel-exact) from structured data."""
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(RX_TEMPLATE)
    writer = PdfWriter()
    writer.append(reader)

    doc = data.get("doctor") or {}
    vals = {
        RX_PDF["doctor_name"]: doctor_name(doc),
        RX_PDF["doctor_addr1"]: doctor_street(doc),
        RX_PDF["doctor_addr2"]: doctor_csz(doc),
        RX_PDF["doctor_phone"]: _g(doc, "phone"),
        RX_PDF["doctor_fax"]: _g(doc, "fax"),
        RX_PDF["assess_date"]: _g(data, "assess_date"),
        RX_PDF["patient_name"]: _g(data, "patient_name"),
        RX_PDF["dob"]: _g(data, "dob"),
        RX_PDF["date_top"]: _g(data, "date"),
        # RX_PDF["date_md"] intentionally left blank (no date in front of MD signature).
    }

    # Diagnoses — "ICD  Title", column-major into the grid.
    dlist = [dx_text(d) for d in (data.get("diagnoses") or []) if dx_text(d)]
    for fn, val in zip(RX_DX, dlist):
        vals[fn] = val

    # Medications — column-major into the grid.
    mlist = [m.strip() for m in (data.get("medications") or []) if m and m.strip()]
    for fn, val in zip(RX_MED, mlist):
        vals[fn] = val

    # Significant events — wrap across the two lines.
    ln1, ln2 = _wrap2(_g(data, "significant_events"))
    if ln1:
        vals[RX_PDF["sig1"]] = ln1
    if ln2:
        vals[RX_PDF["sig2"]] = ln2

    vals = {k: ("" if v is None else str(v)) for k, v in vals.items()}
    for page in writer.pages:
        try:
            writer.update_page_form_field_values(page, vals, auto_regenerate=False)
        except Exception:
            pass
    try:
        writer.set_need_appearances_writer(True)
    except Exception:
        pass
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------
def render_rx_docx(data):
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

    doc = data.get("doctor") or {}
    document = Document()
    for s in document.sections:
        s.top_margin = Inches(0.5); s.bottom_margin = Inches(0.5)
        s.left_margin = Inches(0.7); s.right_margin = Inches(0.7)

    def para(text="", align=None, bold=False, italic=False, size=10, space_after=2):
        p = document.add_paragraph()
        if align:
            p.alignment = align
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.space_before = Pt(0)
        if text:
            r = p.add_run(text); r.bold = bold; r.italic = italic; r.font.size = Pt(size)
        return p

    # Header — three-cell table for left / center / right
    htab = document.add_table(rows=1, cols=3)
    hc = htab.rows[0].cells
    p = hc[0].paragraphs[0]; r = p.add_run(CLINIC["addr1"] + "\n" + CLINIC["addr2"]); r.font.size = Pt(9)
    p = hc[1].paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(CLINIC["name"]); r.bold = True; r.font.size = Pt(15)
    p2 = hc[1].add_paragraph(); p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p2.add_run("Medical / Psychiatric Update"); r.bold = True; r.font.size = Pt(12)
    p = hc[2].paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p.add_run(CLINIC["phone"] + "\n" + CLINIC["fax"]); r.font.size = Pt(9)

    para("Primary Physician/Psychiatrist", size=10, space_after=2)
    ptab = document.add_table(rows=3, cols=3); ptab.style = "Table Grid"
    hdr = ptab.rows[0].cells
    for i, t in enumerate(["Name", "Address", "Phone"]):
        cp = hdr[i].paragraphs[0]; cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = cp.add_run(t); run.bold = True; run.font.size = Pt(9)
    if doc:
        row1 = ptab.rows[1].cells
        for i, val in enumerate([doctor_name(doc), doctor_street(doc), _g(doc, "phone")]):
            cp = row1[i].paragraphs[0]; run = cp.add_run(val); run.font.size = Pt(9)
        row2 = ptab.rows[2].cells   # city/state/zip under address; fax under phone
        for i, val in enumerate(["", doctor_csz(doc), _g(doc, "fax")]):
            cp = row2[i].paragraphs[0]; run = cp.add_run(val); run.font.size = Pt(9)

    para()
    p = document.add_paragraph(); r = p.add_run("Dear Dr. " + (_g(doc, "last") or "")); r.bold = True; r.font.size = Pt(11)
    para("Your patient will be assessed by Mountainview ADHC multi-disciplinary team on "
         + (_g(data, "assess_date") or "________"), size=10.5)

    p = document.add_paragraph()
    r = p.add_run("Patient Name  "); r.font.size = Pt(11)
    r = p.add_run(_g(data, "patient_name")); r.bold = True; r.font.size = Pt(11)
    r = p.add_run("          Date of Birth:  "); r.font.size = Pt(11)
    r = p.add_run(_g(data, "dob")); r.bold = True; r.font.size = Pt(11)

    para("Thank you so much for your assistance in updating this file!", size=10.5)
    para("If we don't hear back from you within 2 weeks, we will be happy to consider all info as current", size=10)
    para(DISCLAIMER, italic=True, size=8.5, space_after=6)

    dis = "DISALLOW Skilled (check any):    "
    dis += ("☒" if data.get("disallow_pt") else "☐") + " PT     "
    dis += ("☒" if data.get("disallow_ot") else "☐") + " OT     "
    dis += ("☒" if data.get("disallow_st") else "☐") + " ST"
    para(dis, size=10, space_after=6)

    para("Current Diagnosis: (per our records)  Please update using specific ICD codes:", size=10)
    diags = [d for d in (data.get("diagnoses") or []) if d.get("name") or d.get("icd")]
    n = max(len(diags), 6)
    dtab = document.add_table(rows=n, cols=1); dtab.style = "Table Grid"
    for i in range(n):
        dx = diags[i] if i < len(diags) else {}
        c0 = dtab.rows[i].cells[0].paragraphs[0]
        r = c0.add_run(dx_text(dx) if dx else ""); r.font.size = Pt(9)

    para()
    para("Current Medications: (per our records)  Please update or verify:", size=10)
    meds = [m for m in (data.get("medications") or []) if m]
    n = max(len(meds), 8)
    mtab = document.add_table(rows=n, cols=1); mtab.style = "Table Grid"
    for i in range(n):
        cp = mtab.rows[i].cells[0].paragraphs[0]
        r = cp.add_run(meds[i] if i < len(meds) else ""); r.font.size = Pt(9)

    para()
    p = document.add_paragraph(); r = p.add_run("Significant events over the last assessment period (6 months):")
    r.font.size = Pt(9.5)
    para(_g(data, "significant_events"), size=9.5, space_after=10)

    para(f"Please sign and fax this form to RN at Mountainview ADHC @ {CLINIC['fax_number']}. Thank you so much.",
         size=11)
    p = document.add_paragraph(); p.paragraph_format.space_after = Pt(2)
    r = p.add_run(f"This fax sent on behalf of {CLINIC['rn']}"); r.font.size = Pt(10); r.underline = True

    the_date = _g(data, "date")
    p = document.add_paragraph()
    r = p.add_run("Date: "); r.font.size = Pt(10)
    r = p.add_run(the_date or "____________"); r.font.size = Pt(10)

    para(space_after=8)
    p = document.add_paragraph()
    r = p.add_run("MD Signature: ______________________________      Date: ______________")
    r.bold = True; r.font.size = Pt(11)

    out = io.BytesIO(); document.save(out); return out.getvalue()
