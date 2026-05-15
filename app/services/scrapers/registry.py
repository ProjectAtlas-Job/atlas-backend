from __future__ import annotations

from urllib.parse import urlparse

from app.services.scrapers.adapters.cutshort import CutshortAdapter
from app.services.scrapers.adapters.generic import GenericAdapter
from app.services.scrapers.adapters.hackernews import HackerNewsAdapter
from app.services.scrapers.adapters.hirist import HiristAdapter
from app.services.scrapers.adapters.iimjobs import IIMJobsAdapter
from app.services.scrapers.adapters.internshala import InternshalaAdapter
from app.services.scrapers.adapters.naukri import NaukriAdapter
from app.services.scrapers.adapters.unstop import UnstopAdapter
from app.services.scrapers.adapters.wellfound import WellfoundAdapter
from app.services.scrapers.base import BaseJobAdapter

ADAPTER_REGISTRY: dict[str, type[BaseJobAdapter] | None] = {
    "naukri.com": NaukriAdapter,
    "www.naukri.com": NaukriAdapter,
    "internshala.com": InternshalaAdapter,
    "www.internshala.com": InternshalaAdapter,
    "wellfound.com": WellfoundAdapter,
    "www.wellfound.com": WellfoundAdapter,
    "hn.algolia.com": HackerNewsAdapter,
    "news.ycombinator.com": HackerNewsAdapter,
    "cutshort.io": CutshortAdapter,
    "www.cutshort.io": CutshortAdapter,
    "unstop.com": UnstopAdapter,
    "www.unstop.com": UnstopAdapter,
    "iimjobs.com": IIMJobsAdapter,
    "www.iimjobs.com": IIMJobsAdapter,
    "hirist.com": HiristAdapter,
    "www.hirist.com": HiristAdapter,
    "hirist.tech": HiristAdapter,
    "www.hirist.tech": HiristAdapter,
    "indeed.co.in": None,
    "www.indeed.co.in": None,
    "glassdoor.co.in": None,
    "www.glassdoor.co.in": None,
    "linkedin.com": None,
    "www.linkedin.com": None,
}

SOURCE_TYPE_REGISTRY: dict[str, type[BaseJobAdapter]] = {
    "naukri": NaukriAdapter,
    "internshala": InternshalaAdapter,
    "wellfound": WellfoundAdapter,
    "hackernews": HackerNewsAdapter,
    "cutshort": CutshortAdapter,
    "unstop": UnstopAdapter,
    "iimjobs": IIMJobsAdapter,
    "hirist": HiristAdapter,
    "scraper": GenericAdapter,
}


def get_adapter_for_domain(domain: str) -> BaseJobAdapter | None:
    adapter_class = ADAPTER_REGISTRY.get(domain.lower())
    if adapter_class is None:
        return None
    return adapter_class()


def get_adapter_for_source(source_type: str) -> BaseJobAdapter:
    adapter_class = SOURCE_TYPE_REGISTRY.get(source_type.lower(), GenericAdapter)
    return adapter_class()


def get_adapter_for_url(url: str) -> BaseJobAdapter:
    domain = urlparse(url).netloc.lower()
    return get_adapter_for_domain(domain) or GenericAdapter()
