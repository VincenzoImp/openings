"""Synthetic postings in every shape the collectors and manual input produce.

Each item is what a collector hands to ingestion: the archive fields plus ``raw``,
the provider's own row. ``released_payload`` is the observation payload releases up
to 0.17 (schema 8) stored for such an item: the whole validated input.
"""

from openings.identities import normalize_url
from openings.models import JobInput

TEXT = "Design, build and operate the synthetic platform services of Example. " * 12
# Every column of the vendored JobSpy row (JobPost), as its serializer emits it.
JOBSPY_ROW = {
    "id": None,
    "site": None,
    "job_url": "",
    "job_url_direct": None,
    "title": "",
    "company": None,
    "location": None,
    "date_posted": "2026-02-03",
    "job_type": "fulltime",
    "salary_source": None,
    "interval": None,
    "min_amount": None,
    "max_amount": None,
    "currency": None,
    "is_remote": False,
    "job_level": "mid-senior level",
    "job_function": "Engineering",
    "listing_type": None,
    "emails": None,
    "description": TEXT,
    "company_industry": "Software",
    "company_url": "https://example.org/company",
    "company_logo": None,
    "company_url_direct": None,
    "company_addresses": None,
    "company_num_employees": None,
    "company_revenue": None,
    "company_description": None,
    "skills": None,
    "experience_range": None,
    "company_rating": None,
    "company_reviews_count": None,
    "vacancy_count": None,
    "work_from_home_type": None,
}


def _item(key, title, company, location, url, metadata, raw, posting=TEXT):
    return {
        "source_key": key,
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "posting": posting,
        "metadata": metadata,
        "raw": raw,
    }


def _board(provider, identity, title, company, location, url, direct):
    row = {
        **JOBSPY_ROW,
        "id": identity,
        "site": provider,
        "job_url": url,
        "job_url_direct": direct,
        "title": title,
        "company": company,
        "location": location,
    }
    return _item(
        f"{provider}:{identity}",
        title,
        company,
        location,
        url,
        {
            "source": provider,
            "collector": "jobspy",
            "collector_version": "1.4.1",
            "is_remote": False,
            "job_type": "fulltime",
            "job_types": ["fulltime"],
            "date_posted": "2026-02-03",
            "salary": {},
            "external_id": identity,
            "description_complete": True,
            "description_status": "complete",
        },
        row,
    )


def _ats(kind, board, identity, title, url, raw, location="Berlin, Germany", **metadata):
    return _item(
        f"{kind}:{board}:{identity}",
        title,
        "Example " + kind.title(),
        location,
        url,
        {"ats": kind, "board": board, "external_id": str(identity), **metadata},
        raw,
    )


