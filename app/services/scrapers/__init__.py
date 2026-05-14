from app.services.scrapers.adapters.generic import GenericAdapter
from app.services.scrapers.adapters.hackernews import HackerNewsAdapter
from app.services.scrapers.adapters.internshala import InternshalaAdapter
from app.services.scrapers.adapters.naukri import NaukriAdapter
from app.services.scrapers.adapters.wellfound import WellfoundAdapter
from app.services.scrapers.base import BaseJobAdapter, JobItem
from app.services.scrapers.utils import get_domain

ADAPTER_REGISTRY: dict[str, BaseJobAdapter] = {}

_REGISTERED_ADAPTERS = [
    NaukriAdapter(),
    InternshalaAdapter(),
    WellfoundAdapter(),
    HackerNewsAdapter(),
]

for adapter in _REGISTERED_ADAPTERS:
    for domain in adapter.domains:
        ADAPTER_REGISTRY[domain] = adapter

GENERIC_ADAPTER = GenericAdapter()
SOURCE_TYPE_REGISTRY: dict[str, BaseJobAdapter] = {adapter.source_name: adapter for adapter in _REGISTERED_ADAPTERS}
SOURCE_TYPE_REGISTRY[GENERIC_ADAPTER.source_name] = GENERIC_ADAPTER


def get_adapter_for_domain(domain: str) -> BaseJobAdapter | None:
    return ADAPTER_REGISTRY.get(domain.lower())


def get_adapter_for_source(source_type: str) -> BaseJobAdapter:
    return SOURCE_TYPE_REGISTRY.get(source_type.lower(), GENERIC_ADAPTER)


def get_adapter_for_url(url: str) -> BaseJobAdapter:
    return get_adapter_for_domain(get_domain(url)) or GENERIC_ADAPTER


__all__ = [
    "ADAPTER_REGISTRY",
    "BaseJobAdapter",
    "GENERIC_ADAPTER",
    "JobItem",
    "get_adapter_for_domain",
    "get_adapter_for_source",
    "get_adapter_for_url",
]
