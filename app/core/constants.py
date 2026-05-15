JWT_ALGORITHM = "HS256"
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"

MAJOR_JOB_BOARDS = [
    {"url": "https://www.naukri.com/jobs-in-india", "source_type": "naukri"},
    {"url": "https://internshala.com/internships", "source_type": "internshala"},
    {"url": "https://wellfound.com/jobs?locations[]=India", "source_type": "wellfound"},
]

MINOR_JOB_BOARDS = [
    {"url": "https://unstop.com/opportunities", "source_type": "unstop"},
    {"url": "https://cutshort.io/jobs", "source_type": "cutshort"},
    {"url": "https://www.indeed.co.in/jobs", "source_type": "indeed"},
    {"url": "https://www.glassdoor.co.in/Job/india-jobs-SRCH_IL.0,5_IN115.htm", "source_type": "glassdoor"},
    {"url": "https://www.iimjobs.com/j/technology", "source_type": "iimjobs"},
    {"url": "https://www.hirist.tech", "source_type": "hirist"},
    {"url": "https://hn.algolia.com/api/v1/search?query=who+is+hiring&tags=ask_hn", "source_type": "hackernews"},
]

BOARD_RATE_LIMITS: dict[str, dict[str, int]] = {
    "naukri": {"min_delay_s": 3, "max_delay_s": 8, "max_jobs_per_run": 50},
    "linkedin": {"min_delay_s": 8, "max_delay_s": 15, "max_jobs_per_run": 25},
    "internshala": {"min_delay_s": 2, "max_delay_s": 5, "max_jobs_per_run": 100},
    "wellfound": {"min_delay_s": 2, "max_delay_s": 6, "max_jobs_per_run": 50},
    "indeed": {"min_delay_s": 4, "max_delay_s": 10, "max_jobs_per_run": 30},
    "glassdoor": {"min_delay_s": 5, "max_delay_s": 12, "max_jobs_per_run": 20},
    "iimjobs": {"min_delay_s": 3, "max_delay_s": 7, "max_jobs_per_run": 50},
    "hirist": {"min_delay_s": 2, "max_delay_s": 5, "max_jobs_per_run": 50},
    "cutshort": {"min_delay_s": 2, "max_delay_s": 5, "max_jobs_per_run": 50},
    "unstop": {"min_delay_s": 2, "max_delay_s": 5, "max_jobs_per_run": 50},
    "hackernews": {"min_delay_s": 2, "max_delay_s": 4, "max_jobs_per_run": 50},
    "default": {"min_delay_s": 2, "max_delay_s": 5, "max_jobs_per_run": 50},
}
