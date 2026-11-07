"""Seed data: the workflow's confirmed screening facts (Nov 5, 2026 set),
settings, a few real ledger entries, and the simulated runner's job pool.

The live workflow's confirmed facts supersede the stale values in the
repo's config.yaml / profile.json (e.g. salary 95000, Python-developer
target roles) wherever they conflict.
"""

# key, label, value
SCREENING_FACTS: list[tuple[str, str, str]] = [
    ("canadian_citizen", "Canadian citizen", "Yes"),
    ("authorized_canada", "Authorized to work in Canada", "Yes"),
    ("sponsorship_canada", "Sponsorship needed for Canada", "No"),
    ("us_authorization", "US work authorization", "No"),
    ("drivers_licence", "Driver's licence", "Yes"),
    ("french_bilingual", "French (bilingual)", "Bilingual (English/French)"),
    ("pm_experience_years", "Years of project-management experience", "6"),
    ("product_experience_years", "Years of product / digital-product experience", "6"),
    ("ai_tools_years", "Years with AI tools", "8+"),
    ("aws_years", "Years with AWS", "8+"),
    ("jira_years", "Years with Jira/Confluence", "8+"),
    ("notice_period", "Notice period", "2 weeks"),
    ("travel", "Open to travel if the role requires it", "Yes"),
    ("secondary_employment", "Secondary employment", "No"),
    ("pronouns", "Pronouns (when forced)", "Prefer not to specify"),
    ("linkedin_url", "LinkedIn profile URL", "linkedin.com/in/jacksonray07"),
    ("address", "Street address", "235 Sherbrooke Ouest, Apt 710, Montreal, QC H2X 1X8"),
    ("education", "Education", "BSc Computer Science Honours (Co-op), Carleton University, 2025"),
    ("salary_fallback", "Salary fallback when no band is posted", "90000"),
    ("background_check", "Willing to undergo pre-employment screening / background check", "Yes"),
]

AI_USE_STATEMENT = (
    "I use AI tools extensively in my daily work — for research, analysis, "
    "documentation, and drafting — as a productivity layer under my own "
    "direction. I personally review, verify, and take responsibility for "
    "everything I deliver; AI assists my process but my professional "
    "judgment and accountability are my own. I use AI agents and automations "
    "to autonomously run routine tasks, manage errands and workflows, develop "
    "new software, and analyze data — including financial and health data. I "
    "bring this same mindset into the workplace, using AI to improve "
    "efficiency, boost productivity, and free up resources for further growth."
)

DEFAULT_SETTINGS: list[tuple[str, str]] = [
    ("target_roles", "technical project manager, program manager, technical product manager, product owner, data consulting, solutions architect, IT project manager, delivery manager, implementation manager, implementation consultant, ERP/CRM project manager"),
    ("excluded_types", "hard engineering, software development, software engineer, developer, devops"),
    ("locations", "Montreal/Greater Montreal hybrid or onsite; Quebec/Canada remote; worldwide remote; US remote only when Canada-based applicants are accepted"),
    ("salary_rule", "If a salary figure is mandatory: top of the posted band; if no band is posted, 90000."),
    ("salary_fallback", "90000"),
    ("ai_use_statement", AI_USE_STATEMENT),
    ("override_date", ""),
]

# Real entries from the live workflow's Nov 6, 2026 run (proof on record).
SEED_APPLICATIONS = [
    dict(company="Parkland", role="Manager Retail Technology Projects", source="indeed",
         url="https://ca.indeed.com/viewjob?jk=410709e1e7d4bdbc",
         proof="Your application has been submitted! (Indeed confirmation email, Nov 6 2026 11:41 EST)",
         status="submitted", delivery_status="delivered", date="2026-11-06"),
    dict(company="KIK Consumer Products", role="Project Manager", source="indeed",
         url="https://ca.indeed.com/viewjob?jk=e184ab5ae839b912",
         proof="Your application has been submitted! (on-screen, Nov 6 2026) — Indeed emailed a delivery-failure notice 11:52 EST: employer's ability to receive applications is affected; flagged for retry via company site.",
         status="submitted", delivery_status="failed", date="2026-11-06"),
    dict(company="Jobgether", role="Principal Technical Program Manager", source="linkedin",
         url="https://www.linkedin.com/jobs/view/4486567455/",
         proof="Your application was sent to Jobgether! (on-screen, Nov 5 2026)",
         status="submitted", delivery_status="delivered", date="2026-11-05"),
]

# Real open stump from the live workflow (Nov 6, 2026 run).
SEED_STUMPS = [
    dict(question="What is your current location (State)?",
         company="Kobie", role="Operations Manager",
         url="https://www.linkedin.com/jobs/view/4460614353/",
         fact_key="address_state"),
]

# Real outreach drafts from the live workflow (Nov 6, 2026) — draft mode only.
SEED_DRAFTS = [
    dict(poster="Brian McKenna", company="Quarry Consulting",
         role="Technical Business Systems Analyst (Microsoft 365 / SharePoint, 6 months, Remote)",
         post_url="https://www.linkedin.com/feed/update/urn:li:activity:7524211579857305600/",
         channel="comment",
         text="Hi Brian — I saw your post about the M365/SharePoint Business Systems Analyst opening. My background is in automation and technical delivery for a national logistics operation, with heavy SharePoint/M365 workflow work. Happy to send my resume if useful — is connecting the best next step?"),
    dict(poster="Jenna Craig", company="Procom",
         role="Business Systems Analyst (Cyber Security Assurance, contract)",
         post_url="https://www.linkedin.com/feed/update/urn:li:activity:7524215680880037888/",
         channel="comment",
         text="Hi Jenna — your Business Systems Analyst post (cyber security assurance, hybrid Ottawa or remote) caught my eye. I work in automation and client-facing technical delivery, including compliance-adjacent systems work. If the role is open to Montreal-based candidates, I'd welcome a short conversation; I can send my resume over."),
]

