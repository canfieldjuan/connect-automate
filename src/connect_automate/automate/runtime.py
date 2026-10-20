"""The pack runtime: load a signed pack, then run its workflow end to end.

This is the composition that makes a signed workflow pack runnable on a licensed host. It
verifies the pack's publisher signature and the per-PC grant (:mod:`connect_automate.
automate.pack`), then drives the verified workflow through the record/stage engine and the
action outbox: an operator decision applies the matching definition's record-ledger effects
(the transition) and emits its declared abstract actions (``notify.local`` and friends)
through the adapter registry. No vendor is named; the registry resolves each abstract action
kind to whatever adapter the operator configured, and ``notify.local`` runs with none.

Every entry point is gated by :meth:`AutomateHost.require_license`, and pack loading is gated
twice more: the publisher signature proves the workflow semantics, and the per-PC grant
authorizes this subject to run this pack. Revalidating the grant at every decision (not only
at load) is deferred hardening.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import TYPE_CHECKING

from .actions import ActionOutcome, ActionRunner, AdapterRegistry
from .definition import MAX_NAME_LENGTH, LeadSourceTrigger, ScheduleTrigger, Workflow, WorkflowV2
from .engine import DecisionOutcome, PackVersionError, WorkflowEngine
from .events import (
    EventBindingError,
    EventInputError,
    LeadSourceEvent,
    SourceBinding,
    check_event_time,
    parse_event,
)
from .host import AutomateHost
from .pack import LoadedPack, load_pack, verify_grant
from .store import ACTION_DEDUPE_PREFIX, RecordView, WorkflowStore, _EventVersionConflict

if TYPE_CHECKING:
    from ..lead_intake.admission import SourceAdmission
    from ..lead_intake.handoff import _SourceHandoff


@dataclass(frozen=True)
class DecisionRun:
    """A decision's record outcome plus the action outcomes it dispatched."""

    outcome: DecisionOutcome
    actions: list[ActionOutcome]


@dataclass(frozen=True)
class EventRun:
    matched: bool
    applied: bool
    record: RecordView | None
    event_id: str | None
    actions: list[ActionOutcome]


# A private construction token. PackRuntime can only be built through load(), which performs
# signature and grant verification; a direct construction that skipped it would defeat the
# whole point of the signed-pack boundary.
_VERIFIED = object()


