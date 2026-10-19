"""Lead Intake contracts. Parsed source data is not authenticated admission."""

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

__all__ = [
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
