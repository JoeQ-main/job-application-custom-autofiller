"""
data_store.py - Loading, saving and preparing the autofill data.

Everything the program remembers lives in ONE readable file next to this
script:

    autofill_data.json     your profile, saved answers, cover letter, settings
    application_history.csv  one row per application you click "Finished" on

This module also:
  * reads plain text out of a Word .docx file (no extra installs needed),
  * fills the {company}/{job_title}/{hiring_manager} blanks in the cover letter,
  * builds the ordered list of "rules" that the Firefox extension uses to
    decide what to type into each box on the page.
"""

import csv
import json
import os
import re
import zipfile
from datetime import date, datetime
from xml.etree import ElementTree

import field_rules

# Folder that holds this script, the data file and your documents.
APP_FOLDER = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(APP_FOLDER, "autofill_data.json")
HISTORY_FILE = os.path.join(APP_FOLDER, "application_history.csv")


# ---------------------------------------------------------------------------
# Default data (used only if autofill_data.json does not exist yet)
# ---------------------------------------------------------------------------
def make_empty_data():
    """Return a brand-new data dictionary with every known key present."""
    profile = {}
    for key, _label, _pattern, _multi in field_rules.PROFILE_FIELDS:
        if not key.startswith("#"):
            profile[key] = field_rules.DEFAULT_VALUES.get(key, "")

    application = {}
    for key, _label, _pattern, _multi in field_rules.APPLICATION_FIELDS:
        application[key] = ""

    return {
        "profile": profile,
        "application": application,
        # Each answer: {"question": "...", "answer": "...", "scope": "always" | "application"}
        "custom_answers": [],
        "cover_letter": {
            "default_text": "",
            "fill_cover_letter": True,
        },
        "settings": {
            "attach_resume": False,
            "resume_file": "",
            "port": 47321,
        },
    }


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------
def load_data():
    """
    Read autofill_data.json. Any keys missing from the file (for example
    after an update adds a new field) are filled in from make_empty_data(),
    so older data files keep working.

    Raises ValueError with the file name and line number if the JSON is
    damaged (for example after a manual edit with a missing comma).
    """
    data = make_empty_data()
    if not os.path.exists(DATA_FILE):
        return data

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
    except json.JSONDecodeError as err:
        raise ValueError(
            f"Could not read {DATA_FILE}\n"
            f"The file is not valid JSON at line {err.lineno}, column {err.colno}: {err.msg}.\n"
            f"Fix that spot in a text editor, or rename the file to start over."
        ) from err

    # Merge saved values on top of the defaults, one section at a time.
    for section in ("profile", "application", "cover_letter", "settings"):
        data[section].update(saved.get(section, {}))
    data["custom_answers"] = saved.get("custom_answers", [])
    # Settings from older versions that no longer do anything (filling now
    # happens once per click on the Firefox button, on whatever page is open).
    for old_key in ("allowed_sites", "fill_all_sites", "auto_finish_minutes"):
        data["settings"].pop(old_key, None)
    return data


def save_data(data):
    """
    Write the data dictionary to autofill_data.json.
    Writes to a temporary file first, then swaps it in, so a crash halfway
    through can never leave you with a half-written data file.
    """
    temp_path = DATA_FILE + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(temp_path, DATA_FILE)


# ---------------------------------------------------------------------------
# Word document reading
# ---------------------------------------------------------------------------
def read_docx_text(path):
    """
    Return the text of a .docx file, one paragraph per line.
    A .docx is a zip file; the text lives in word/document.xml inside it.
    """
    word_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        with zipfile.ZipFile(path) as docx:
            xml_bytes = docx.read("word/document.xml")
    except FileNotFoundError as err:
        raise ValueError(f"File not found: {path}") from err
    except (zipfile.BadZipFile, KeyError) as err:
        raise ValueError(
            f"{path} is not a readable Word .docx file ({err}). "
            f"If it is an older .doc file, open it in Word and 'Save As' .docx."
        ) from err

    root = ElementTree.fromstring(xml_bytes)
    paragraphs = []
    for paragraph in root.iter(word_ns + "p"):
        pieces = []
        for node in paragraph.iter():
            if node.tag == word_ns + "t" and node.text:
                pieces.append(node.text)
            elif node.tag == word_ns + "tab":
                pieces.append("\t")
            elif node.tag in (word_ns + "br", word_ns + "cr"):
                pieces.append("\n")
        paragraphs.append("".join(pieces))
    return "\n".join(paragraphs)


def cover_letter_from_docx(path):
    """
    Read a cover letter .docx and turn it into a reusable template:
      * puts exactly one blank line between paragraphs (easy to read in
        a web page text box),
      * replaces the greeting name with {hiring_manager}.
    The job-specific sentences are left for you to adjust in the program.
    """
    lines = [line.strip() for line in read_docx_text(path).split("\n")]
    text = "\n\n".join(line for line in lines if line)
    text = re.sub(r"^Dear .+?,", "Dear {hiring_manager},", text, count=1, flags=re.MULTILINE)
    return text