class PackRuntime:
    """Runs a verified workflow pack against the durable store and the action outbox.

    Construct only through :meth:`load`, which verifies the publisher signature and the per-PC
    grant. The constructor rejects any other caller so a runtime cannot exist for a pack that
    was not verified.
    """

    def __init__(
        self,
        *,
        pack: LoadedPack,
        store: WorkflowStore,
        host: AutomateHost,
        registry: AdapterRegistry,
        subject: str = "",
        event_bindings: Mapping[str, SourceBinding] | None = None,
        source_handoffs: Mapping[str, _SourceHandoff] | None = None,
        _token: object = None,
    ):
        if _token is not _VERIFIED:
            raise TypeError(
                "PackRuntime must be created through PackRuntime.load(); direct construction "
                "would bypass pack-signature and grant verification"
            )
        self._pack = pack
        self._host = host
        self._store = store
        self._engine = WorkflowEngine(store=store, host=host)
        self._runner = ActionRunner(store=store, registry=registry, host=host)
        self._subject = subject
        self._event_bindings = MappingProxyType(
            {} if event_bindings is None else dict(event_bindings)
        )
        self._source_handoffs = MappingProxyType(
            {} if source_handoffs is None else dict(source_handoffs)
        )

    @property
    def pack(self) -> LoadedPack:
        # A defensive deep copy: the verified workflow the engine executes is private, so a
        # caller cannot mutate an effect or append an action after load() and have
        # submit_decision run unsigned semantics.
        return LoadedPack(
            pack_id=self._pack.pack_id,
            pack_version=self._pack.pack_version,
            workflow=self._pack.workflow.model_copy(deep=True),
        )

    @property
    def workflow(self) -> Workflow | WorkflowV2:
        # A defensive deep copy, for the same reason as :attr:`pack`.
        return self._pack.workflow.model_copy(deep=True)

    @classmethod
    def load(
        cls,
        pack_bytes: bytes,
        grant_bytes: bytes,
        *,
        store: WorkflowStore,
        host: AutomateHost,
        registry: AdapterRegistry,
        publisher_keys: Mapping[str, bytes],
        grant_keys: Mapping[str, bytes],
        subject: str,
        now: datetime,
        event_bindings: Mapping[str, SourceBinding | Mapping[str, object]] | None = None,
        source_admission: SourceAdmission | None = None,
        source_clock: Callable[[], datetime] | None = None,
    ) -> PackRuntime:
        """Verify a pack and its per-PC grant, then return a runtime for its workflow.

        Gated by the license first: an unlicensed host cannot load a pack at all.
        :func:`load_pack` verifies the publisher signature over the pack bytes against
        ``publisher_keys``; :func:`verify_grant` authorizes this ``subject`` (the licensed
        PC/customer) against the *separate* ``grant_keys``. The two trust stores are kept
        distinct so a pack publisher cannot self-issue a grant and a grant issuer cannot
        sign an executable pack; pass the same mapping for both only when one authority holds
        both roles. A tampered pack, an untrusted key, or a missing/mismatched grant raises
        :class:`PackError` here, before any record is created.

        Optional source_admission/source_clock are paired trusted-host configuration
        for the private lead composition seams. They do not enable public source
        submission or claim workflow acceptance in this increment.
        """
        host.require_license()
        pack = load_pack(pack_bytes, keys=publisher_keys)
        verify_grant(grant_bytes, keys=grant_keys, pack_id=pack.pack_id, subject=subject, now=now)
        bindings, configuration = cls._validate_bindings(pack.workflow, event_bindings)
        handoffs = {}
        if source_admission is not None or source_clock is not None:
            # Keep operational imports out of pure event/receipt import paths.
            from ..lead_intake.handoff import _SourceHandoff

            lead_bindings = {
                name: source
                for name, source in bindings.items()
                if source.source_kind == "lead.source.received"
            }
            if not lead_bindings:
                raise EventBindingError()
            handoffs = {
                name: _SourceHandoff(source, source_admission, source_clock)
                for name, source in lead_bindings.items()
            }
        if isinstance(pack.workflow, WorkflowV2):
            store.register_bindings(subject, pack.pack_id, configuration)
        return cls(
            pack=pack,
            store=store,
            host=host,
            registry=registry,
            subject=subject,
            event_bindings=bindings,
            source_handoffs=handoffs,
            _token=_VERIFIED,
        )

    @staticmethod
    def _validate_bindings(workflow, supplied):
        if not isinstance(workflow, WorkflowV2):
            if supplied is not None:
                raise EventBindingError()
            return {}, {}
        try:
            if not isinstance(supplied, Mapping):
                raise ValueError("missing source bindings")
            triggers = [
                definition.trigger
                for definition in workflow.definitions
                if definition.trigger.source_kind != "operator.decision"
            ]
            names = {trigger.binding for trigger in triggers}
            if set(supplied) != names or any(
                not isinstance(name, str) or not 1 <= len(name) <= MAX_NAME_LENGTH
                for name in supplied
            ):
                raise ValueError("invalid source names")
            bindings = {
                name: SourceBinding.model_validate(
                    value.model_dump() if isinstance(value, SourceBinding) else value
                )
                for name, value in supplied.items()
            }
            configuration = {}
            for name, source in bindings.items():
                matching = [trigger for trigger in triggers if trigger.binding == name]
                if any(trigger.source_kind != source.source_kind for trigger in matching):
                    raise ValueError("wrong source kind")
                policies = {
                    (trigger.anchor, trigger.every_seconds)
                    for trigger in matching
                    if isinstance(trigger, ScheduleTrigger)
                }
                if len(policies) > 1:
                    raise ValueError("ambiguous timer policy")
                policy = (
                    {"anchor": matching[0].anchor, "every_seconds": matching[0].every_seconds}
                    if policies
                    else None
                )
                if isinstance(matching[0], LeadSourceTrigger):
                    policy = {"schema_version": "1.0"}
                configuration[name] = {**source.model_dump(mode="json"), "policy": policy}
            return bindings, configuration
        except (ValueError, TypeError, RecursionError):
            pass
        raise EventBindingError()

    def _lead_source_binding(self, binding: str) -> SourceBinding:
        self._host.require_license()
        if (
            not isinstance(self._pack.workflow, WorkflowV2)
            or not isinstance(binding, str)
            or binding not in self._event_bindings
            or self._event_bindings[binding].source_kind != "lead.source.received"
        ):
            raise EventBindingError()
        return self._event_bindings[binding]

    def _prepare_source(self, *, binding: str, raw_source_bytes: bytes):
        """Private composition only; source custody is NOT workflow acceptance."""
        self._lead_source_binding(binding)
        handoff = self._source_handoffs.get(binding)
        if handoff is None:
            raise EventBindingError()
        return handoff.prepare(raw_source_bytes)

    def _lookup_source_receipt(self, *, binding: str, event_id: str, expected_payload_digest: str):
        """Private historical projection; no admission, source access or dispatch."""
        source = self._lead_source_binding(binding)
        try:
            return self._store.lookup_source_event(
                subject=self._subject,
                pack_id=self._pack.pack_id,
                pack_version=self._pack.pack_version,
                binding=binding,
                source=source,
                event_id=event_id,
                expected_payload_digest=expected_payload_digest,
            )
        except _EventVersionConflict:
            raise PackVersionError("event belongs to another pack revision") from None

    def submit_event(self, *, binding: str, event: bytes, now: datetime) -> EventRun:
        self._host.require_license()
        parsed = parse_event(event)
        if isinstance(parsed, LeadSourceEvent):
            # A receipt-shaped value is not authenticated source custody.
            raise EventInputError()
        if (
            not isinstance(self._pack.workflow, WorkflowV2)
            or not isinstance(binding, str)
            or binding not in self._event_bindings
        ):
            raise EventBindingError()
        source = self._event_bindings[binding]
        if source.source_kind != parsed.source_kind:
            raise EventBindingError()
        check_event_time(parsed, now)
        outcome = self._engine.submit_event(
            self._pack.workflow,
            subject=self._subject,
            pack_id=self._pack.pack_id,
            pack_version=self._pack.pack_version,
            binding=binding,
            source=source,
            event=parsed,
            now=now,
        )
        actions = self._dispatch_event_actions(
            outcome.record, outcome.event_id, outcome.applied, now
        )
        return EventRun(outcome.matched, outcome.applied, outcome.record, outcome.event_id, actions)

    def _dispatch_event_actions(self, record, event_id, applied, now):
        if record is None or event_id is None:
            return []
        prefix = f"{ACTION_DEDUPE_PREFIX}{event_id}:"
        return [
            self._runner.dispatch(view, now=now, safe_replay=not applied)
            for view in self._store.list_actions(record.record_id)
            if view.dedupe_key.startswith(prefix)
        ]

    def create_record(self, *, now: datetime) -> RecordView:
        """Create a record for the pack's workflow at its initial stage.

        The record is bound to this pack's identity, so only this pack's runtime can later
        submit decisions against it, even if another signed pack declares a same-named
        workflow.
        """
        return self._engine.create_record(
            self._pack.workflow,
            now=now,
            pack_id=self._pack.pack_id,
            pack_version=self._pack.pack_version,
        )

    def submit_decision(
        self,
        record_id: str,
        *,
        decision: str,
        operation_key: str,
        request: Mapping[str, object],
        expected_version: int,
        now: datetime,
    ) -> DecisionRun:
        """Apply a decision and dispatch the matched definition's declared actions.

        The engine commits the record-ledger effects (the transition) and admits the matched
        definition's action intents to the outbox in the *same* transaction, so the moment a
        decision applies its declared side effects are durable pending rows. This method then
        dispatches (delivers and settles) those pending rows.

        This is idempotent and crash-recoverable: a replay of the same ``operation_key``
        returns ``applied=False`` and re-admits nothing, and the dispatch here re-drives only
        rows still ``pending`` from an earlier crash mid-dispatch, so each declared action
        runs at most once and is never lost. An action whose kind has no configured adapter
        stays pending and resumable rather than being lost or blocking the others.
        """
        outcome = self._engine.submit_decision(
            self._pack.workflow,
            record_id,
            decision=decision,
            operation_key=operation_key,
            request=request,
            expected_version=expected_version,
            now=now,
            expected_pack_id=self._pack.pack_id,
            expected_pack_version=self._pack.pack_version,
        )
        actions: list[ActionOutcome] = []
        if outcome.matched and outcome.event_id is not None:
            # The decision's action rows were admitted (pending) in the same transaction as
            # its ledger event, keyed by that event id. Dispatch them in admission order;
            # dispatch() delivers a pending row, replays a terminal one, and leaves an
            # unconfigured-adapter row pending for a later resume.
            prefix = f"{ACTION_DEDUPE_PREFIX}{outcome.event_id}:"
            for view in self._store.list_actions(record_id):
                if view.dedupe_key.startswith(prefix):
                    actions.append(
                        self._runner.dispatch(
                            view,
                            now=now,
                            safe_replay=isinstance(self._pack.workflow, WorkflowV2)
                            and not outcome.applied,
                        )
                    )
        return DecisionRun(outcome=outcome, actions=actions)
