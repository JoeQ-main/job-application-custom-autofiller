# Job Application Custom Autofiller

A small Windows program plus a Firefox extension that fill in job applications on
Indeed, LinkedIn and employer sites from your saved information. Each click on the
extension's toolbar button fills the page you are on, once. Nothing runs on a
timer, and it never clicks Next or Submit for you.

## What is in this folder

| File | What it is |
|---|---|
| `Run Job Application Custom Autofiller.cmd` | Double-click to open the program |
| `job_application_custom_autofiller.py` | The program window |
| `field_rules.py` | The list of fields it recognizes and the label patterns for each |
| `data_store.py` | Saving/loading, cover letter blanks, reading .docx files |
| `local_server.py` | Lets the Firefox extension talk to the program (your computer only, 127.0.0.1) |
| `autofill_data.json` | **All your saved data.** It is a plain text file you can open in Notepad |
| `application_history.csv` | Created on your first **Finished** click: one row per application |
| `firefox_extension\` | The "Job Application Custom Autofiller" Firefox extension |
| `job_application_custom_autofiller.xpi` | The same extension packed into one file, for permanent installs |

## One-time setup

1. **Python.** The program needs Python 3 with Tkinter, which the standard
   python.org installer and Anaconda both include. The launcher finds either one
   by itself.
2. **Load the extension in Firefox.** Pick one option:
   * **A. Temporary load (fastest, works on regular Firefox).** Go to
     `about:debugging`, click **This Firefox**, then **Load Temporary Add-on...**,
     and pick `firefox_extension\manifest.json`. Firefox removes it when it
     restarts, so you repeat this once per Firefox session.
   * **B. Permanent, Firefox Developer Edition or ESR.** In `about:config`, set
     `xpinstall.signatures.required` to `false`. Then open `about:addons`, click
     the gear icon, choose **Install Add-on From File...**, and pick
     `job_application_custom_autofiller.xpi`. Regular Firefox does not allow this setting.
   * **C. Permanent, regular Firefox.** Sign it privately (it is free and stays
     unlisted) at https://addons.mozilla.org/developers/ : choose **Submit a New
     Add-on**, pick **On your own**, and upload `job_application_custom_autofiller.xpi`. Mozilla
     returns a signed .xpi, usually within 24 hours, which you install with
     **Install Add-on From File...**.

   Firefox asks the extension for access to all websites. It needs that because
   Indeed often sends you on to the employer's own site. It only fills the page
   you are on when you click its toolbar button, and never anything else.

## Applying for a job

1. Double-click **Run Job Application Custom Autofiller.cmd**.
2. On **This Application**, enter the company, job title and (if you know it) the
   hiring manager. The cover letter uses these. Fill in "why this company" if you
   want it filled too.
3. Open the application in Firefox. On each page of it, click the
   **Job Application Custom Autofiller** toolbar button. The page is filled once, and the button's
   badge shows how many boxes were filled (a red **!** means the program is not
   running, or the page needs a reload).
4. Click through the application pages yourself, clicking the toolbar button on
   each new page.
5. Questions it doesn't recognize appear on the **Autofill** tab. Double-click
   one, type your answer, and choose whether to keep it for future applications.
   Then click the toolbar button again to fill it.
6. Submit on the website, then click **Finished** in the program. The application
   is logged in `application_history.csv`. Nothing finishes on its own.
7. Before the next job, click **New Application** on the **This Application** tab.

## Good to know

* **It replaces what is already in a box.** Anything the site pre-filled, and
  anything you typed into a box it recognizes, is overwritten with your saved
  answer on every click. The Activity log shows what was replaced. If a page
  has something you want to keep, click the button *before* typing your own
  changes, or save that answer in the program.
* **Kinds of boxes it fills:** text boxes, large text areas, rich-text editors,
  date boxes (save dates like `10/20/2026`), normal drop-down lists, type-ahead
  drop-downs (Greenhouse, Lever, LinkedIn), button-style drop-downs (Workday),
  Yes/No buttons, and check boxes. For a group of check boxes (for example
  shift availability) save a comma-separated answer such as `Days, Weekends`.
  A lone check box whose wording matches a Yes/No field is ticked when your
  answer agrees with it ("Yes" for "I am authorized to work", "No" for "I do
  not require sponsorship"). Lone check boxes are never unticked, and ones it
  does not recognize, such as "I agree", are never touched.
* **Reference boxes** all get the same single reference saved in My Profile;
  fix the second and third ones by hand.
* **`{today}`** in any saved answer becomes the date you click, e.g. `10/13/2026`.
  The "Today's date" field starts with it.
* **Blank fields in My Profile are skipped.** The Activity log tells you which
  ones a page asked for, for example "Desired pay".
* **Yes/No questions and drop-downs**: the saved answer must match one of the
  choices. If none matches, the log lists the choices so you can fix the answer.
  For example, some sites want `PA` instead of `Pennsylvania`.
* **Cover letter blanks**: `{company}`, `{job_title}`, `{hiring_manager}`, `{today}`.
* **Resume upload** is off by default. LinkedIn and Indeed usually have your resume
  saved already, and uploading again adds a duplicate. Turn it on in **Settings**
  for employer sites that need a file.
* **Adding a field.** Add a line to `field_rules.py`. The comments at the top
  explain the format.

## Troubleshooting

| What you see | Cause and fix |
|---|---|
| "No usable Python was found" | Install Python from python.org and tick "Add python.exe to PATH" |
| "Could not start the local server on 127.0.0.1:47321" | The program is already open in another window. Close it. |
| "...autofill_data.json is not valid JSON at line X" | A manual edit broke the file. Fix that line, or rename the file to start over. |
| No toolbar button | The extension isn't loaded (option A has to be repeated after every Firefox restart) |
| Red **!** on the button | The program isn't running, or the page was open before the extension was loaded: reload the page and click again |
| Badge shows **0** | Every recognized box already held your answer, or the page's labels weren't recognized: check the **Autofill** tab |
| A box was filled with the wrong thing | Add a Saved Answer with that question's exact text (saved answers are checked first), then click the button again. Typing over it by hand only lasts until the next click |
| A drop-down was not set | The list's choices must contain your answer. The Activity log lists the choices it saw, so you can match one, e.g. `PA` or `Pennsylvania` both work for states |

Detailed errors from inside the extension appear in Firefox's console
(`about:debugging` → **Inspect** next to Job Application Custom Autofiller, or F12 on the page)
with the prefix `[Job Application Custom Autofiller]`.
