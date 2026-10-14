/*
 * content.js - Runs inside every web page (and every frame inside a page).
 *
 * It does nothing on its own. Each time you click the "Job Application Custom Autofiller"
 * toolbar button, the background script sends this page the current rules
 * from the Job Application Custom Autofiller program, and this script makes ONE pass:
 *   1. finds the boxes, drop-downs, Yes/No buttons, check boxes, date boxes
 *      and rich-text editors on the page,
 *   2. reads each one's label ("First name", "Are you 18 or older?", ...),
 *   3. finds the first rule from the program whose pattern matches the label,
 *   4. fills in that rule's value, REPLACING whatever the box already held,
 *   5. tells the program what it filled and which labels it did not know.
 *
 * It never clicks Next / Submit. You stay in control of moving through the
 * application. To fill the next page, click the button again.
 *
 * Kinds of boxes it can fill:
 *   - plain text boxes and large text areas (also number / phone / url / email)
 *   - rich-text editors (contenteditable boxes used for cover letters)
 *   - date boxes (<input type="date">), from a value like "10/20/2026"
 *   - normal drop-down lists (<select>)
 *   - custom drop-downs: type-ahead boxes (Greenhouse, Lever, LinkedIn) and
 *     button-style lists (Workday). These open the list and pick the choice
 *     that best matches your answer, waiting under a second for it to appear.
 *   - Yes/No (radio) button groups
 *   - check boxes: a single box whose wording matches a Yes/No answer (only
 *     ever ticked, never unticked), and groups of boxes (e.g. shift
 *     availability) from a comma-separated answer
 *   - resume upload boxes (only when "Attach resume file" is on)
 */

// Rules compiled into RegExp objects, rebuilt on every click.
let compiledRules = [];
// True while a fill pass is in progress (a second click is ignored until it ends).
let fillRunning = false;
// Report being built during the current pass.
let currentReport = null;

// ---------------------------------------------------------------------------
// Text helpers
// ---------------------------------------------------------------------------

/* Squeeze spaces, drop "*" and a trailing "required", and undo the
 * "First nameFirst name" doubling some sites create with hidden text. */
function cleanLabel(text) {
  let t = (text || "").replace(/\s+/g, " ").replace(/\*/g, "").trim();
  t = t.replace(/\s*\(?required\)?\s*$/i, "").trim();
  const half = t.length / 2;
  if (t.length > 1 && Number.isInteger(half) && t.slice(0, half).trim() === t.slice(half).trim()) {
    t = t.slice(0, half).trim();
  }
  return t;
}

/* "firstName" / "first_name" / "first-name" -> "first name" */
function humanize(text) {
  return (text || "")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/[_\-.\[\]]+/g, " ")
    .trim();
}

function normalize(text) {
  return (text || "").replace(/\s+/g, " ").trim().toLowerCase();
}

function isYes(value) {
  const text = (value || "").trim();
  return /^y$/i.test(text) || /^(yes|true|1|i\s*(do|am|have|agree|confirm|consent))\b/i.test(text);
}

/* "No", "N", "false", "I do not..." - but not "N/A" or "None". */
function isNo(value) {
  const text = (value || "").trim();
  return /^n$/i.test(text) || /^(no|false|0|i\s*(do\s*not|don't|am\s*not|have\s*not|haven't))\b/i.test(text);
}

/* Is a check box's own wording a negative statement ("I do NOT require...")? */
function isNegatedStatement(label) {
  return /\b(not|no|never|don't|doesn't|isn't|aren't|without|neither)\b/i.test(label || "");
}

function looksLikePlaceholder(text) {
  return /^(select|choose|please|--|—|none)/i.test((text || "").trim());
}

// ---------------------------------------------------------------------------
// Finding the label of a box
// ---------------------------------------------------------------------------

function textOfIds(idList) {
  return (idList || "")
    .split(/\s+/)
    .map((id) => document.getElementById(id))
    .filter(Boolean)
    .map((node) => node.textContent)
    .join(" ");
}

