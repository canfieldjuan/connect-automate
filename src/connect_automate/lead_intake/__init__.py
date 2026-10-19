"""Lead Intake contracts. Parsed source data is not authenticated admission."""

from .admission import (
    SourceAdmission,
    SourceAdmissionConflict,
    SourceAdmissionResult,
    SourceReceipt,
)
from .auth import (
    AuthenticatedSource,
    SourceAuthenticationError,
    SourceKeyGrant,
    SourceRetentionPolicy,
    SourceTrustSnapshot,
    authenticate_source,
    source_signing_bytes,
)
from .source import (
    SourceInputError,
    UntrustedSource,
    canonical_payload,
    canonical_source,
    parse_untrusted_source,
    payload_digest,
)
from .source_store import (
    SourceStore,
    SourceStoreBusy,
    SourceStoreConflict,
    SourceStoreError,
    SourceStoreInputError,
    SourceStoreUnavailable,
    SourceStoreUncertain,
)

__all__ = [
    "SourceAdmission",
    "SourceAdmissionConflict",
    "SourceAdmissionResult",
    "SourceReceipt",
    "SourceStore",
    "SourceStoreBusy",
    "SourceStoreConflict",
    "SourceStoreError",
    "SourceStoreInputError",
    "SourceStoreUnavailable",
    "SourceStoreUncertain",
    "AuthenticatedSource",
    "SourceAuthenticationError",
    "SourceKeyGrant",
    "SourceRetentionPolicy",
    "SourceTrustSnapshot",
    "authenticate_source",
    "source_signing_bytes",
    "SourceInputError",
    "UntrustedSource",
    "canonical_payload",
    "canonical_source",
    "parse_untrusted_source",
    "payload_digest",
]
