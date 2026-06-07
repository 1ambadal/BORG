import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from services.db_service import add_scraped_jobs, get_setting, set_setting

logger = logging.getLogger(__name__)


# ── Config ────────────────────────────────────────────────────────────────────
def get_scraper_config() -> dict:
    """Gets the active scraper configuration from the database, falling back to defaults."""
    default_config = {
        "keywords": ["python developer", "software engineer", "backend developer"],
        "locations": ["gurgaon", "noida", "bangalore"],
        "naukri_max_pages": 3,
        "search_pages": 2,
        "delay_between_reqs": 3.0,
        "mandatory_skill": "python",
        "nice_to_have": [
            "postgresql",
            "psql",
            "postgres",
            "docker",
            "fastapi",
            "django",
            "flask",
            "aws",
        ],
        "exp_min": 3,
        "exp_max": 6,
    }
    return get_setting("scraper_config", default_config)


def save_scraper_config(config: dict) -> None:
    """Saves the scraper configuration to the database."""
    set_setting("scraper_config", config)


# ── Scraper Global State ──────────────────────────────────────────────────────
@dataclass
class ScraperState:
    is_running: bool = False
    status_message: str = "Idle"
    last_run_time: Optional[str] = None
    scraped_count: int = 0          # new jobs actually saved to DB
    total_found: int = 0            # raw jobs collected before dedup/filter
    progress_pct: float = 0.0       # 0–100, updated each page
    error_message: Optional[str] = None


state = ScraperState()


def get_state_dict() -> dict:
    """Single source of truth for scraper state — used by both polling and SSE routes."""
    return {
        "is_running": state.is_running,
        "status_message": state.status_message,
        "last_run_time": state.last_run_time,
        "scraped_count": state.scraped_count,
        "total_found": state.total_found,
        "progress_pct": round(state.progress_pct, 1),
        "error_message": state.error_message,
    }

# ── Helpers ───────────────────────────────────────────────────────────────────


def is_fresh(date_str: str) -> bool:
    if not date_str:
        return True
    ds = date_str.lower().strip()
    if any(k in ds for k in ["today", "yesterday", "just posted", "recent", "hour"]):
        return True
    m = re.search(r"(\d+)\s*(day|week|month)", ds)
    if m:
        num, unit = int(m.group(1)), m.group(2)
        if "month" in unit:
            return False
        if "week" in unit:
            return num <= 1
        if "day" in unit:
            return num <= 7
    if re.search(r"30\+|15\+|20\+", ds):
        return False
    return True


def skill_filter(job: dict) -> dict | None:
    cfg = get_scraper_config()
    haystack = job["title"].lower()
    mandatory = cfg.get("mandatory_skill", "python").lower()
    if "linkedin.com" in job.get("url", "") and mandatory not in haystack:
        return None
    nice_to_have = cfg.get("nice_to_have", [])
    score = sum(1 for s in nice_to_have if s.lower() in haystack)
    return {**job, "_skill_score": score}


def is_blocked(html: str) -> bool:
    h = html.lower()
    return (
        ("captcha" in h and "algo" not in h)
        or "unusual traffic" in h
        or len(html) < 500
    )


# ── Naukri parser ─────────────────────────────────────────────────────────────


