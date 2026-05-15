from app.services.scrapers.base import BaseJobAdapter, JobItem
from app.services.scrapers.registry import ADAPTER_REGISTRY, get_adapter_for_domain, get_adapter_for_source, get_adapter_for_url


__all__ = [
    "ADAPTER_REGISTRY",
    "BaseJobAdapter",
    "JobItem",
    "get_adapter_for_domain",
    "get_adapter_for_source",
    "get_adapter_for_url",
]
