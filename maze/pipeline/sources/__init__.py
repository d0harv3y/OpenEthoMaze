"""Legacy source adapters for normalized offline work discovery."""

from ..work_items import SourceWorkItem
from .legacy_ehram import discover_legacy_ehram_work_items
from .legacy_ehram_import import (
    LegacyRamImportResult,
    bootstrap_legacy_ram_database,
    discover_and_import_legacy_ram,
    import_legacy_ram_work_items,
    legacy_ram_work_item_to_trial_key,
)
from .legacy_vast import discover_legacy_vast_work_items, manifest_to_work_item

__all__ = [
    "LegacyRamImportResult",
    "SourceWorkItem",
    "bootstrap_legacy_ram_database",
    "discover_and_import_legacy_ram",
    "discover_legacy_ehram_work_items",
    "discover_legacy_vast_work_items",
    "import_legacy_ram_work_items",
    "legacy_ram_work_item_to_trial_key",
    "manifest_to_work_item",
]