/* Returns the best human-readable label for a box, or "" if none. */
function getLabel(el) {
  // 1. <label for="..."> or a <label> wrapped around the box
  if (el.labels && el.labels.length > 0) {
    const text = cleanLabel(Array.from(el.labels).map((l) => l.textContent).join(" "));
    if (text) return text;
  }
  if (el.id) {
    const forLabel = document.querySelector("label[for='" + CSS.escape(el.id) + "']");
    if (forLabel && cleanLabel(forLabel.textContent)) return cleanLabel(forLabel.textContent);
  }
  // 2. aria-labelledby / aria-label (common on LinkedIn, Indeed and Workday)
  const labelledBy = cleanLabel(textOfIds(el.getAttribute("aria-labelledby")));
  if (labelledBy) return labelledBy;
  const ariaLabel = cleanLabel(el.getAttribute("aria-label"));
  if (ariaLabel) return ariaLabel;
  // 3. A question written in a fieldset legend
  const fieldset = el.closest("fieldset");
  const legend = fieldset ? fieldset.querySelector("legend") : null;
  if (legend && cleanLabel(legend.textContent)) return cleanLabel(legend.textContent);
  // 4. Placeholder text inside the box
  const placeholder = cleanLabel(el.getAttribute("placeholder"));
  if (placeholder) return placeholder;
  // 5. Short text in the surrounding element (up to 3 levels up)
  let parent = el.parentElement;
  for (let level = 0; level < 3 && parent; level++) {
    let text = parent.innerText || parent.textContent || "";
    // Leave out the box's own text (a drop-down button's current choice, say).
    if (el.innerText) text = text.replace(el.innerText, " ");
    text = cleanLabel(text);
    if (text && text.length <= 200) return text;
    parent = parent.parentElement;
  }
  // 6. Last resort: the box's internal name or id
  return cleanLabel(humanize(el.getAttribute("name") || el.id || el.getAttribute("data-automation-id") || ""));
}

/* The question for a group of Yes/No (radio) or check boxes. */
function getGroupLabel(items) {
  const first = items[0];
  const fieldset = first.closest("fieldset");
  const legend = fieldset ? fieldset.querySelector("legend") : null;
  if (legend && cleanLabel(legend.textContent)) return cleanLabel(legend.textContent);

  const group = first.closest("[role='radiogroup'], [role='group']");
  if (group) {
    const text = cleanLabel(textOfIds(group.getAttribute("aria-labelledby")) || group.getAttribute("aria-label"));
    if (text) return text;
  }

  // Fall back to the text around the buttons, minus the button labels.
  let container = first.parentElement;
  while (container && !items.every((r) => container.contains(r))) {
    container = container.parentElement;
  }
  for (let level = 0; level < 2 && container; level++) {
    let text = container.innerText || container.textContent || "";
    items.forEach((r) => { text = text.replace(getOptionLabel(r), ""); });
    text = cleanLabel(text);
    if (text && text.length <= 250) return text;
    container = container.parentElement;
  }
  return cleanLabel(humanize(first.name));
}

function getOptionLabel(box) {
  if (box.labels && box.labels.length > 0) return cleanLabel(box.labels[0].textContent);
  return cleanLabel(box.getAttribute("aria-label") || box.value);
}

// ---------------------------------------------------------------------------
// Which boxes can be filled
// ---------------------------------------------------------------------------

// Input types handled elsewhere (checkbox, radio, file, date) or never filled.
const SKIPPED_INPUT_TYPES = new Set([
  "hidden", "submit", "button", "reset", "image", "password", "checkbox",
  "radio", "file", "search", "date", "datetime-local", "month", "week",
  "time", "color", "range",
]);

function isVisible(el) {
  if (!el || el.getClientRects().length === 0) return false;
  const style = window.getComputedStyle(el);
  return style.visibility !== "hidden" && style.display !== "none";
}

function isUsable(el) {
  return !el.disabled && !el.readOnly && el.getAttribute("aria-disabled") !== "true" && isVisible(el);
}

