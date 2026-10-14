"""
job_application_custom_autofiller.py - Job Application Custom Autofiller: the program window.

Start it with "Run Job Application Custom Autofiller.cmd" (or: python job_application_custom_autofiller.py).

How it works
------------
1. Fill in "My Profile" once (it was pre-filled from your resume).
2. For each job, fill in "This Application" (company, title, ...).
3. On each application page in Firefox, click the "Job Application Custom Autofiller"
   toolbar button. The extension fills every box it recognizes on that
   page, once, replacing whatever the box already held. Click again on
   the next page.
4. Boxes the extension did not recognize show up in the list on the
   Autofill tab. Select one, click "Answer selected question", type your
   answer, then click the Firefox button again to fill it.
5. Click "Finished" after submitting, to log the application.

There are no timers: nothing is filled, and nothing stops, on its own.
All data is saved in autofill_data.json in this folder.

Tabs:  Autofill | This Application | My Profile | Saved Answers | Cover Letter | Settings
"""

import os
import sys
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import data_store
import field_rules
from local_server import AutofillServer

# Virtual event the server thread raises when the extension sends a report.
REPORT_EVENT = "<<AutofillReport>>"


class JobApplicationCustomAutofiller:
    """The main window. Each build_*_tab method creates one tab."""

    def __init__(self, root):
        self.root = root
        self.root.title("Job Application Custom Autofiller")
        self.root.geometry("900x680")
        self.root.report_callback_exception = self.show_unexpected_error

        self.data = data_store.load_data()
        self.port = self.data["settings"].get("port", 47321)

        # Counters for the current application (reset by "Finished")
        self.session_filled = 0     # boxes filled since the last "Finished"
        self.session_pages = set()  # page addresses filled since the last "Finished"
        self.unmatched_labels = []  # questions the extension did not recognize
        self.logged_empty_labels = set()  # "recognized but blank" fields already mentioned in the log

        # Widgets that hold data, by key, so we can read them back on save.
        self.profile_widgets = {}
        self.application_widgets = {}

        self.build_window()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Reports arrive on the server thread. It raises a virtual event, which
        # Tkinter delivers on the main thread, where read_reports() runs.
        self.root.bind(REPORT_EVENT, self.read_reports)
        self.server = AutofillServer(self.port, on_report=self.wake_for_report)
        self.server.start()
        self.publish_state()
        # A report can arrive before the window's event loop is running; its
        # wake-up call is lost then, so read the queue once the loop starts.
        self.root.after_idle(self.read_reports)

    # =======================================================================
    # Window layout
    # =======================================================================
    def build_window(self):
        top_bar = ttk.Frame(self.root, padding=(10, 8))
        top_bar.pack(fill="x")

        ttk.Button(top_bar, text="■  Finished (log this application)", command=self.finish_application).pack(side="left")
        ttk.Button(top_bar, text="Save", command=self.save_clicked).pack(side="left", padx=(20, 0))

        self.status_var = tk.StringVar(value="Ready. Click the Job Application Custom Autofiller button in Firefox.")
        self.status_label = tk.Label(top_bar, textvariable=self.status_var, fg="#555", font=("Segoe UI", 10, "bold"))
        self.status_label.pack(side="left", padx=16)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.build_autofill_tab()
        self.build_application_tab()
        self.build_profile_tab()
        self.build_answers_tab()
        self.build_cover_letter_tab()
        self.build_settings_tab()

    # -- Autofill tab -------------------------------------------------------
    def build_autofill_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Autofill")

        ttk.Label(
            tab,
            text=("Questions the extension did not recognize on the page. Select one and click "
                  "\"Answer selected question\" (or double-click it) to type your answer."),
            wraplength=840,
        ).pack(anchor="w")

        self.unmatched_list = tk.Listbox(tab, height=8)
        self.unmatched_list.pack(fill="x", pady=(4, 4))
        self.unmatched_list.bind("<Double-Button-1>", lambda _event: self.answer_selected_question())

        buttons = ttk.Frame(tab)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Answer selected question", command=self.answer_selected_question).pack(side="left")
        ttk.Button(buttons, text="Clear list", command=self.clear_unmatched).pack(side="left", padx=6)

        ttk.Label(tab, text="Activity").pack(anchor="w", pady=(12, 0))
        log_frame = ttk.Frame(tab)
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_frame, height=14, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

        self.log("Ready. Open a job application in Firefox and click the Job Application Custom Autofiller toolbar button. "
                 "Each click fills the page you are on, once, replacing what the boxes already hold.")

    # -- This Application tab ----------------------------------------------
    def build_application_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="This Application")

        top = ttk.Frame(tab)
        top.pack(fill="x")
        ttk.Label(top, text="Details for the job you are applying to now. Cleared by \"New Application\".").pack(side="left")
        ttk.Button(top, text="New Application", command=self.new_application).pack(side="right")

        form = self.make_scrollable(tab)
        for row, (key, label, _pattern, multiline) in enumerate(field_rules.APPLICATION_FIELDS):
            widget = self.add_form_row(form, row, label, multiline, self.data["application"].get(key, ""))
            self.application_widgets[key] = widget

    # -- My Profile tab -----------------------------------------------------
    def build_profile_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="My Profile")
        ttk.Label(
            tab,
            text=("Used on every application. Leave a box blank to fill it yourself on the page. "
                  "For Yes/No questions type Yes or No. Click Save after changes."),
            wraplength=840,
        ).pack(anchor="w")

        form = self.make_scrollable(tab)
        for row, (key, label, _pattern, multiline) in enumerate(field_rules.PROFILE_FIELDS):
            if key.startswith("#"):
                heading = ttk.Label(form, text=label, font=("Segoe UI", 10, "bold"))
                heading.grid(row=row, column=0, columnspan=2, sticky="w", pady=(12, 2))
                continue
            widget = self.add_form_row(form, row, label, multiline, self.data["profile"].get(key, ""))
            self.profile_widgets[key] = widget

    # -- Saved Answers tab --------------------------------------------------
    def build_answers_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Saved Answers")
        ttk.Label(
            tab,
            text=("Answers to specific questions. The question text only needs to appear inside the "
                  "label on the page (not case-sensitive). These are checked before My Profile."),
            wraplength=840,
        ).pack(anchor="w")

        columns = ("question", "answer", "scope")
        self.answers_tree = ttk.Treeview(tab, columns=columns, show="headings", height=16)
        self.answers_tree.heading("question", text="Question (text on the page)")
        self.answers_tree.heading("answer", text="Answer")
        self.answers_tree.heading("scope", text="Used for")
        self.answers_tree.column("question", width=380)
        self.answers_tree.column("answer", width=330)
        self.answers_tree.column("scope", width=120)
        self.answers_tree.pack(fill="both", expand=True, pady=6)
        self.answers_tree.bind("<Double-Button-1>", lambda _event: self.edit_answer())

        buttons = ttk.Frame(tab)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Add", command=self.add_answer).pack(side="left")
        ttk.Button(buttons, text="Edit", command=self.edit_answer).pack(side="left", padx=6)
        ttk.Button(buttons, text="Delete", command=self.delete_answer).pack(side="left")
        self.refresh_answers_tree()

    # -- Cover Letter tab ---------------------------------------------------
    def build_cover_letter_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Cover Letter")

        self.fill_cover_var = tk.BooleanVar(value=self.data["cover_letter"].get("fill_cover_letter", True))
        ttk.Checkbutton(tab, text="Fill cover letter boxes with this default letter",
                        variable=self.fill_cover_var).pack(anchor="w")
        ttk.Label(
            tab,
            text=("Blanks you can use: {company}  {job_title}  {hiring_manager}  {today}  "
                  "(filled from the This Application tab)."),
        ).pack(anchor="w", pady=(4, 4))

        frame = ttk.Frame(tab)
        frame.pack(fill="both", expand=True)
        self.cover_text = tk.Text(frame, wrap="word", undo=True)
        scroll = ttk.Scrollbar(frame, command=self.cover_text.yview)
        self.cover_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.cover_text.pack(side="left", fill="both", expand=True)
        self.cover_text.insert("1.0", self.data["cover_letter"].get("default_text", ""))

        buttons = ttk.Frame(tab)
        buttons.pack(fill="x", pady=(6, 0))
        ttk.Button(buttons, text="Preview for this application", command=self.preview_cover_letter).pack(side="left")
        ttk.Button(buttons, text="Import from Word file...", command=self.import_cover_letter).pack(side="left", padx=6)

    # -- Settings tab -------------------------------------------------------
    def build_settings_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Settings")
        settings = self.data["settings"]

        ttk.Label(tab, text="Pages are filled only when you click the Job Application Custom Autofiller button in Firefox, "
                  "so there is no list of allowed sites: the page you click on is the page that is filled.",
                  wraplength=840).grid(row=0, column=0, columnspan=2, sticky="w")

        self.attach_resume_var = tk.BooleanVar(value=settings.get("attach_resume", False))
        ttk.Checkbutton(tab, text="Attach resume file to resume upload boxes "
                        "(leave off if the site already has your resume saved)",
                        variable=self.attach_resume_var).grid(row=1, column=0, sticky="w", pady=(10, 0))

        ttk.Label(tab, text="Resume file:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.resume_var = tk.StringVar(value=settings.get("resume_file", ""))
        ttk.Entry(tab, textvariable=self.resume_var, width=60).grid(row=3, column=0, sticky="we")
        ttk.Button(tab, text="Browse...", command=self.browse_resume).grid(row=3, column=1, padx=6)

        ttk.Label(
            tab,
            text=(f"Data file: {data_store.DATA_FILE}\n"
                  f"History:   {data_store.HISTORY_FILE}\n"
                  f"Extension connects to 127.0.0.1:{self.port} "
                  f"(change \"port\" in the data file and background.js together)."),
            foreground="#666", justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(20, 0))
        tab.columnconfigure(0, weight=1)

    # =======================================================================
    # Small form helpers
    # =======================================================================
    def make_scrollable(self, parent):
        """Return a frame inside a scrolling area (for long forms)."""
        outer = ttk.Frame(parent)
        outer.pack(fill="both", expand=True, pady=(6, 0))
        canvas = tk.Canvas(outer, highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        # Mouse wheel scrolls the form while the pointer is over it.
        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(int(-ev.delta / 120), "units")))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
        inner.columnconfigure(1, weight=1)
        return inner

    def add_form_row(self, form, row, label, multiline, value):
        """Add 'label: [box]' to a form and return the box widget."""
        ttk.Label(form, text=label).grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=2)
        if multiline:
            widget = tk.Text(form, height=4, wrap="word", undo=True)
            widget.insert("1.0", value)
        else:
            widget = ttk.Entry(form)
            widget.insert(0, value)
        widget.grid(row=row, column=1, sticky="we", pady=2, padx=(0, 6))
        return widget

    @staticmethod
    def read_widget(widget):
        if isinstance(widget, tk.Text):
            return widget.get("1.0", "end-1c").strip()
        return widget.get().strip()

    @staticmethod
    def write_widget(widget, value):
        if isinstance(widget, tk.Text):
            widget.delete("1.0", "end")
            widget.insert("1.0", value)
        else:
            widget.delete(0, "end")
            widget.insert(0, value)

    def log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # =======================================================================
    # Saving and sending data to Firefox
    # =======================================================================
    def collect_form_data(self):
        """Copy everything typed in the window into self.data."""
        for key, widget in self.profile_widgets.items():
            self.data["profile"][key] = self.read_widget(widget)
        for key, widget in self.application_widgets.items():
            self.data["application"][key] = self.read_widget(widget)
        self.data["cover_letter"]["default_text"] = self.cover_text.get("1.0", "end-1c").strip()
        self.data["cover_letter"]["fill_cover_letter"] = self.fill_cover_var.get()

        settings = self.data["settings"]
        settings["attach_resume"] = self.attach_resume_var.get()
        settings["resume_file"] = self.resume_var.get().strip()

    def save_all(self):
        """Save to autofill_data.json and send the new data to Firefox."""
        self.collect_form_data()
        try:
            data_store.save_data(self.data)
        except OSError as err:
            messagebox.showerror(
                "Could not save",
                f"Saving {data_store.DATA_FILE} failed:\n{err}\n\n"
                f"If the file is open in another program (or OneDrive is syncing it), close that and try again.",
            )
            return False
        self.publish_state()
        return True

    def save_clicked(self):
        if self.save_all():
            self.log("Saved. The next click on the Firefox button uses the new data.")

    def publish_state(self):
        """Give the local server what the extension should type on the next click."""
        state = {"rules": data_store.build_rules(self.data)}
        self.server.set_state(state, data_store.resume_file_path(self.data))

    # =======================================================================
    # Finished / New Application
    # =======================================================================
    def finish_application(self):
        """Log the application to the history file and reset the counters."""
        self.save_all()
        self.log(f"--- Finished. {self.session_filled} boxes filled. ---")
        if self.session_filled or self.session_pages:
            try:
                data_store.append_history(self.data, self.session_filled, self.session_pages)
                self.log(f"Logged to {os.path.basename(data_store.HISTORY_FILE)}.")
            except OSError as err:
                self.log(f"Could not write {data_store.HISTORY_FILE}: {err} (close it in Excel and try again).")
        else:
            self.log("Nothing was filled, so nothing was logged.")
        self.session_filled = 0
        self.session_pages = set()
        self.logged_empty_labels = set()
        self.status_var.set("Ready. Click the Job Application Custom Autofiller button in Firefox.")

    def new_application(self):
        if not messagebox.askyesno(
            "New Application",
            "Clear the This Application tab and answers saved only for this application?",
        ):
            return
        for widget in self.application_widgets.values():
            self.write_widget(widget, "")
        self.data["custom_answers"] = [a for a in self.data["custom_answers"] if a.get("scope") != "application"]
        self.refresh_answers_tree()
        self.clear_unmatched()
        self.save_all()
        self.log("Cleared for a new application.")

    # =======================================================================
    # Reports from Firefox
    # =======================================================================
    def wake_for_report(self):
        """
        Called on the SERVER thread after a report is queued. Raising a
        virtual event is the one Tkinter call that is safe from another
        thread; Tkinter then runs read_reports() on the main thread.
        """
        try:
            self.root.event_generate(REPORT_EVENT, when="tail")
        except (tk.TclError, RuntimeError):
            # The event loop is not running (window closing, or still starting
            # up). The report stays queued; read_reports() picks it up on the
            # after_idle call at startup or with the next report.
            pass

    def read_reports(self, _event=None):
        """Read everything the extension has sent (main thread)."""
        while not self.server.reports.empty():
            self.handle_report(self.server.reports.get())

    def handle_report(self, report):
        site = report.get("site", "page")
        self.session_pages.add(report.get("url", ""))

        for item in report.get("filled", []):
            self.session_filled += 1
            replaced = item.get("replaced", "")
            note = f"  (replaced \"{replaced[:40]}\")" if replaced else ""
            self.log(f"[{site}] Filled \"{item['label'][:70]}\"  <- {item['rule']}{note}")
        for item in report.get("recognized_empty", []):
            if item["label"] in self.logged_empty_labels:
                continue
            self.logged_empty_labels.add(item["label"])
            self.log(f"[{site}] Recognized \"{item['label'][:70]}\" as {item['rule']}, but that field "
                     f"is blank in the program. Fill it in and click Save, or type it on the page.")
        for item in report.get("no_choice", []):
            choices = " / ".join(item.get("choices", []))
            self.log(f"[{site}] \"{item['label'][:70]}\": none of the choices matched \"{item['value']}\". "
                     f"Choices are: {choices}")
        for message in report.get("errors", []):
            self.log(f"[{site}] Problem: {message}")
        for label in report.get("unmatched", []):
            if label not in self.unmatched_labels:
                self.unmatched_labels.append(label)
                self.unmatched_list.insert("end", label)

        company = self.data["application"].get("company") or "this application"
        self.status_var.set(f"{self.session_filled} boxes filled for {company}.")

    def clear_unmatched(self):
        self.unmatched_labels = []
        self.unmatched_list.delete(0, "end")

    def answer_selected_question(self):
        selection = self.unmatched_list.curselection()
        if not selection:
            messagebox.showinfo("Answer a question", "Select a question in the list first.")
            return
        index = selection[0]
        question = self.unmatched_labels[index]
        result = self.ask_answer_dialog("Answer this question", question, "", "application")
        if not result:
            return
        self.data["custom_answers"].append(result)
        self.unmatched_list.delete(index)
        del self.unmatched_labels[index]
        self.refresh_answers_tree()
        self.save_all()
        self.log(f"Answer saved for \"{question[:70]}\". Click the Firefox button again to fill it.")

    # =======================================================================
    # Saved Answers
    # =======================================================================
    def refresh_answers_tree(self):
        self.answers_tree.delete(*self.answers_tree.get_children())
        for index, item in enumerate(self.data["custom_answers"]):
            scope = "This application" if item.get("scope") == "application" else "All applications"
            answer_preview = item.get("answer", "").replace("\n", " ")[:80]
            self.answers_tree.insert("", "end", iid=str(index), values=(item.get("question", ""), answer_preview, scope))

    def selected_answer_index(self):
        selection = self.answers_tree.selection()
        if not selection:
            messagebox.showinfo("Saved Answers", "Select an answer in the list first.")
            return None
        return int(selection[0])

    def add_answer(self):
        result = self.ask_answer_dialog("Add an answer", "", "", "always")
        if result:
            self.data["custom_answers"].append(result)
            self.refresh_answers_tree()
            self.save_all()

    def edit_answer(self):
        index = self.selected_answer_index()
        if index is None:
            return
        item = self.data["custom_answers"][index]
        result = self.ask_answer_dialog("Edit answer", item["question"], item["answer"], item.get("scope", "always"))
        if result:
            self.data["custom_answers"][index] = result
            self.refresh_answers_tree()
            self.save_all()

    def delete_answer(self):
        index = self.selected_answer_index()
        if index is None:
            return
        question = self.data["custom_answers"][index]["question"]
        if messagebox.askyesno("Delete answer", f"Delete the saved answer for:\n\n{question}"):
            del self.data["custom_answers"][index]
            self.refresh_answers_tree()
            self.save_all()

    def ask_answer_dialog(self, title, question, answer, scope):
        """
        Pop-up to type a question and answer. Returns
        {"question", "answer", "scope"} or None if cancelled.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()
        result = {}

        ttk.Label(dialog, text="Question (text that appears in the label on the page):").pack(anchor="w", padx=10, pady=(10, 0))
        question_entry = ttk.Entry(dialog, width=80)
        question_entry.insert(0, question)
        question_entry.pack(fill="x", padx=10)

        ttk.Label(dialog, text="Your answer (for Yes/No or drop-downs, type the choice exactly as shown):").pack(anchor="w", padx=10, pady=(10, 0))
        answer_text = tk.Text(dialog, width=80, height=8, wrap="word")
        answer_text.insert("1.0", answer)
        answer_text.pack(fill="both", expand=True, padx=10)
        answer_text.focus_set()

        always_var = tk.BooleanVar(value=(scope == "always"))
        ttk.Checkbutton(dialog, text="Use this answer for all future applications (otherwise only this one)",
                        variable=always_var).pack(anchor="w", padx=10, pady=6)

        def on_ok():
            q = question_entry.get().strip()
            a = answer_text.get("1.0", "end-1c").strip()
            if not q:
                messagebox.showwarning("Missing question", "The question text cannot be empty.", parent=dialog)
                return
            result.update({"question": q, "answer": a, "scope": "always" if always_var.get() else "application"})
            dialog.destroy()

        buttons = ttk.Frame(dialog)
        buttons.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(buttons, text="Save", command=on_ok).pack(side="right")
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right", padx=6)

        self.root.wait_window(dialog)
        return result or None

    # =======================================================================
    # Cover letter and settings buttons
    # =======================================================================
    def preview_cover_letter(self):
        self.collect_form_data()
        window = tk.Toplevel(self.root)
        window.title("Cover letter preview")
        text = tk.Text(window, wrap="word", width=90, height=35)
        text.insert("1.0", data_store.render_cover_letter(self.data))
        text.configure(state="disabled")
        text.pack(fill="both", expand=True)

    def import_cover_letter(self):
        path = filedialog.askopenfilename(
            title="Choose a cover letter (.docx)", initialdir=data_store.APP_FOLDER,
            filetypes=[("Word documents", "*.docx")],
        )
        if not path:
            return
        try:
            text = data_store.cover_letter_from_docx(path)
        except ValueError as err:
            messagebox.showerror("Import failed", str(err))
            return
        if not messagebox.askyesno("Replace cover letter", "Replace the current default cover letter with this file's text?"):
            return
        self.cover_text.delete("1.0", "end")
        self.cover_text.insert("1.0", text)
        self.save_all()
        self.log(f"Imported cover letter from {os.path.basename(path)}.")

    def browse_resume(self):
        path = filedialog.askopenfilename(
            title="Choose your resume file", initialdir=data_store.APP_FOLDER,
            filetypes=[("Resume files", "*.pdf *.docx *.doc"), ("All files", "*.*")],
        )
        if path:
            # Store files in this folder as just their name, so the folder can be moved.
            folder = os.path.normcase(data_store.APP_FOLDER)
            if os.path.normcase(os.path.dirname(path)) == folder:
                path = os.path.basename(path)
            self.resume_var.set(path)

    # =======================================================================
    # Closing and errors
    # =======================================================================
    def on_close(self):
        self.save_all()
        self.server.stop()
        self.root.destroy()

    def show_unexpected_error(self, exc_type, exc_value, exc_traceback):
        """Any unexpected error inside a button click is shown with where it happened."""
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        print(details, file=sys.stderr)
        messagebox.showerror("Unexpected error", f"{exc_type.__name__}: {exc_value}\n\nWhere it happened:\n{details[-1500:]}")


def main():
    root = tk.Tk()
    try:
        JobApplicationCustomAutofiller(root)
    except (ValueError, OSError) as err:
        # Problems reading the data file or starting the local server.
        root.withdraw()
        messagebox.showerror("Job Application Custom Autofiller could not start", str(err))
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
