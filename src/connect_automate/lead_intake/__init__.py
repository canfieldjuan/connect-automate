"""Lead Intake exports; pure contracts must not import operational owners eagerly.

Resolve each public name from its owning module only when requested. This keeps
receipt/source imports independent of admission and future workflow handoffs.
Parsed source data is not authenticated admission.
"""

from importlib import import_module as _import_module

_EXPORT_MODULES = {
    "SourceAdmission": ".admission",
    "SourceAdmissionConflict": ".admission",
    "SourceAdmissionResult": ".admission",
    "SourceReceipt": ".admission",
    "SourceStore": ".source_store",
    "SourceStoreBusy": ".source_store",
    "SourceStoreConflict": ".source_store",
    "SourceStoreError": ".source_store",
    "SourceStoreInputError": ".source_store",
    "SourceStoreUnavailable": ".source_store",
    "SourceStoreUncertain": ".source_store",
    "AuthenticatedSource": ".auth",
    "SourceAuthenticationError": ".auth",
    "SourceKeyGrant": ".auth",
    "SourceRetentionPolicy": ".auth",
    "SourceTrustSnapshot": ".auth",
    "authenticate_source": ".auth",
    "source_signing_bytes": ".auth",
    "SourceInputError": ".source",
    "UntrustedSource": ".source",
    "canonical_payload": ".source",
    "canonical_source": ".source",
    "parse_untrusted_source": ".source",
    "payload_digest": ".source",
}

__all__ = list(_EXPORT_MODULES)


def __getattr__(name: str) -> object:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(_import_module(module_name, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