function isFillableBox(el) {
  if (el.tagName === "INPUT" && SKIPPED_INPUT_TYPES.has((el.type || "text").toLowerCase())) return false;
  return isUsable(el);
}

/* Type-ahead boxes: an <input> that opens a list of choices as you type. */
function isComboboxInput(el) {
  if (el.tagName !== "INPUT") return false;
  return el.getAttribute("role") === "combobox" ||
    el.getAttribute("aria-autocomplete") === "list" ||
    el.getAttribute("aria-autocomplete") === "both" ||
    el.getAttribute("aria-haspopup") === "listbox" ||
    (el.closest("[role='combobox']") !== null && el.closest("[role='combobox']") !== el);
}

function isPlaceholderOption(option) {
  return option.value === "" || looksLikePlaceholder(option.textContent);
}

// ---------------------------------------------------------------------------
// Matching labels to rules
// ---------------------------------------------------------------------------

function compileRules(rules) {
  const result = [];
  for (const rule of rules) {
    try {
      result.push({ ...rule, regex: new RegExp(rule.pattern, "i") });
    } catch (err) {
      console.warn("[Job Application Custom Autofiller] Skipping rule '" + rule.name + "': bad pattern /" + rule.pattern + "/ (" + err.message + ")");
    }
  }
  return result;
}

function findRule(label, kind) {
  const text = normalize(label);
  return compiledRules.find((rule) => rule.kind === kind && rule.regex.test(text)) || null;
}

function siteName() {
  const host = location.hostname;
  if (host.includes("indeed")) return "Indeed";
  if (host.includes("linkedin")) return "LinkedIn";
  return host.replace(/^www\./, "");
}

const US_STATES = {
  al: "alabama", ak: "alaska", az: "arizona", ar: "arkansas", ca: "california", co: "colorado",
  ct: "connecticut", de: "delaware", dc: "district of columbia", fl: "florida", ga: "georgia",
  hi: "hawaii", id: "idaho", il: "illinois", in: "indiana", ia: "iowa", ks: "kansas", ky: "kentucky",
  la: "louisiana", me: "maine", md: "maryland", ma: "massachusetts", mi: "michigan", mn: "minnesota",
  ms: "mississippi", mo: "missouri", mt: "montana", ne: "nebraska", nv: "nevada", nh: "new hampshire",
  nj: "new jersey", nm: "new mexico", ny: "new york", nc: "north carolina", nd: "north dakota",
  oh: "ohio", ok: "oklahoma", or: "oregon", pa: "pennsylvania", ri: "rhode island", sc: "south carolina",
  sd: "south dakota", tn: "tennessee", tx: "texas", ut: "utah", vt: "vermont", va: "virginia",
  wa: "washington", wv: "west virginia", wi: "wisconsin", wy: "wyoming", pr: "puerto rico",
};

const SYNONYMS = {
  "yes": ["y", "true"], "no": ["n", "false"],
  "united states": ["united states of america", "usa", "us", "u.s.", "u.s.a."],
  "usa": ["united states", "united states of america", "us"],
  "us": ["united states", "united states of america", "usa"],
  "male": ["man"], "female": ["woman"],
  "full time": ["full-time", "fulltime"], "part time": ["part-time", "parttime"],
};

/* Every spelling of the wanted answer worth trying, most exact first. */
function expandWanted(wanted) {
  const want = normalize(wanted);
  const list = [want];
  if (US_STATES[want]) list.push(US_STATES[want]);
  for (const [abbr, name] of Object.entries(US_STATES)) {
    if (name === want) list.push(abbr);
  }
  for (const alias of SYNONYMS[want] || []) list.push(alias);
  const unhyphenated = want.replace(/-/g, " ");
  if (unhyphenated !== want) list.push(unhyphenated);
  return list;
}

/* Find the choice in a list that best matches the wanted answer.
 * Exact text first, then "starts with", then "contains" either way. */
