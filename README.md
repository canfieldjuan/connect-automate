# Connect Automate

The vendor-neutral, licensed-consumer host core for Local Connect automations.

This package is the reusable substrate a downloadable, per-PC automation product
is built on. It holds:

- a Connect v2 client (`connect_automate.connect`) with same-PC loopback
  discovery, a caller-minted stable `job_id` for idempotent submission, and the
  verified terminal-transition table;
- the entitlement gate (`connect_automate.entitlement`), an Ed25519 signed-license
  verifier checked against a compiled public keyring;
- a file-locking substrate (`connect_automate.locking`);
- the Automate host (`connect_automate.automate`): the strict workflow definition
  model, the durable record and lifecycle ledger, the stage engine, the effect
  executor, the action outbox, the adapter registry, and the signed-pack loader;
- the single-shot `connect.invoke` capability invoker
  (`connect_automate.automate_connect`).

## Vendor neutrality

The core names only abstract action kinds (`notify.local`, `notify`,
`mail.send`, `calendar.write`, `connect.invoke`) and opaque capability
identifiers. It never imports a vendor integration, a provider backend, or any
host application. That boundary is enforced by
`tests/test_connect_automate_boundary.py`, which fails the build if any module
here imports a host application package or a concrete provider SDK. Bundled
adapters (mail, notify, calendar) register into the adapter registry at a host
composition layer that lives in the consuming application, not here.

## Development

This project uses [uv](https://docs.astral.sh/uv/).

```
uv sync --all-groups
uv run ruff check .
uv run pytest
```

The Windows-only Connect placement tests (`tests/test_windows_connect.py`) run
on Windows and require `CONNECT_CONTRACTS_DIR` to point at a checkout of the
`connect-contracts` fixtures; they skip on other platforms.
