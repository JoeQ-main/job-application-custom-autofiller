r"""
field_rules.py - The list of job-application fields this program knows about.

Each entry in PROFILE_FIELDS and APPLICATION_FIELDS describes ONE field:

    (key, display_label, label_pattern, multiline)

    key            Name used to store the value in autofill_data.json.
    display_label  Text shown next to the box in the program window.
    label_pattern  A regular expression (case-insensitive) that is tested
                   against the label text of each box on the web page.
                   Leave it as "" for fields that are only used inside
                   the cover letter (company, job title, ...).
    multiline      True = show a large text box in the program window.

ORDER MATTERS: the browser extension uses the FIRST pattern that matches a
label. Specific patterns (e.g. "phone country code", "first name") must come
before general ones (e.g. "phone", "name").

The patterns are sent to the Firefox extension and run as JavaScript
regular expressions, so only use syntax both Python and JavaScript share:
  \b  \s  \d  .  *  +  ?  |  ( )  (?: )  (?! )  [ ]  ^  $
"""

# ---------------------------------------------------------------------------
# Fields that stay the same for every application ("My Profile" tab).
# Section headings are rows whose key starts with "#".
# ---------------------------------------------------------------------------
PROFILE_FIELDS = [
    ("#contact", "Contact information", "", False),
    ("email", "Email", r"e-?mail", False),
    ("phone_country_code", "Phone country code", r"country\s*code|phone.*code|dialing code", False),
    ("alt_phone", "Alternate phone", r"(alternate|alternative|secondary|other|second|home|work|evening|day)\s*(phone|number|tel)", False),
    ("phone", "Phone", r"phone|mobile|cell", False),
    ("preferred_name", "Preferred name", r"preferred\s*(first\s*|last\s*)?name|nick\s*name|name\s*you\s*(go|prefer)|goes?\s*by|known\s*as|chosen\s*name", False),
    ("first_name", "First name", r"first\s*name|given\s*name|^first$", False),
    ("middle_name", "Middle name / initial", r"middle\s*(name|initial)", False),
    ("last_name", "Last name", r"last\s*name|surname|family\s*name|^last$", False),
    ("name_suffix", "Name suffix (Jr., III)", r"suffix", False),
    ("full_name", "Full name", r"^(your\s*)?(full\s*|legal\s*)?name$|full\s*name|legal\s*name|signature|^name$", False),
    ("pronouns", "Pronouns", r"pronoun", False),
    ("signature_date", "Today's date ({today} = the date you click)", r"^date$|today'?s\s*date|date\s*(signed|of\s*(application|signature))|^signed\s*on", False),

    ("#address", "Address", "", False),
    ("address_line1", "Street address", r"street|address\s*line\s*1|address\s*1|^address$|home\s*address|mailing\s*address", False),
    ("address_line2", "Address line 2 (apt, suite)", r"address\s*line\s*2|address\s*2|apt|suite", False),
    ("city", "City", r"\bcity\b|\btown\b", False),
    ("state", "State", r"\bstate\b|province|region", False),
    ("zip_code", "ZIP / postal code", r"\bzip|postal", False),
    ("country", "Country", r"country", False),
    ("location", "Location (City, State)", r"location|where.*(live|located|based)|city,\s*state", False),
    ("time_zone", "Time zone", r"time\s*zone", False),

    ("#links", "Online profiles", "", False),
    ("linkedin_url", "LinkedIn URL", r"linked\s*in", False),
    ("github_url", "GitHub URL", r"git\s*hub", False),
    ("website_url", "Website / portfolio", r"website|portfolio|personal\s*(site|url|page)|\burl\b", False),

    ("#work", "Work history", "", False),
    ("current_title", "Current / most recent job title", r"(current|most\s*recent|present)\s*(job\s*)?(title|position|role)", False),
    ("current_company", "Current / most recent employer", r"(current|most\s*recent|present)\s*(company|employer)|^employer$", False),
    ("years_experience", "Total years of work experience", r"^(how\s*many\s*)?(total\s*)?years\s*of\s*(professional\s*|work\s*|relevant\s*)?experience(\s*do\s*you\s*have)?\??$", False),
    ("headline", "Professional headline", r"headline|professional\s*title", False),
    ("summary", "Professional summary", r"summary|about\s*(you|yourself|me)|tell\s*us\s*about\s*yourself|describe\s*yourself", True),
    ("skills", "Skills", r"^skills|key\s*skills|technical\s*skills|skill\s*set", True),
    ("languages", "Languages spoken", r"language", False),
    ("employment_start", "Most recent job: start date", r"(employment|job|position)\s*(start|from)\b|work\s*(start|from)\s*(date|month|year)|start\s*(month|year)|date\s*started|from\s*(date|month|year)|^from$", False),
    ("employment_end", "Most recent job: end date", r"(employment|job|position)\s*(end|to)\b|work\s*end\s*(date|month|year)|end\s*(date|month|year)|date\s*(ended|left)|to\s*(date|month|year)|^to$", False),
    ("job_duties", "Most recent job: duties / responsibilities", r"duties|responsibilit|description\s*of\s*(work|role|job|position)|job\s*description|what\s*did\s*you\s*do", True),
    ("reason_for_leaving", "Most recent job: reason for leaving", r"reason\s*(for|of)\s*leaving|why\s*(did|do)\s*you\s*(leave|want\s*to\s*leave)", False),
    ("supervisor_name", "Most recent job: supervisor name", r"supervisor|manager'?s?\s*name", False),
    ("may_contact_employer", "May we contact your current employer? (Yes/No)", r"may\s*we\s*contact|contact\s*(your\s*)?(current|previous|this|present)\s*employer|permission\s*to\s*contact", False),
    ("previous_title", "Previous job title", r"(previous|prior|last|former)\s*(job\s*)?(title|position|role)", False),
    ("previous_company", "Previous employer", r"(previous|prior|last|former)\s*(company|employer)", False),
    ("employment_gaps", "Explanation of employment gaps", r"\bgaps?\b", True),

    ("#education", "Education", "", False),
    ("completed_bachelors", "Completed a Bachelor's degree? (Yes/No)", r"completed.*bachelor|have\s*a\s*bachelor|bachelor'?s\s*degree\s*\?", False),
    ("education_level", "Highest education level", r"highest.*(education|degree)|education\s*level|level\s*of\s*education", False),
    ("school", "School / university", r"school|university|college|institution", False),
    ("degree", "Degree", r"^degree|degree\s*(type|earned|obtained)", False),
    ("major", "Major / field of study", r"major|field\s*of\s*study|discipline|area\s*of\s*study", False),
    ("graduation_year", "Graduation year", r"graduat", False),
    ("gpa", "GPA", r"\bgpa\b|grade\s*point", False),
    ("minor", "Minor", r"\bminor\b", False),
    ("currently_enrolled", "Currently a student? (Yes/No)", r"currently\s*(enrolled|attending|a\s*student)|still\s*(attending|enrolled|in\s*school)", False),
    ("education_dates", "Dates attended", r"dates?\s*(attended|of\s*attendance)|attended\s*from|years?\s*attended", False),
    ("certifications", "Certifications", r"certification|certificate", True),

    ("#references", "References (one set of details; used for every reference box)", "", False),
    ("reference_name", "Reference: name", r"reference.*name|name.*reference", False),
    ("reference_phone", "Reference: phone", r"reference.*(phone|number|tel)", False),
    ("reference_email", "Reference: email", r"reference.*e-?mail", False),
    ("reference_company", "Reference: company", r"reference.*(company|employer|organi[sz]ation)", False),
    ("reference_title", "Reference: job title", r"reference.*(title|position)", False),
    ("reference_relationship", "Reference: relationship to you", r"relationship|reference.*relation", False),
    ("references", "References (free text, for one big box)", r"^(professional\s*|personal\s*|work\s*)?references?\b|list.*references", True),

    ("#eligibility", "Work eligibility and logistics", "", False),
    ("authorized_to_work", "Authorized to work in the US? (Yes/No)", r"authori[sz]ed\s*to\s*work|legally\s*(authorized|eligible|able|permitted)|eligible\s*to\s*work|right\s*to\s*work", False),
    ("require_sponsorship", "Require visa sponsorship? (Yes/No)", r"sponsor", False),
    ("over_18", "At least 18 years old? (Yes/No)", r"18\s*years|at\s*least\s*18|over\s*18|\b18\s*or\s*older|legal\s*age", False),
    ("background_check", "Willing to do a background check? (Yes/No)", r"background\s*(check|screen)", False),
    ("drug_test", "Willing to do a drug test? (Yes/No)", r"drug\s*(test|screen)", False),
    ("drivers_license", "Valid driver's license? (Yes/No)", r"driver'?s?\s*licen[cs]e", False),
    ("willing_to_relocate", "Willing to relocate? (Yes/No)", r"relocat", False),
    ("commute_ok", "Able to commute to the job? (Yes/No)", r"commut", False),
    ("remote_ok", "Comfortable working remotely? (Yes/No)", r"remote|from\s*home|telecommut|hybrid", False),
    ("start_date", "Available start date", r"available\s*(to\s*)?start|when\s*can\s*you\s*start|earliest.*start|availability\s*date|desired\s*start|^start\s*date$|date\s*available", False),
    ("notice_period", "Notice period", r"notice\s*period", False),
    ("current_salary", "Current / most recent salary", r"current\s*(salary|pay|compensation|rate)|salary\s*history|(most\s*recent|last|previous)\s*(salary|pay)", False),
    ("desired_salary", "Desired salary", r"salary|compensation|desired\s*pay|pay\s*(expectation|requirement|rate)|hourly\s*rate|wage", False),
    ("employment_type", "Employment type wanted (Full-time / Part-time)", r"employment\s*type|type\s*of\s*(employment|position|work)|full[\s-]*time|part[\s-]*time|position\s*type|job\s*type|hours\s*type", False),
    ("weekends_ok", "Able to work weekends / holidays? (Yes/No)", r"weekend|holiday", False),
    ("nights_ok", "Able to work nights / evenings? (Yes/No)", r"(night|evening)(?!\s*(phone|number|tel|contact|e-?mail))", False),
    ("overtime_ok", "Willing to work overtime? (Yes/No)", r"overtime", False),
    ("hours_per_week", "Hours available per week", r"hours\s*(per|a|each)\s*week|how\s*many\s*hours|weekly\s*hours", False),
    ("shift_availability", "Shifts / days available (comma separated for check boxes)", r"shift|^availability$|available\s*(days|hours|to\s*work)|days\s*(available|you\s*can\s*work)|work\s*availability|which\s*days", False),
    ("travel_ok", "Willing to travel? (Yes/No or %)", r"travel", False),
    ("reliable_transportation", "Reliable transportation? (Yes/No)", r"transportation", False),
    ("security_clearance", "Security clearance", r"clearance", False),
    ("work_location_preference", "Preferred work location / office", r"preferred\s*(work\s*)?(location|office|site)|office\s*location|work\s*(location|site)\s*preference|which\s*(location|office)", False),
    ("currently_employed", "Currently employed? (Yes/No)", r"currently\s*(employed|working)|current\s*employee|^employed\?*$", False),
    ("felony", "Ever convicted of a crime? (Yes/No)", r"felony|convict|criminal|misdemeanor", False),
    ("relatives_employed", "Relatives employed at this company? (Yes/No)", r"relative|family\s*member", False),
    ("non_compete", "Bound by a non-compete agreement? (Yes/No)", r"non[\s-]*compete|non[\s-]*solicit|restrictive\s*covenant", False),
    ("referral_source", "How did you hear about us? ({site} = Indeed/LinkedIn)", r"how\s*did\s*you\s*(hear|find|learn)|referral\s*source|^source$", False),
    ("employee_referral", "Referred by an employee? (Yes/No)", r"\breferred\s*by|employee\s*referral|were\s*you\s*referred", False),
    ("previously_employed", "Previously worked for this company? (Yes/No)", r"(previously|ever|before)\s*(been\s*)?(worked|employed)", False),

    ("#eeo", "Voluntary self-identification (leave blank to skip)", "", False),
    ("gender", "Gender", r"gender|\bsex\b", False),
    ("hispanic_latino", "Hispanic or Latino?", r"hispanic|latin[oax]", False),
    ("race", "Race / ethnicity", r"\brace\b|ethnic", False),
    ("veteran_status", "Veteran status", r"veteran", False),
    ("disability_status", "Disability status", r"disabilit", False),
]