function pickChoice(choices, wanted) {
  const usable = choices.filter((c) => c.text !== "");
  const wants = expandWanted(wanted);
  for (const want of wants) {
    const exact = usable.find((c) => c.text === want || c.value === want);
    if (exact) return exact;
  }
  for (const want of wants) {
    const found =
      usable.find((c) => c.text.startsWith(want)) ||
      usable.find((c) => want.length >= 2 && c.text.includes(want)) ||
      usable.find((c) => c.text.length >= 2 && want.includes(c.text));
    if (found) return found;
  }
  return null;
}

/* "Days, Evenings / Weekends" -> ["days", "evenings", "weekends"] */
function splitAnswers(value) {
  return normalize(value).split(/\s*[,;\/|]\s*|\s+and\s+/).map((s) => s.trim()).filter(Boolean);
}

// ---------------------------------------------------------------------------
// Filling primitives
// ---------------------------------------------------------------------------

/* Set a box's value so that React/Angular pages (LinkedIn, Indeed) notice it.
 * Using the browser's own value setter, then firing input/change events,
 * is what makes the site register the new text. */
function setBoxValue(el, value, keepFocus) {
  const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
  el.focus();
  if (descriptor && descriptor.set) {
    descriptor.set.call(el, value);
  } else {
    el.value = value;
  }
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  if (!keepFocus) {
    el.dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
    el.blur();
  }
}

function fillContentEditable(el, value) {
  el.focus();
  let done = false;
  try {
    document.execCommand("selectAll", false, null);
    done = document.execCommand("insertText", false, value);
  } catch (err) {
    done = false;
  }
  if (!done || normalize(el.innerText) !== normalize(value)) {
    el.textContent = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }
  el.dispatchEvent(new Event("change", { bubbles: true }));
  el.blur();
}

function selectChoices(el) {
  return Array.from(el.options).map((option, index) => ({
    index: index,
    text: isPlaceholderOption(option) ? "" : normalize(option.textContent),
    value: normalize(option.value),
  }));
}

/* Returns "filled", "same" or {no_choice: [...the list's choices]}. */
function fillSelect(el, value) {
  const choice = pickChoice(selectChoices(el), value);
  if (!choice) {
    return { no_choice: Array.from(el.options).filter((o) => !isPlaceholderOption(o)).map((o) => o.textContent.trim()) };
  }
  if (el.selectedIndex === choice.index) return "same";
  el.selectedIndex = choice.index;
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  return "filled";
}

/* "10/20/2026", "2026-10-20", "October 20, 2026" -> "2026-10-20"; "" if not a date. */
function toIsoDate(value) {
  const text = (value || "").trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const us = text.match(/^(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{4})$/);
  if (us) return us[3] + "-" + us[1].padStart(2, "0") + "-" + us[2].padStart(2, "0");
  const parsed = new Date(text);
  if (isNaN(parsed.getTime()) || !/\d{4}/.test(text)) return "";
  return parsed.getFullYear() + "-" + String(parsed.getMonth() + 1).padStart(2, "0") + "-" + String(parsed.getDate()).padStart(2, "0");
}

function clickLikeAUser(el) {
  const opts = { bubbles: true, cancelable: true, view: window };
  el.dispatchEvent(new PointerEvent("pointerdown", opts));
  el.dispatchEvent(new MouseEvent("mousedown", opts));
  el.dispatchEvent(new PointerEvent("pointerup", opts));
  el.dispatchEvent(new MouseEvent("mouseup", opts));
  el.click();
}

function pressKey(el, key) {
  for (const type of ["keydown", "keyup"]) {
    el.dispatchEvent(new KeyboardEvent(type, { key: key, code: key, bubbles: true, cancelable: true }));
  }
}

/* Does the box already hold the answer (or the list's longer spelling of it,
 * "Pittsburgh, PA" for "Pittsburgh")? */
function alreadyHolds(current, value) {
  const text = normalize(current);
  return text !== "" && !looksLikePlaceholder(text) && pickChoice([{ text: text, value: text }], value) !== null;
}

