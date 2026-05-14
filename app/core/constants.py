JWT_ALGORITHM = "HS256"
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"

MAJOR_JOB_BOARDS = [
    {"url": "https://www.naukri.com/jobs-in-india", "source_type": "naukri"},
    {"url": "https://www.linkedin.com/jobs/search/?location=India", "source_type": "linkedin"},
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