# Sample feed posts the simulated runner turns into outreach drafts
# (max 3 per run, draft mode only — never sent).
SAMPLE_FEED_POSTS = [
    dict(poster="Marie Dubois", company="Northwind Labs", role="Technical Project Manager",
         post_url="https://www.linkedin.com/feed/update/urn:li:activity:sim-northwind-001/",
         channel="comment",
         text="Hi Marie — I saw your post that Northwind Labs is hiring a Technical Project Manager in Montreal. I currently do client-facing technical delivery and automation for a national courier operation, bilingual EN/FR. If helpful, I can send my resume — is a connection the best next step?"),
    dict(poster="Alex Chen", company="RemoteWorks", role="Senior Product Manager",
         post_url="https://www.linkedin.com/feed/update/urn:li:activity:sim-remoteworks-002/",
         channel="comment",
         text="Hi Alex — your Senior Product Manager opening (remote, Canada) matches my background: 6 years across product and project delivery, currently shipping automation for enterprise clients. Happy to share my resume if you'd like a look."),
]

# Simulated job pool. Indeed is deliberately NOT first in this list — the
# runner must sort by the sweep rule (Indeed first, freshest first).
SAMPLE_POOL: list[dict] = [
    dict(company="RemoteWorks", title="Senior Product Manager", platform="linkedin",
         location_scope="canada_remote", posted_hours_ago=3,
         url="https://www.linkedin.com/jobs/view/sim-remoteworks-spm/",
         questions=[{"text": "Are you authorized to work in Canada?", "fact_key": "authorized_canada"}]),
    dict(company="Northwind Labs", title="Technical Project Manager", platform="indeed",
         location_scope="montreal", posted_hours_ago=2,
         url="https://ca.indeed.com/viewjob?jk=sim-northwind-tpm",
         questions=[{"text": "Are you authorized to work in Canada?", "fact_key": "authorized_canada"},
                    {"text": "Do you speak French?", "fact_key": "french_bilingual"}]),
    dict(company="Parkland", title="Manager Retail Technology Projects", platform="indeed",
         location_scope="montreal", posted_hours_ago=1,
         url="https://ca.indeed.com/viewjob?jk=410709e1e7d4bdbc", questions=[]),
    dict(company="CloudScale", title="Senior Software Engineer", platform="indeed",
         location_scope="canada_remote", posted_hours_ago=4,
         url="https://ca.indeed.com/viewjob?jk=sim-cloudscale-swe", questions=[]),
    dict(company="SecureGov Consulting", title="Program Manager", platform="indeed",
         location_scope="canada_remote", posted_hours_ago=5,
         url="https://ca.indeed.com/viewjob?jk=sim-securegov-pm",
         questions=[{"text": "Do you hold an active Government of Canada security clearance?", "fact_key": "security_clearance"}]),
    dict(company="Liberty Health", title="Product Manager", platform="indeed",
         location_scope="us_remote_canada_ok", requires_us_auth_hard=True, posted_hours_ago=6,
         url="https://www.indeed.com/viewjob?jk=sim-liberty-pm", questions=[]),
    dict(company="DataForge", title="Data Consultant", platform="indeed",
         location_scope="canada_remote", posted_hours_ago=7,
         url="https://ca.indeed.com/viewjob?jk=sim-dataforge-dc",
         questions=[{"text": "How many years of experience do you have with AI tools?", "fact_key": "ai_tools_years"}]),
    dict(company="Orion ERP Group", title="ERP Project Manager", platform="indeed",
         location_scope="montreal", posted_hours_ago=9,
         url="https://ca.indeed.com/viewjob?jk=sim-orion-erp-pm",
         questions=[{"text": "What is your notice period?", "fact_key": "notice_period"}]),
    dict(company="Montreal AI Labs", title="Solutions Architect", platform="linkedin",
         location_scope="montreal", posted_hours_ago=8,
         url="https://www.linkedin.com/jobs/view/sim-mtlai-sa/",
         questions=[{"text": "Are you willing to travel if the role requires it?", "fact_key": "travel"}]),
    dict(company="FinServe", title="Implementation Manager", platform="linkedin",
         location_scope="canada_remote", posted_hours_ago=10, delivery="failed",
         url="https://www.linkedin.com/jobs/view/sim-finserve-im/",
         questions=[{"text": "Do you have a driver's licence?", "fact_key": "drivers_licence"}]),
    dict(company="ShopStack", title="Product Owner", platform="linkedin",
         location_scope="toronto_onsite", posted_hours_ago=11,
         url="https://www.linkedin.com/jobs/view/sim-shopstack-po/", questions=[]),
    dict(company="AnalyticsPro", title="Analytics Consultant", platform="linkedin",
         location_scope="canada_remote", posted_hours_ago=12, band_low=120000, band_high=150000,
         url="https://www.linkedin.com/jobs/view/sim-analyticspro-ac/",
         questions=[{"text": "What are your salary expectations?", "fact_key": "salary_expectation"}]),
]