const OPTION_SELECTOR = "[role='option'], [role='listbox'] li, [role='menuitem'], [role='menuitemradio']";

/* The list elements a drop-down points at through aria-controls / aria-owns. */
function ownedLists(el) {
  const ids = [el, el.parentElement].filter(Boolean)
    .flatMap((node) => [node.getAttribute("aria-controls"), node.getAttribute("aria-owns")])
    .filter(Boolean)
    .flatMap((value) => value.split(/\s+/));
  return ids.map((id) => document.getElementById(id)).filter(Boolean);
}

/* The visible choices of an open custom drop-down attached to el.
 * `before` holds the options that were already visible before the list was
 * opened: those belong to some other widget and are never clicked. */
function openOptions(el, before) {
  let nodes = [];
  for (const list of ownedLists(el)) {
    nodes = nodes.concat(Array.from(list.querySelectorAll("[role='option'], li")));
  }
  if (nodes.length === 0) {
    nodes = Array.from(document.querySelectorAll(OPTION_SELECTOR)).filter((n) => !before.has(n));
  }
  nodes = nodes.filter((n) => isVisible(n) && n !== el && !el.contains(n) && !n.contains(el));
  // Keep the innermost option when both an <li> and its [role=option] child matched.
  return nodes.filter((n) => !nodes.some((other) => other !== n && n.contains(other)));
}

function visibleOptionsNow() {
  return new Set(Array.from(document.querySelectorAll(OPTION_SELECTOR)).filter(isVisible));
}

/* Wait for the drop-down list of el to show choices. Gives up after
 * timeoutMs, or sooner when the box says it is closed (aria-expanded="false")
 * once it has had a moment to open. Only runs while a click is handled. */
function waitForOptions(el, before, timeoutMs) {
  const started = Date.now();
  const limit = timeoutMs || 800;
  return new Promise((resolve) => {
    (function look() {
      const nodes = openOptions(el, before);
      if (nodes.length) return resolve(nodes);
      const elapsed = Date.now() - started;
      const saysClosed = el.getAttribute("aria-expanded") === "false";
      if (elapsed >= limit || (elapsed >= 200 && saysClosed)) return resolve([]);
      setTimeout(look, 50);
    })();
  });
}

function optionChoices(nodes) {
  return nodes.map((node) => ({
    el: node,
    text: normalize(node.innerText || node.textContent),
    value: normalize(node.getAttribute("data-value") || node.getAttribute("value") || node.id || ""),
  }));
}

/* After a drop-down was opened: click the choice matching value.
 * Returns "filled", "none" (no list appeared) or {no_choice: [...]}. */
async function pickFromOpenList(el, value, before) {
  const nodes = await waitForOptions(el, before);
  if (nodes.length === 0) return "none";
  const choice = pickChoice(optionChoices(nodes), value);
  if (!choice) {
    pressKey(el, "Escape");
    el.blur();
    return { no_choice: nodes.map((n) => cleanLabel(n.innerText || n.textContent)) };
  }
  clickLikeAUser(choice.el);
  return "filled";
}

/* Type-ahead box: type the answer, then click the matching suggestion.
 * Returns "filled", "same", or an object {no_choice: [...choices]}. */
async function fillComboboxInput(el, value) {
  if (alreadyHolds(el.value, value)) return "same";
  const before = visibleOptionsNow();
  setBoxValue(el, value, true);
  pressKey(el, "ArrowDown");
  const result = await pickFromOpenList(el, value, before);
  if (result === "none") {
    // No list appeared: the site accepts typed text. Leave it typed in.
    el.dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
    el.blur();
    return "filled";
  }
  return result;
}

/* Button-style drop-down (Workday): open it, click the matching choice. */
async function fillDropdownButton(el, value) {
  if (alreadyHolds(el.innerText, value)) return "same";
  const before = visibleOptionsNow();
  clickLikeAUser(el);
  const result = await pickFromOpenList(el, value, before);
  if (result === "none") {
    pressKey(el, "Escape");
    return { error: "the drop-down list did not open after clicking it. Pick the answer by hand." };
  }
  return result;
}