# ---------------------------------------------------------------------------
# Fields that change with every job ("This Application" tab).
# These are cleared when you click "New Application".
# ---------------------------------------------------------------------------
APPLICATION_FIELDS = [
    ("company", "Company name (used in the cover letter)", "", False),
    ("job_title", "Job title (cover letter; also fills \"Position applied for\")", r"position\s*(applied|applying|desired|of\s*interest|sought)|job\s*(applied|applying)\s*for|desired\s*(position|role|job)|which\s*(position|role)|title\s*of\s*(the\s*)?(position|job)", False),
    ("hiring_manager", "Hiring manager name (cover letter greeting)", "", False),
    ("referral_name", "Name of the employee who referred you (if any)", r"\breferr(ed|al|er)?.*name|who\s*referred|name\s*of\s*(the\s*)?(employee|person).*\breferr", False),
    ("why_company", "Why do you want to work here?", r"why\s*(do\s*you\s*want|are\s*you\s*interested|this\s*(company|role|position|job))|interest(ed)?\s*in\s*(this|our|the)\s*(company|role|position|job)|what\s*attracted", True),
    ("why_fit", "Why are you a good fit?", r"why\s*(should\s*we|are\s*you\s*a\s*good|would\s*you\s*be)|good\s*fit|best\s*candidate|what\s*makes\s*you", True),
    ("additional_info", "Additional information / message to hiring manager", r"additional\s*(information|comments|details)|anything\s*else|message\s*to\s*(the\s*)?hiring", True),
    ("cover_letter_override", "Custom cover letter for this job (blank = use default)", "", True),
]

# Pattern for cover-letter boxes on the web page. The value comes from the
# "Cover Letter" tab (or the custom one above), not from a profile field.
COVER_LETTER_PATTERN = r"cover\s*letter|letter\s*of\s*(interest|introduction|motivation)|motivation\s*letter"

# Pattern for resume upload boxes (used only if "Attach resume file" is on).
RESUME_FILE_PATTERN = r"resume|résumé|\bcv\b|curriculum"

# Profile sections whose patterns are checked BEFORE all other profile
# fields. These are full-sentence questions ("Are you authorized to work in
# this country?") that contain words like "country" or "city", so they must
# get the first chance to match.
SECTIONS_MATCHED_FIRST = ["#references", "#eligibility", "#eeo"]

# Values a brand-new data file starts with (everything else starts blank).
# {today} is replaced with the current date each time you click.
DEFAULT_VALUES = {"signature_date": "{today}"}
