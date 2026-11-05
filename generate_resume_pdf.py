import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
HTML_PATH = ASSETS_DIR / "resume.html"
PDF_PATH = ASSETS_DIR / "resume.pdf"

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  @page { margin: 20mm; size: A4; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #222;
    line-height: 1.4;
    font-size: 10pt;
    margin: 0;
    padding: 0;
  }
  h1 { font-size: 20pt; margin: 0 0 2px 0; color: #111; letter-spacing: -0.5px; }
  .subtitle { font-size: 11pt; font-weight: 600; color: #333; margin-bottom: 6px; }
  .contact { font-size: 9pt; color: #555; margin-bottom: 12px; border-bottom: 1px solid #ddd; padding-bottom: 8px; }
  .contact a { color: #0066cc; text-decoration: none; }
  h2 { font-size: 11pt; text-transform: uppercase; border-bottom: 1.5px solid #222; padding-bottom: 3px; margin: 12px 0 6px 0; letter-spacing: 0.5px; color: #111; }
  .impact-grid { display: flex; justify-content: space-between; margin-bottom: 10px; background: #f8f9fa; padding: 8px; border-radius: 4px; }
  .impact-card { flex: 1; padding: 0 6px; }
  .impact-val { font-weight: bold; font-size: 10pt; color: #0066cc; margin-bottom: 2px; }
  .impact-desc { font-size: 8pt; color: #444; }
  .job { margin-bottom: 10px; }
  .job-header { display: flex; justify-content: space-between; font-weight: bold; font-size: 9.5pt; color: #111; }
  .job-date { font-weight: normal; color: #666; font-size: 8.5pt; }
  ul { margin: 4px 0 6px 18px; padding: 0; }
  li { margin-bottom: 3px; font-size: 9pt; }
  .skills-sec { font-size: 8.5pt; line-height: 1.5; }
  .skills-sec strong { color: #222; }
</style>
</head>
<body>
  <h1>Jackson Ray</h1>
  <div class="subtitle">Technical Consultant — Automation, Data Analytics & Systems Architecture</div>
  <div class="contact">
    Montreal, QC · Tel: 437-673-4543 · jacksonzhuang@cmail.carleton.ca · 
    <a href="https://linkedin.com/in/jacksonray07">linkedin.com/in/jacksonray07</a> · 
    <a href="https://github.com/jacksonzhuang07">github.com/jacksonzhuang07</a>
  </div>

  <h2>Profile</h2>
  <p style="margin: 4px 0; font-size: 9pt;">
    Automation-focused technical consultant with experience designing and deploying Python, REST API, OCR/AI, SQL, and Power BI solutions across enterprise and federal government environments. Proven record of improving efficiency, modernizing workflows, and translating operational pain points into scalable technical systems.
  </p>

  <h2>Key Consulting Impact</h2>
  <div class="impact-grid">
    <div class="impact-card"><div class="impact-val">86% FASTER</div><div class="impact-desc">Cut proposal processing (49 to 7 min), projected $90k+ annual savings.</div></div>
    <div class="impact-card"><div class="impact-val">500+ HRS / YR</div><div class="impact-desc">Automated batch documentation and request workflows across teams.</div></div>
    <div class="impact-card"><div class="impact-val">200% FASTER QA</div><div class="impact-desc">Increased federal QA testing with Selenium/Python, saving 10 hrs/wk.</div></div>
    <div class="impact-card"><div class="impact-val">1 DAY &rarr; 2 HRS</div><div class="impact-desc">Reduced compliance reporting effort with automated Power BI pipelines.</div></div>
  </div>

  <h2>Professional Experience</h2>
  <div class="job">
    <div class="job-header"><span>Continuous Improvement Consultant, Automation &middot; Omnitrans</span><span class="job-date">Sept 2025 – Present</span></div>
    <ul>
      <li>Built end-to-end pricing and quotation platform (Python, REST APIs, OCR, NLP, Supabase, Streamlit, Azure) cutting proposal time from 49 min to under 7.</li>
      <li>Engineered enterprise automation pipeline connecting API data histories, customer invoices, and documentation workflows end to end.</li>
      <li>Deployed OCR/AI batch processing system extracting document data into standardized templates, processing up to 10,000 jobs per batch.</li>
      <li>Developed Python/API bulk request-generation GUI enabling operators to submit 100 service requests at once (300% throughput boost).</li>
    </ul>
  </div>

  <div class="job">
    <div class="job-header"><span>Oracle Software Consultant (Contract) &middot; Employment and Social Development Canada</span><span class="job-date">Aug 2024 – Jan 2025</span></div>
    <ul>
      <li>Developed Selenium-based Python regression and integration test suites for Oracle PeopleSoft, accelerating QA speed by 200%.</li>
      <li>Contributed to full-stack development of department-wide PeopleSoft HR platform using PeopleCode, JavaScript, and HTML.</li>
    </ul>
  </div>

  <div class="job">
    <div class="job-header"><span>Database Consultant &middot; Environment and Climate Change Canada</span><span class="job-date">Dec 2022 – Sept 2023</span></div>
    <ul>
      <li>Designed relational database (Azure SQL, Access) for RIMS modernizing Schedule 1 substances data supporting 100% federal compliance.</li>
      <li>Built Power BI refresh workflows reducing reporting effort from 1 day to under 2 hours; built Python/Pandas ETL pipelines.</li>
    </ul>
  </div>

  <h2>Professional Skills</h2>
  <div class="skills-sec">
    <strong>Automation & Scripting:</strong> Python, Pandas, Selenium, PowerShell, Bash, VBA<br>
    <strong>APIs & Cloud:</strong> REST APIs, Third-Party Vendor APIs, Oracle PeopleSoft, LLM APIs, Microsoft Azure, Supabase, Vercel<br>
    <strong>AI/OCR & Data:</strong> Tesseract OCR, NLP Workflows, SQL, Azure SQL, PostgreSQL, Power BI, Excel<br>
    <strong>Web & Internal Tools:</strong> JavaScript, HTML, CSS, Streamlit, Tkinter, Git, Jira, Confluence, Agile
  </div>

  <h2>Education & Certifications</h2>
  <div class="job">
    <div class="job-header"><span>BSc in Computer Science, Honours (Co-op) &middot; Carleton University</span><span class="job-date">2020 – 2025</span></div>
    <div style="font-size: 8.5pt; color: #444; margin-top: 2px;">
      Dean's List (2020–2025) &middot; Certifications: Certified Pendo Project Manager &middot; AWS Certified Solutions Architect (in progress) &middot; Languages: English, French, Mandarin
    </div>
  </div>
</body>
</html>
"""

def generate_pdf():
    os.makedirs(ASSETS_DIR, exist_ok=True)
    HTML_PATH.write_text(HTML_CONTENT, encoding="utf-8")
    print(f"[*] Compiling resume HTML to PDF: {PDF_PATH}...")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(HTML_CONTENT)
        page.pdf(
            path=str(PDF_PATH),
            format="A4",
            print_background=True,
            margin={"top": "15mm", "bottom": "15mm", "left": "15mm", "right": "15mm"}
        )
        browser.close()

    print("[OK] Resume PDF successfully generated and saved at assets/resume.pdf!")

if __name__ == "__main__":
    generate_pdf()