function setChecked(box, checked) {
  if (box.checked === checked) return false;
  box.click();
  if (box.checked !== checked) {
    box.checked = checked;
    box.dispatchEvent(new Event("input", { bubbles: true }));
    box.dispatchEvent(new Event("change", { bubbles: true }));
  }
  return true;
}

function base64ToFile(base64, name) {
  const bytes = Uint8Array.from(atob(base64), (ch) => ch.charCodeAt(0));
  const types = {
    pdf: "application/pdf",
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    doc: "application/msword",
    txt: "text/plain",
  };
  const extension = name.split(".").pop().toLowerCase();
  return new File([bytes], name, { type: types[extension] || "application/octet-stream" });
}

async function attachResume(el, report) {
  const reply = await browser.runtime.sendMessage({ type: "getResume" });
  if (!reply || !reply.ok) {
    report.errors.push("Resume upload: " + (reply ? reply.error : "no reply from extension background"));
    return;
  }
  if (el.files && el.files.length > 0 && el.files[0].name === reply.name) return;
  const transfer = new DataTransfer();
  transfer.items.add(base64ToFile(reply.base64, reply.name));
  el.files = transfer.files;
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  report.filled.push({ label: getLabel(el) || "Resume upload", rule: "Resume file (" + reply.name + ")" });
}

// ---------------------------------------------------------------------------
// One pass over the page
// ---------------------------------------------------------------------------

function newReport() {
  return { url: location.href, site: siteName(), filled: [], recognized_empty: [], unmatched: [], no_choice: [], errors: [], seen: new Set() };
}

/* Add a label to a report list once, even if several boxes share the label. */
function addOnce(list, key, item) {
  if (currentReport.seen.has(key)) return;
  currentReport.seen.add(key);
  list.push(item);
}

/* The rule for a label, or null after noting why there is none. */
function ruleFor(label, report) {
  if (!label || /^search\b/i.test(label)) return null;
  const rule = findRule(label, "text");
  if (!rule) {
    addOnce(report.unmatched, "unmatched:" + label, label);
    return null;
  }
  if (!rule.value) {
    addOnce(report.recognized_empty, "empty:" + label, { label: label, rule: rule.name });
    return null;
  }
  return rule;
}

function ruleValue(rule) {
  return rule.value.replace(/\{site\}/g, siteName());
}

function noteResult(result, label, rule, value, oldValue, report) {
  if (result === "filled") {
    const item = { label: label, rule: rule.name };
    if (oldValue && !looksLikePlaceholder(oldValue) && normalize(oldValue) !== normalize(value)) item.replaced = oldValue;
    report.filled.push(item);
  } else if (result && result.no_choice) {
    report.no_choice.push({ label: label, value: value, choices: result.no_choice.slice(0, 15) });
  } else if (result && result.error) {
    report.errors.push("\"" + label.slice(0, 70) + "\": " + result.error);
  }
}

/* Text boxes, text areas, drop-downs and type-ahead boxes. */
async function handleBox(el, report) {
  const label = getLabel(el);
  const rule = ruleFor(label, report);
  if (!rule) return;
  const value = ruleValue(rule);
  let result;

  if (el.tagName === "SELECT") {
    const oldOption = el.selectedIndex >= 0 ? el.options[el.selectedIndex] : null;
    const oldText = oldOption && !isPlaceholderOption(oldOption) ? oldOption.textContent.trim() : "";
    noteResult(fillSelect(el, value), label, rule, value, oldText, report);
    return;
  }

  const oldValue = el.value || "";
  if (isComboboxInput(el)) {
    result = await fillComboboxInput(el, value);
  } else if (normalize(oldValue) === normalize(value)) {
    result = "same";
  } else {
    setBoxValue(el, value);
    result = "filled";
  }
  noteResult(result, label, rule, value, oldValue, report);
}