def provider_postings():
    """One or more postings per provider shape; several describe the same vacancies."""
    greenhouse = "https://boards.greenhouse.io/example/jobs/4001"
    lever = "https://jobs.lever.co/example/0f6c1d3e-aaaa-bbbb-cccc-000000000001"
    return [
        # Job boards (JobSpy rows): with and without the employer's own apply link.
        _board(
            "linkedin",
            "li-1001",
            "Platform Engineer",
            "Example Greenhouse",
            "Berlin, Germany",
            "https://www.linkedin.com/jobs/view/1001",
            greenhouse + "?gh_src=synthetic",
        ),
        _board(
            "linkedin",
            "li-1002",
            "Data Engineer",
            "Example Data",
            "Rome, Italy",
            "https://www.linkedin.com/jobs/view/1002",
            None,
        ),
        _board(
            "indeed",
            "in-2001",
            "Platform Engineer (m/f/d)",
            "Example Greenhouse GmbH",
            "Berlin",
            "https://www.indeed.com/viewjob?jk=2001",
            greenhouse,
        ),
        _board(
            "indeed",
            "in-2002",
            "Backend Engineer",
            "Example Lever",
            "Remote",
            "https://www.indeed.com/viewjob?jk=2002",
            lever + "/apply",
        ),
        _board(
            "glassdoor",
            "gd-3001",
            "Backend Engineer",
            "Example Lever",
            "Remote",
            "https://www.glassdoor.com/job-listing/j?jl=3001",
            "https://example.org/careers/backend?ref=glassdoor",
        ),
        # Company boards.
        _ats(
            "greenhouse",
            "example",
            4001,
            "Platform Engineer",
            greenhouse,
            {
                "id": 4001,
                "title": "Platform Engineer",
                "absolute_url": greenhouse,
                "location": {"name": "Berlin, Germany"},
                "departments": [{"id": 7, "name": "Engineering"}],
                "content": "&lt;p&gt;" + TEXT + "&lt;/p&gt;",
                "updated_at": "2026-02-03T10:00:00Z",
            },
            departments=[{"id": 7, "name": "Engineering"}],
        ),
        _ats(
            "lever",
            "example",
            "0f6c1d3e-aaaa-bbbb-cccc-000000000001",
            "Backend Engineer",
            lever,
            {
                "id": "0f6c1d3e-aaaa-bbbb-cccc-000000000001",
                "text": "Backend Engineer",
                "hostedUrl": lever,
                "applyUrl": lever + "/apply",
                "categories": {"location": "Remote", "team": "Engineering"},
                "descriptionPlain": TEXT,
                "lists": [{"text": "Requirements", "content": "<li>Python</li>"}],
                "workplaceType": "remote",
                "createdAt": 1770112800000,
            },
            location="Remote",
            workplace_type="remote",
        ),
        _ats(
            "ashby",
            "example",
            "5b1c",
            "Site Reliability Engineer",
            "https://jobs.ashbyhq.com/example/5b1c",
            {
                "id": "5b1c",
                "title": "Site Reliability Engineer",
                "jobUrl": "https://jobs.ashbyhq.com/example/5b1c",
                "applyUrl": "https://jobs.ashbyhq.com/example/5b1c/application",
                "descriptionPlain": TEXT,
                "isListed": True,
                "isRemote": True,
                "compensation": {"summary": "Synthetic range"},
            },
            department="Engineering",
        ),
        _ats(
            "recruitee",
            "example",
            61,
            "Product Designer",
            "https://example.recruitee.com/o/product-designer",
            {
                "id": 61,
                "title": "Product Designer",
                "careers_url": "https://example.recruitee.com/o/product-designer",
                "careers_apply_url": "https://example.recruitee.com/o/product-designer/c/new",
                "city": "Milan",
                "country": "Italy",
                "description": TEXT,
                "requirements": "Synthetic requirements.",
                "employment_type_code": "fulltime",
            },
            source="recruitee",
        ),
        _ats(
            "personio",
            "example",
            "7001",
            "Finance Analyst",
            "https://example.jobs.personio.de/job/7001",
            {
                "id": "7001",
                "name": "Finance Analyst",
                "office": "Munich",
                "schedule": "full-time",
                "createdAt": "2026-02-03T08:00:00+00:00",
                "jobDescriptions": None,
            },
            source="personio",
        ),
        _ats(
            "workable",
            "example",
            "A1B2C3",
            "Support Engineer",
            "https://apply.workable.com/j/A1B2C3",
            {
                "shortcode": "A1B2C3",
                "title": "Support Engineer",
                "url": "https://apply.workable.com/j/A1B2C3",
                "shortlink": "https://apply.workable.com/j/A1B2C3",
                "application_url": "https://apply.workable.com/j/A1B2C3/apply",
                "telecommuting": False,
                "description": TEXT,
                "published_on": "2026-02-03",
            },
            source="workable",
        ),
        _ats(
            "breezy",
            "example",
            "bz-81",
            "Office Manager",
            "https://example.breezy.hr/p/bz-81-office-manager",
            {
                "id": "bz-81",
                "name": "Office Manager",
                "url": "https://example.breezy.hr/p/bz-81-office-manager",
                "location": {"name": "Lisbon", "is_remote": False},
                "type": {"name": "Full-Time"},
            },
            source="breezy",
            description_available=False,
        ),
        _ats(
            "bamboohr",
            "example",
            91,
            "People Partner",
            "https://example.bamboohr.com/careers/91",
            {
                "id": 91,
                "jobOpeningName": "People Partner",
                "jobOpeningShareUrl": "https://example.bamboohr.com/careers/91",
                "location": {"city": "Dublin"},
                "description": TEXT,
                "isRemote": None,
            },
            source="bamboohr",
        ),
        _ats(
            "rippling",
            "example",
            "9d2e",
            "Security Engineer",
            "https://ats.rippling.com/example/jobs/9d2e",
            {
                "uuid": "9d2e",
                "name": "Security Engineer",
                "url": "https://ats.rippling.com/example/jobs/9d2e",
                "workLocation": {"label": "Amsterdam"},
                "description": {"company": "Synthetic.", "role": TEXT},
            },
            source="rippling",
        ),
        _ats(
            "smartrecruiters",
            "example",
            "744000",
            "Sales Engineer",
            "https://jobs.smartrecruiters.com/example/744000",
            {
                "id": "744000",
                "name": "Sales Engineer",
                "ref": "https://api.smartrecruiters.com/v1/companies/example/postings/744000",
                "applyUrl": "https://jobs.smartrecruiters.com/example/744000?oga=true",
                "location": {"city": "Paris", "country": "fr"},
                "jobAd": {"sections": {"jobDescription": {"text": TEXT}}},
            },
            source="smartrecruiters",
        ),
        _ats(
            "workday",
            "example.wd3.myworkdayjobs.com/Careers",
            "/job/Madrid/Analyst_R-100",
            "Analyst R-100",
            "https://example.wd3.myworkdayjobs.com/Careers/job/Madrid/Analyst_R-100",
            {
                "listing": {"title": "Analyst", "externalPath": "/job/Madrid/Analyst_R-100"},
                "detail": {
                    "externalUrl": "https://example.wd3.myworkdayjobs.com/Careers/job/Madrid/Analyst_R-100",
                    "jobDescription": TEXT,
                    "timeType": "Full time",
                },
            },
            source="workday",
        ),
        _ats(
            "oracle",
            "example.fa.oraclecloud.com/CX_1",
            "300000123",
            "Consultant",
            "https://example.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/300000123",
            {
                "Id": "300000123",
                "Title": "Consultant",
                "PrimaryLocation": "Vienna",
                "ExternalDescriptionStr": TEXT,
            },
            source="oracle",
        ),
        _ats(
            "joincom",
            "example",
            8123,
            "Marketing Manager",
            "https://join.com/companies/example/8123-marketing-manager",
            {
                "id": 8123,
                "idParam": "8123-marketing-manager",
                "title": "Marketing Manager",
                "city": {"cityName": "Hamburg", "countryName": "Germany"},
                "intro": TEXT,
            },
            source="joincom",
        ),
        # A feed entry.
        _item(
            "rss:" + "a" * 64,
            "Research Engineer",
            "Example Feed",
            "",
            "https://example.org/feed/research-engineer",
            {"feed": "https://example.org/jobs.rss", "external_id": "guid-1"},
            {"guid": "guid-1", "description": "<p>" + TEXT + "</p>"},
        ),
        # Manual and API input: no source key, no provider row, or an odd provider row.
        {
            "url": "https://example.org/careers/manual-role?utm_source=synthetic",
            "title": "Manual Role",
            "company": "Example Manual",
            "posting": TEXT,
        },
        {"title": "Pasted Role", "company": "Example Pasted", "posting": TEXT},
        {
            "url": "https://example.org/careers/api-role",
            "title": "API Role",
            "company": "Example API",
            "posting": TEXT,
            "source_key": "custom:api-role",
            "raw": {"job_url_direct": "https://example.org/apply/api-role", "note": "x" * 2000},
        },
        {
            "url": "https://example.org/careers/odd-role",
            "title": "Odd Role",
            "company": "Example Odd",
            "posting": TEXT,
            "source_key": "custom:odd-role",
            "raw": {"job_url_direct": {"href": "https://example.org/apply/odd"}, "n": 1},
        },
    ]


def released_payload(item):
    """The stored observation payload of releases up to 0.17, as plain data."""
    value = JobInput.model_validate(item)
    data = value.model_dump()
    url = normalize_url(value.url)
    data.update(
        title=value.title.strip() or "Untitled opportunity",
        company=value.company.strip() or "Unknown company",
        url=url,
    )
    return data
