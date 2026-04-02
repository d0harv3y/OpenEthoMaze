"""Legacy source adapters for normalized offline work discovery."""

from ..work_items import SourceWorkItem
from .legacy_ehram import discover_legacy_ehram_work_items
from .legacy_vast import discover_legacy_vast_work_items, manifest_to_work_item

__all__ = [
    "SourceWorkItem",
    "discover_legacy_ehram_work_items",
    "discover_legacy_vast_work_items",
    "manifest_to_work_item",
]