function handleDateBox(el, report) {
  const label = getLabel(el);
  const rule = ruleFor(label, report);
  if (!rule) return;
  const value = ruleValue(rule);
  const iso = toIsoDate(value);
  if (!iso) {
    report.errors.push("\"" + label.slice(0, 70) + "\" is a date box, but the saved answer \"" + value + "\" is not a date (use e.g. 10/20/2026).");
    return;
  }
  const oldValue = el.value || "";
  if (oldValue === iso) return;
  setBoxValue(el, iso);
  noteResult("filled", label, rule, iso, oldValue, report);
}

function handleRichText(el, report) {
  const label = getLabel(el);
  const rule = ruleFor(label, report);
  if (!rule) return;
  const value = ruleValue(rule);
  const oldValue = el.innerText || "";
  if (normalize(oldValue) === normalize(value)) return;
  fillContentEditable(el, value);
  noteResult("filled", label, rule, value, oldValue, report);
}

async function handleDropdownButton(el, report) {
  const label = getLabel(el);
  const rule = ruleFor(label, report);
  if (!rule) return;
  const value = ruleValue(rule);
  const oldValue = el.innerText || "";
  const result = await fillDropdownButton(el, value);
  noteResult(result, label, rule, value, oldValue, report);
}

function handleRadioGroup(radios, report) {
  if (!radios.some((r) => isVisible(r) || (r.labels && r.labels[0] && isVisible(r.labels[0])))) return;
  const label = getGroupLabel(radios);
  const rule = ruleFor(label, report);
  if (!rule) return;
  const value = ruleValue(rule);

  const choices = radios.map((r, index) => ({ index: index, text: normalize(getOptionLabel(r)), value: normalize(r.value) }));
  const choice = pickChoice(choices, value);
  if (!choice) {
    report.no_choice.push({ label: label, value: value, choices: radios.map(getOptionLabel) });
    return;
  }
  const target = radios[choice.index];
  if (target.checked) return;
  const previous = radios.find((r) => r.checked);
  target.click();
  noteResult("filled", label, rule, value, previous ? getOptionLabel(previous) : "", report);
}

/* A group of check boxes sharing one question: tick the ones named in the
 * answer ("Days, Weekends"), untick the others. */
function handleCheckboxGroup(boxes, report) {
  if (!boxes.some((b) => isVisible(b) || (b.labels && b.labels[0] && isVisible(b.labels[0])))) return;
  const label = getGroupLabel(boxes);
  const rule = ruleFor(label, report);
  if (!rule) return;
  const value = ruleValue(rule);
  const wanted = splitAnswers(value);
  const choices = boxes.map((b, index) => ({ index: index, text: normalize(getOptionLabel(b)), value: normalize(b.value) }));
  const picked = new Set();
  for (const answer of wanted) {
    const choice = pickChoice(choices, answer);
    if (choice) picked.add(choice.index);
  }
  if (picked.size === 0) {
    report.no_choice.push({ label: label, value: value, choices: boxes.map(getOptionLabel) });
    return;
  }
  let changed = false;
  boxes.forEach((b, index) => { if (setChecked(b, picked.has(index))) changed = true; });
  if (changed) report.filled.push({ label: label, rule: rule.name });
}

/* A lone check box whose text is itself the question ("I am 18 or older").
 * It is only ever TICKED, never unticked: a box you ticked yourself (an
 * acknowledgement, say) is left alone. It is ticked when the saved answer
 * agrees with the box's wording: "Yes" for "I am authorized to work",
 * "No" for "I do NOT require sponsorship". */
function handleSingleCheckbox(box, report) {
  if (!(isVisible(box) || (box.labels && box.labels[0] && isVisible(box.labels[0])))) return;
  const label = getLabel(box);
  if (!label) return;
  const rule = findRule(label, "text");
  if (!rule || !rule.value) return;   // Unknown boxes ("I agree") are never touched or reported.
  const value = ruleValue(rule);
  let agrees;
  if (isYes(value)) agrees = !isNegatedStatement(label);
  else if (isNo(value)) agrees = isNegatedStatement(label);
  else agrees = pickChoice([{ index: 0, text: normalize(label), value: normalize(box.value) }], value) !== null;
  if (agrees && setChecked(box, true)) {
    report.filled.push({ label: label, rule: rule.name + " (ticked)" });
  }
}