def parse_naukri(html: str, keyword: str, location: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    now = datetime.now().isoformat(timespec="seconds")

    cards = soup.find_all(class_=re.compile(r"jobtuple|srp-jobtuple|job-tuple", re.I))
    if not cards:
        seen, cards = set(), []
        for link in soup.find_all("a", href=re.compile(r"/job-listings-")):
            parent = (
                link.find_parent("article")
                or link.find_parent(
                    "div", class_=re.compile(r"tuple|card|listing|container", re.I)
                )
                or link.find_parent("div")
            )
            if parent and id(parent) not in seen:
                seen.add(id(parent))
                cards.append(parent)

    if not cards:
        return []

    jobs, seen_urls = [], set()
    for card in cards:
        a = card.find("a", href=re.compile(r"/job-listings-"))
        if not a:
            continue
        url = a.get("href", "").strip()
        if not url.startswith("http"):
            url = f"https://www.naukri.com{url}"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        comp_tag = card.find(class_=re.compile(r"comp-name|company-name|comp\b", re.I))
        company = comp_tag.get_text(" ", strip=True) if comp_tag else "N/A"
        company = (
            re.sub(
                r"\s*\d+(\.\d+)?\s*(reviews?|star\s*rating|ratings?)?.*$",
                "",
                company,
                flags=re.I,
            ).strip()
            or "N/A"
        )

        loc_tag = card.find(class_=re.compile(r"\bloc\b|location", re.I))

        date_str = "Unknown"
        for cls in [r"postdate", r"date", r"posted", r"time"]:
            tag = card.find(class_=re.compile(cls, re.I))
            if tag and len(tag.get_text(strip=True)) < 60:
                date_str = tag.get_text(" ", strip=True)
                break
        if date_str == "Unknown":
            for tag in card.find_all(["span", "div", "p"]):
                t = tag.get_text(" ", strip=True)
                if len(t) < 60 and re.search(
                    r"\d+\s*(day|week|month|hour)s?\s*ago|just\s*posted|today|yesterday",
                    t,
                    re.I,
                ):
                    date_str = t
                    break
        if date_str == "Unknown":
            m = re.search(
                r"(\d+\+?\s*(?:day|week|month|hour)s?\s*ago|just\s*posted|today|yesterday)",
                card.get_text(" ", strip=True),
                re.I,
            )
            if m:
                date_str = m.group(1).strip()

        if not is_fresh(date_str):
            continue

        jobs.append(
            {
                "title": a.get_text(" ", strip=True),
                "company": company,
                "location": loc_tag.get_text(" ", strip=True) if loc_tag else location,
                "date_posted": date_str,
                "url": url,
            }
        )
    return jobs


# ── LinkedIn / Yahoo parser ───────────────────────────────────────────────────

_LI_JOB = re.compile(r"linkedin\.com/(jobs|job-apply|comm/jobs)", re.I)
_LI_POST = re.compile(r"linkedin\.com/(posts|pulse|feed/update)", re.I)


def clean_yahoo_linkedin_title(title: str) -> str:
    """Cleans up Yahoo search breadcrumbs, usernames, and URLs from parsed LinkedIn post titles."""
    # 1. Split by typical Yahoo breadcrumb delimiters
    parts = re.split(r"[›>»]", title)
    if len(parts) > 1:
        title = parts[-1].strip()

    # 2. Remove any remaining URLs
    title = re.sub(r"https?://[^\s]+", "", title)

    # 3. Strip leading username/handle (e.g. shweta-singh-79913620a)
    title = re.sub(r"^[a-z0-9\-]{3,40}\b", "", title).strip()

    # 4. Remove leading "LinkedIn", "Post", "Feed" prefixes if any remains
    title = re.sub(r"^(?:LinkedIn|Post|Feed)\b", "", title, flags=re.I).strip()

    # 5. Clean up any weird starting characters or whitespace
    title = title.strip(" :|-›>»")

    return title or "LinkedIn Post"


def _company_from_title(title: str, snippet: str) -> str:
    m = re.match(r"^(.+?)\s+on\s+LinkedIn", title, re.I)
    if m:
        return m.group(1).strip()
    m = re.match(r"^(.+?)\s*[|:]\s*LinkedIn", title, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(
        r"^([A-Z][^.!?\n]{3,50}?)\s+(?:is\s+hiring|we(?:'re|\s+are)\s+hiring)",
        snippet,
        re.I,
    )
    if m:
        return m.group(1).strip()
    return "N/A"


def parse_linkedin_from_yahoo(html: str, keyword: str, location: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    now = datetime.now().isoformat(timespec="seconds")
    posts, seen = [], set()

    blocks = soup.find_all("div", class_=re.compile(r"^algo", re.I))
    if not blocks:
        blocks = soup.find_all("li", class_=re.compile(r"first|last|result", re.I))

    for block in blocks:
        heading = block.find(["h3", "h2"])
        a_tag = heading.find("a", href=True) if heading else None
        if not a_tag:
            continue
        url = a_tag["href"].strip()
        m = re.search(r"[?&](?:u|url)=(https?://[^&]+)", url)
        if m:
            url = m.group(1)
        if not _LI_POST.search(url) or _LI_JOB.search(url) or url in seen:
            continue
        seen.add(url)
        title = clean_yahoo_linkedin_title(a_tag.get_text(" ", strip=True))
        snippet_tag = block.find("p") or block.find(
            "span", class_=re.compile(r"fc-2nd|lh", re.I)
        )
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""
        posts.append(
            {
                "title": title,
                "company": _company_from_title(title, snippet),
                "location": location,
                "date_posted": "Recent",
                "url": url,
            }
        )

    if not posts:
        for a in soup.find_all("a", href=True):
            url = a["href"].strip()
            if not _LI_POST.search(url) or _LI_JOB.search(url) or url in seen:
                continue
            seen.add(url)
            title = clean_yahoo_linkedin_title(a.get_text(" ", strip=True))
            parent = a.find_parent("li") or a.find_parent("div")
            posts.append(
                {
                    "title": title,
                    "company": _company_from_title(
                        title, parent.get_text(" ", strip=True) if parent else ""
                    ),
                    "location": location,
                    "date_posted": "Recent",
                    "url": url,
                }
            )

    return posts


# ── Scrape Runner ─────────────────────────────────────────────────────────────


async def run_scraper_task(
    keywords: Optional[List[str]] = None, locations: Optional[List[str]] = None
):
    """
    Background job scraper run task. Saves scraped jobs directly into SQLite database
    and tracks running state.
    """
    global state
    if state.is_running:
        logger.warning("Scraper is already running.")
        return

    state.is_running = True
    state.error_message = None
    state.scraped_count = 0
    state.total_found = 0
    state.progress_pct = 0.0
    state.status_message = "Initializing crawler..."

    # Load dynamic config
    cfg = get_scraper_config()
    keywords = keywords or cfg.get("keywords", [])
    locations = locations or cfg.get("locations", [])

    naukri_max_pages = cfg.get("naukri_max_pages", 3)
    search_pages = cfg.get("search_pages", 2)
    delay_between_reqs = cfg.get("delay_between_reqs", 3.0)

    mandatory_skill = cfg.get("mandatory_skill", "python")
    nice_to_have = cfg.get("nice_to_have", [])
    exp_min = cfg.get("exp_min", 3)
    exp_max = cfg.get("exp_max", 6)

    # Total pages across both sources — used for progress tracking
    _total_pages = (
        len(keywords) * len(locations) * naukri_max_pages
        + len(keywords) * len(locations) * search_pages
    )
    _pages_done = 0

    all_jobs = []

    try:
        naukri_browser = BrowserConfig(
            headless=True,
            java_script_enabled=True,
            extra_args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
            headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        naukri_cfg = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=30_000,
            magic=True,
            wait_for="css:a[href*='/job-listings-']",
            delay_before_return_html=2.5,
        )

        yahoo_browser = BrowserConfig(
            headless=True,
            java_script_enabled=True,
            enable_stealth=True,
            extra_args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
            headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        yahoo_cfg = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=30_000,
            simulate_user=True,
            override_navigator=True,
            magic=True,
            wait_for="css:#web",
            delay_before_return_html=4.0,
            mean_delay=2.0,
            max_range=2.0,
        )

        # 1. Naukri Scrape
        state.status_message = "Starting Naukri scraping..."
        async with AsyncWebCrawler(config=naukri_browser) as crawler:
            for loc_idx, location in enumerate(locations):
                loc_slug = location.lower().replace(" ", "-")
                for kw_idx, keyword in enumerate(keywords):
                    kw_slug = keyword.lower().replace(" ", "-")
                    params = f"keyskill={mandatory_skill}"
                    for s in nice_to_have:
                        params += f"&keyskill={s.replace(' ', '%20')}"
                    params += f"&experience={exp_min}&experienceMax={exp_max}"

                    for page in range(1, naukri_max_pages + 1):
                        state.status_message = f"Naukri: Crawling {keyword} in {location} (Page {page}/{naukri_max_pages})"
                        suffix = f"-{page}" if page > 1 else ""
                        url = f"https://www.naukri.com/{kw_slug}-jobs-in-{loc_slug}{suffix}?{params}"
                        try:
                            res = await crawler.arun(url=url, config=naukri_cfg)
                            if res.success:
                                jobs = parse_naukri(res.html, keyword, location)
                                all_jobs.extend(jobs)
                                state.total_found = len(all_jobs)
                                if not jobs:
                                    break
                            else:
                                break
                        except Exception:
                            break
                        _pages_done += 1
                        state.progress_pct = (_pages_done / _total_pages * 100) if _total_pages else 0
                        await asyncio.sleep(delay_between_reqs)

        # 2. Yahoo/LinkedIn Scrape
        state.status_message = "Starting LinkedIn/Yahoo scraping..."
        async with AsyncWebCrawler(config=yahoo_browser) as crawler:
            for loc_idx, location in enumerate(locations):
                for kw_idx, keyword in enumerate(keywords):
                    for page in range(search_pages):
                        state.status_message = f"LinkedIn/Yahoo: {keyword} in {location} (Page {page+1}/{search_pages})"
                        first = page * 10 + 1
                        q = f'site:linkedin.com/posts/ "hiring" "{keyword}" "{location}"'
                        encoded = q.replace('"', "%22").replace(" ", "+")
                        url = f"https://search.yahoo.com/search?p={encoded}&b={first}&pz=10"
                        try:
                            res = await crawler.arun(url=url, config=yahoo_cfg)
                            html = res.html or ""
                            if not is_blocked(html):
                                posts = parse_linkedin_from_yahoo(
                                    html, keyword, location
                                )
                                all_jobs.extend(posts)
                                state.total_found = len(all_jobs)
                        except Exception:
                            pass
                        _pages_done += 1
                        state.progress_pct = (_pages_done / _total_pages * 100) if _total_pages else 0
                        await asyncio.sleep(delay_between_reqs)

        # 3. Filtering & Scoring
        state.status_message = "Filtering and calculating matching scores..."
        filtered_with_scores = [
            r for j in all_jobs if (r := skill_filter(j)) is not None
        ]
        filtered_with_scores.sort(key=lambda j: j["_skill_score"], reverse=True)

        # Strictly keep only standard fields saved in data
        filtered = []
        for j in filtered_with_scores:
            filtered.append(
                {
                    "title": j.get("title", "N/A"),
                    "company": j.get("company", "N/A"),
                    "location": j.get("location", "N/A"),
                    "date_posted": j.get("date_posted", "Recent"),
                    "url": j.get("url"),
                }
            )

        # 4. Save to Database
        state.status_message = "Saving jobs to database..."
        new_jobs_count = add_scraped_jobs(filtered)

        # Update State
        state.is_running = False
        state.scraped_count = new_jobs_count
        state.total_found = len(filtered)
        state.progress_pct = 100.0
        state.last_run_time = datetime.now().isoformat()
        state.status_message = f"Scraping completed! Found {len(filtered)} total, saved {new_jobs_count} new jobs."

    except Exception as e:
        logger.error(f"Scraper task encountered an exception: {e}", exc_info=True)
        state.is_running = False
        state.status_message = "Failed with error"
        state.error_message = str(e)


def trigger_job_scraper(
    keywords: Optional[List[str]] = None, locations: Optional[List[str]] = None
) -> bool:
    """
    Triggers the job scraper in a background async task.
    Returns True if started, False if already running.
    """
    if state.is_running:
        return False

    # Start background task
    asyncio.create_task(run_scraper_task(keywords, locations))
    return True
