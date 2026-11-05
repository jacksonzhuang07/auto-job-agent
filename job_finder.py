import logging
from typing import List, Dict, Any
from jobspy import scrape_jobs

logger = logging.getLogger(__name__)

class JobFinder:
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("search", {})

    def find_jobs(self) -> List[Dict[str, Any]]:
        """
        Scrapes job listings from Indeed and LinkedIn using JobSpy.
        """
        search_term = self.config.get("keywords", "Software Engineer")
        location = self.config.get("location", "United States")
        is_remote = self.config.get("is_remote", True)
        results_per_platform = self.config.get("results_per_platform", 15)

        logger.info(f"Searching for '{search_term}' in '{location}' (Remote: {is_remote})...")

        try:
            # scrape_jobs supports: "linkedin", "indeed", "glassdoor", "zip_recruiter"
            jobs_df = scrape_jobs(
                site_name=["indeed", "linkedin"],
                search_term=search_term,
                location=location,
                results_wanted=results_per_platform,
                hours_old=24,  # Focus on fresh postings from the past day
                country_indeed="USA",
                is_remote=is_remote,
            )

            if jobs_df.empty:
                logger.warning("No jobs found matching criteria.")
                return []

            # Clean and normalize into standard dictionaries
            records = jobs_df.to_dict(orient="records")
            formatted_jobs = []

            for r in records:
                job_url = str(r.get("job_url", "")).strip()
                if not job_url:
                    continue

                formatted_jobs.append({
                    "id": str(r.get("id", job_url)),
                    "platform": str(r.get("site", "unknown")).lower(),
                    "title": str(r.get("title", "")),
                    "company": str(r.get("company", "")),
                    "location": str(r.get("location", "")),
                    "job_url": job_url,
                    "description": str(r.get("description", "")),
                    "is_direct_apply": bool(r.get("is_direct_apply", False)), # True if Easy Apply or Indeed apply
                })

            logger.info(f"Discovered {len(formatted_jobs)} postings across LinkedIn and Indeed.")
            return formatted_jobs

        except Exception as e:
            logger.error(f"Error querying job sources: {e}", exc_info=True)
            return []