function groupBy(items) {
  const groups = new Map();
  for (const item of items) {
    const key = item.name
      ? "name:" + item.name.replace(/\[\]$/, "")
      : (item.closest("fieldset, [role='radiogroup'], [role='group']") || item.parentElement);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }
  return Array.from(groups.values());
}

async function fillPageOnce() {
  const report = newReport();
  currentReport = report;
  const done = new Set();

  // 1. Text boxes, large text areas, drop-downs and type-ahead boxes
  for (const el of Array.from(document.querySelectorAll("input, textarea, select"))) {
    if (done.has(el) || !isFillableBox(el)) continue;
    done.add(el);
    await handleBox(el, report);
  }

  // 2. Date boxes
  for (const el of Array.from(document.querySelectorAll("input[type='date']"))) {
    if (done.has(el) || !isUsable(el)) continue;
    done.add(el);
    handleDateBox(el, report);
  }

  // 3. Rich-text editors
  for (const el of Array.from(document.querySelectorAll("[contenteditable=''], [contenteditable='true'], [role='textbox']"))) {
    if (done.has(el) || el.tagName === "INPUT" || el.tagName === "TEXTAREA" || !isUsable(el)) continue;
    if (el.isContentEditable === false) continue;
    done.add(el);
    handleRichText(el, report);
  }

  // 4. Button-style drop-downs (Workday and similar)
  const buttonSelector = "button[aria-haspopup='listbox'], [role='combobox']:not(input):not(select), [role='button'][aria-haspopup='listbox']";
  for (const el of Array.from(document.querySelectorAll(buttonSelector))) {
    if (done.has(el) || !isUsable(el)) continue;
    if (el.querySelector("input, select")) continue;   // A wrapper around a real box, handled above.
    done.add(el);
    await handleDropdownButton(el, report);
  }

  // 5. Yes/No style button groups, grouped by their shared name
  const radios = Array.from(document.querySelectorAll("input[type='radio']")).filter((r) => !r.disabled);
  for (const group of groupBy(radios)) {
    handleRadioGroup(group, report);
  }

  // 6. Check boxes: groups share a question, singles are their own question
  const boxes = Array.from(document.querySelectorAll("input[type='checkbox']")).filter((b) => !b.disabled);
  for (const group of groupBy(boxes)) {
    if (group.length > 1) handleCheckboxGroup(group, report);
    else handleSingleCheckbox(group[0], report);
  }

  // 7. Resume upload boxes (only when the program sends a "file" rule)
  if (compiledRules.some((rule) => rule.kind === "file")) {
    for (const el of Array.from(document.querySelectorAll("input[type='file']"))) {
      if (el.disabled) continue;
      if (!findRule(getLabel(el), "file")) continue;
      await attachResume(el, report);
    }
  }

  delete report.seen;
  const somethingToSay = ["filled", "recognized_empty", "unmatched", "no_choice", "errors"].some((k) => report[k].length > 0);
  if (somethingToSay) {
    await browser.runtime.sendMessage({ type: "report", report: report });
  }
  return report.filled.length;
}

/* One click on the toolbar button = one fill pass over this frame. */
async function onFillRequest(rules) {
  if (fillRunning) return { skipped: true };
  fillRunning = true;
  try {
    compiledRules = compileRules(rules || []);
    return { filled: await fillPageOnce() };
  } catch (err) {
    console.warn("[Job Application Custom Autofiller] Filling failed on " + location.href + ": " + err);
    return { error: String(err) };
  } finally {
    fillRunning = false;
  }
}

browser.runtime.onMessage.addListener((message) => {
  if (message.type === "fill") {
    return onFillRequest(message.rules);
  }
  return undefined;
});
