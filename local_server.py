"""
local_server.py - The tiny web server the Firefox extension talks to.

It listens ONLY on 127.0.0.1 (your own computer), so nothing on the network
can reach it. The program window and the extension exchange three messages:

    GET  /state        extension asks (when you click its button):
                       "What should I type into each box?"
    POST /report       extension says: "I filled these boxes, and I saw
                       these boxes I did not recognize."
    GET  /file/resume  extension asks for the resume file to attach
                       (only used when "Attach resume file" is turned on)

The extension only sends these when you click its toolbar button; it never
polls. Thread safety: the server runs in a background thread. Tkinter must
only be touched from the main thread, so:
  * the window gives the server a new state with set_state() (a simple
    dictionary swap, safe across threads), and
  * reports from the extension go into a queue, and the server calls
    on_report() so the window can wake up and read the queue.
"""

import base64
import json
import os
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class AutofillServer:
    """Owns the HTTP server thread and the data shared with the window."""

    def __init__(self, port, on_report=None):
        self.port = port
        # What /state returns. Replaced as a whole by set_state().
        self._state = {"rules": []}
        # Path of the resume file served by /file/resume ("" = none).
        self._resume_path = ""
        # Reports from the extension. After each one is queued, on_report()
        # is called (from the server thread) so the window knows to read it.
        self.reports = queue.Queue()
        self.on_report = on_report
        self._httpd = None

    # -- called from the window (main thread) -------------------------------
    def set_state(self, state, resume_path=""):
        self._state = state
        self._resume_path = resume_path

    def start(self):
        """
        Start listening. Raises OSError with a clear message if the port is
        already taken (usually because the program is already open).
        """
        handler = _make_handler(self)
        try:
            self._httpd = ThreadingHTTPServer(("127.0.0.1", self.port), handler)
        except OSError as err:
            raise OSError(
                f"Could not start the local server on 127.0.0.1:{self.port} ({err}).\n"
                f"Most likely Job App Manager is already open in another window.\n"
                f"Close the other copy, or change \"port\" in autofill_data.json "
                f"(and the same number in firefox_extension/background.js)."
            ) from err
        thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        thread.start()

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()


def _make_handler(server):
    """Build the request handler class with access to our AutofillServer."""

    class Handler(BaseHTTPRequestHandler):

        def _send_json(self, status, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/state":
                self._send_json(200, server._state)
                return

            if self.path == "/file/resume":
                path = server._resume_path
                if not path or not os.path.exists(path):
                    self._send_json(404, {"error": f"Resume file not found: {path or '(none set)'}"})
                    return
                with open(path, "rb") as f:
                    content = base64.b64encode(f.read()).decode("ascii")
                self._send_json(200, {"name": os.path.basename(path), "base64": content})
                return

            self._send_json(404, {"error": f"Unknown address {self.path}"})

        def do_POST(self):
            if self.path != "/report":
                self._send_json(404, {"error": f"Unknown address {self.path}"})
                return
            length = int(self.headers.get("Content-Length", 0))
            try:
                report = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError as err:
                self._send_json(400, {"error": f"Report was not valid JSON: {err}"})
                return
            server.reports.put(report)
            if server.on_report:
                server.on_report()
            self._send_json(200, {"ok": True})

        def do_OPTIONS(self):
            # Lets the browser send JSON POSTs (CORS "preflight" request).
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def log_message(self, fmt, *args):
            # Keep the console quiet; the Activity log in the window has the details.
            pass

    return Handler