# ---------------------------------------------------------------------------
# Cover letter
# ---------------------------------------------------------------------------
def render_cover_letter(data):
    """
    Return the cover letter text to type into the page, with blanks filled:
      {company}        -> company name    (or "your company")
      {job_title}      -> job title       (or "open")
      {hiring_manager} -> hiring manager  (or "Hiring Manager")
      {today}          -> today's date, e.g. October 10, 2026
    The per-application custom letter wins over the default when not blank.
    """
    app = data["application"]
    template = app.get("cover_letter_override", "").strip()
    if not template:
        template = data["cover_letter"].get("default_text", "")

    replacements = {
        "{company}": app.get("company", "").strip() or "your company",
        "{job_title}": app.get("job_title", "").strip() or "open",
        "{hiring_manager}": app.get("hiring_manager", "").strip() or "Hiring Manager",
        "{today}": date.today().strftime("%B %d, %Y").replace(" 0", " "),
    }
    for blank, value in replacements.items():
        template = template.replace(blank, value)
    return template


# ---------------------------------------------------------------------------
# Rules for the browser extension
# ---------------------------------------------------------------------------
def js_escape(text):
    """Escape text so it can be used literally inside a JavaScript regex."""
    return re.sub(r"([.*+?^${}()|\[\]\\/])", r"\\\1", text)


def normalize_question(text):
    """Lower-case and squeeze spaces, the same way the extension does."""
    return re.sub(r"\s+", " ", text).strip().lower()


def fill_blanks(value):
    """Replace {today} in a saved value with the current date, e.g. 10/13/2026."""
    if "{today}" not in value:
        return value
    today = date.today()
    return value.replace("{today}", f"{today.month}/{today.day}/{today.year}")


def build_rules(data):
    """
    Return the ordered list of rules sent to the extension. Each rule is:
        {"name": ..., "pattern": <JS regex>, "value": ..., "kind": "text" | "file"}
    {today} in any value becomes the current date; {site} is filled in by
    the extension with the site name (Indeed, LinkedIn, ...).

    Order (first match wins):
      1. Answers you typed for THIS application
      2. Answers you saved for ALL applications
      3. Per-application questions (why this company, why a good fit, ...)
      4. Cover letter
      5. Yes/No eligibility and self-identification questions
      6. All other profile fields
      7. Resume file upload (only if turned on in Settings)

    Rules with an empty value are still sent, so the page box counts as
    "recognized - nothing saved yet" instead of "unrecognized".
    """
    rules = []

    # 1 and 2: typed answers. Exact question text -> "contains" match.
    for scope in ("application", "always"):
        for item in data["custom_answers"]:
            if item.get("scope", "always") != scope:
                continue
            question = normalize_question(item.get("question", ""))
            if not question:
                continue
            rules.append({
                "name": f"Saved answer: {item['question'][:60]}",
                "pattern": js_escape(question),
                "value": fill_blanks(item.get("answer", "")),
                "kind": "text",
            })

    # 3: per-application questions.
    for key, label, pattern, _multi in field_rules.APPLICATION_FIELDS:
        if pattern:
            rules.append({"name": label, "pattern": pattern,
                          "value": fill_blanks(data["application"].get(key, "")), "kind": "text"})

    # 4: cover letter.
    letter = render_cover_letter(data) if data["cover_letter"].get("fill_cover_letter") else ""
    rules.append({"name": "Cover letter", "pattern": field_rules.COVER_LETTER_PATTERN,
                  "value": letter, "kind": "text"})

    # 5 and 6: profile fields, priority sections first.
    first_rules = []
    other_rules = []
    current_section = ""
    for key, label, pattern, _multi in field_rules.PROFILE_FIELDS:
        if key.startswith("#"):
            current_section = key
            continue
        rule = {"name": label, "pattern": pattern,
                "value": fill_blanks(data["profile"].get(key, "")), "kind": "text"}
        if current_section in field_rules.SECTIONS_MATCHED_FIRST:
            first_rules.append(rule)
        else:
            other_rules.append(rule)
    rules.extend(first_rules)
    rules.extend(other_rules)

    # 7: resume upload.
    settings = data["settings"]
    if settings.get("attach_resume") and settings.get("resume_file"):
        rules.append({"name": "Resume file", "pattern": field_rules.RESUME_FILE_PATTERN,
                      "value": settings["resume_file"], "kind": "file"})
    return rules


def resume_file_path(data):
    """Full path of the resume file chosen in Settings (relative paths = app folder)."""
    name = data["settings"].get("resume_file", "")
    if not name:
        return ""
    if os.path.isabs(name):
        return name
    return os.path.join(APP_FOLDER, name)


# ---------------------------------------------------------------------------
# Application history
# ---------------------------------------------------------------------------
HISTORY_COLUMNS = ["date_time", "company", "job_title", "sites", "fields_filled", "pages"]


def append_history(data, fields_filled, page_urls):
    """Add one row to application_history.csv (creates it with headers if needed)."""
    is_new_file = not os.path.exists(HISTORY_FILE)
    sites = sorted({re.sub(r"^https?://([^/]+).*$", r"\1", url) for url in page_urls})
    row = {
        "date_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "company": data["application"].get("company", ""),
        "job_title": data["application"].get("job_title", ""),
        "sites": " ".join(sites),
        "fields_filled": fields_filled,
        "pages": " ".join(sorted(page_urls)),
    }
    with open(HISTORY_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_COLUMNS)
        if is_new_file:
            writer.writeheader()
        writer.writerow(row)
