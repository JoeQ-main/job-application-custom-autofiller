/*
 * background.js - Runs once for the whole browser.
 *
 * Nothing happens until you click the "Job App Autofill" toolbar button.
 * On each click it:
 *   1. asks the Job App Manager program (running on this same computer at
 *      127.0.0.1) for the current fill rules,
 *   2. hands those rules to the content script in every frame of the
 *      current tab, which fills the page ONCE,
 *   3. forwards each frame's "what I filled" report to the program, and
 *      shows the number of boxes filled on the toolbar badge.
 *
 * There are no timers and no background polling: the program is only
 * contacted when you click.
 *
 * Why go through here? Only the background script has permission to talk
 * to 127.0.0.1, so web pages themselves can never reach the program.
 *
 * If you change the port, change it in autofill_data.json too ("port").
 */

const SERVER = "http://127.0.0.1:47321";

// Boxes filled by the most recent click (shown on the toolbar badge).
let clickFilled = 0;

function showBadge(text, color, title) {
  browser.browserAction.setBadgeText({ text: text });
  browser.browserAction.setBadgeBackgroundColor({ color: color });
  browser.browserAction.setTitle({ title: "Job App Autofill: " + title });
}

async function getRules() {
  const response = await fetch(SERVER + "/state", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("program answered HTTP " + response.status);
  }
  const state = await response.json();
  return state.rules || [];
}

async function fillCurrentPage(tab) {
  clickFilled = 0;
  showBadge("", "#2e7d32", "filling this page...");

  let rules;
  try {
    rules = await getRules();
  } catch (err) {
    // Normal when the program is not open.
    showBadge("!", "#c62828", "the Job App Manager program is not running (" + err + ")");
    return;
  }

  try {
    // Sent to every frame of the tab; each frame fills itself and reports.
    await browser.tabs.sendMessage(tab.id, { type: "fill", rules: rules });
  } catch (err) {
    // No content script in this tab: a browser page, or a page that was
    // already open before the extension was loaded.
    showBadge("!", "#c62828", "cannot fill this page. If it is a web page, reload it and click again. (" + err + ")");
    return;
  }
  showBadge(String(clickFilled), "#2e7d32", clickFilled + " box(es) filled on the last click. Click to fill this page again.");
}

async function sendReport(report) {
  clickFilled += (report.filled || []).length;
  showBadge(String(clickFilled), "#2e7d32", clickFilled + " box(es) filled on the last click. Click to fill this page again.");
  try {
    await fetch(SERVER + "/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(report),
    });
    return { ok: true };
  } catch (err) {
    return { ok: false, error: "Could not send report to the program: " + err };
  }
}

async function getResumeFile() {
  try {
    const response = await fetch(SERVER + "/file/resume", { cache: "no-store" });
    const body = await response.json();
    if (!response.ok) {
      return { ok: false, error: body.error || ("HTTP " + response.status) };
    }
    return { ok: true, name: body.name, base64: body.base64 };
  } catch (err) {
    return { ok: false, error: "Could not get the resume file from the program: " + err };
  }
}

// Messages from content scripts. Returning a Promise sends its result back.
browser.runtime.onMessage.addListener((message) => {
  if (message.type === "report") {
    return sendReport(message.report);
  }
  if (message.type === "getResume") {
    return getResumeFile();
  }
  return Promise.resolve({ ok: false, error: "Unknown message type: " + message.type });
});

browser.browserAction.onClicked.addListener(fillCurrentPage);
showBadge("", "#2e7d32", "click to fill the job application on this page");
