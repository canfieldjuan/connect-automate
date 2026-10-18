"""python -m tools.pack_kit: repository-only authoring CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import core
from .files import Publication, read_input


class Parser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        self._value_options = set()
        kwargs["allow_abbrev"] = False
        super().__init__(*args, **kwargs)

    def add_argument(self, *args, **kwargs):
        action = super().add_argument(*args, **kwargs)
        if action.option_strings and action.nargs is None:
            self._value_options.update(action.option_strings)
        return action

    def parse_known_args(self, args=None, namespace=None):
        # Every declared single-value option owns its next token, even "--help".
        # Derive arity from add_argument rather than maintaining another option list.
        tokens = list(sys.argv[1:] if args is None else args)
        normalized = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token == "--":
                normalized.extend(tokens[index:])
                break
            if token in self._value_options and index + 1 < len(tokens):
                normalized.append(f"{token}={tokens[index + 1]}")
                index += 2
            else:
                normalized.append(token)
                index += 1
        return super().parse_known_args(normalized, namespace)

    def error(self, message):
        # argparse messages can echo input values. Keep diagnostics entirely structural.
        raise core.KitError(2, "usage:")


def main(argv=None) -> int:
    publication = None
    try:
        parser = Parser(prog="pack-kit")
        commands = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
        new = commands.add_parser("new")
        new.add_argument("--archetype", required=True)
        new.add_argument("--pack-id", required=True)
        new.add_argument("--name", required=True)
        new.add_argument("--pack-version", type=int, default=1)
        new.add_argument("--out", required=True, type=Path)
        for command in ["build", "check", "sign"]:
            child = commands.add_parser(command)
            child.add_argument("input", type=Path)
            if command != "check":
                child.add_argument("--out", required=True, type=Path)
            if command != "build":
                child.add_argument("--fake-apps", required=True, type=Path)
                child.add_argument("--fake-events", type=Path)
            if command == "sign":
                child.add_argument("--key-id", required=True)
                child.add_argument("--public-key-base64url", required=True)
        args = parser.parse_args(argv)
        if args.command == "new":
            result = core.new_spec(args.archetype, args.pack_id, args.name, args.pack_version)
            inputs = ()
            message = "created spec"
        else:
            limit = core.SPEC_LIMIT if args.command == "build" else core.ARTIFACT_LIMIT
            raw = read_input(args.input, limit)
            inputs = (args.input,)
            if args.command == "build":
                result = core.build(core.parse_spec(raw))
                message = "built unsigned artifact"
            else:
                catalogue = read_input(args.fake_apps, core.SPEC_LIMIT)
                events = (
                    read_input(args.fake_events, core.SPEC_LIMIT)
                    if args.fake_events is not None
                    else None
                )
                if args.command == "check":
                    if events is None:
                        core.check(raw, catalogue)
                    else:
                        core.check(raw, catalogue, events)
                    print("pack-kit: check passed (offline only)")
                    return 0
                signing = {} if events is None else {"event_catalogue": events}
                result = core.sign(
                    raw,
                    catalogue,
                    args.key_id,
                    args.public_key_base64url,
                    sys.stdin.buffer,
                    **signing,
                )
                inputs += (args.fake_apps,)
                if args.fake_events is not None:
                    inputs += (args.fake_events,)
                message = "signed pack"
        # Register ownership before linking and retain it through the final announcement.
        publication = Publication(args.out)
        publication.write(result, inputs=inputs)
        print(f"pack-kit: {message}")
        return 0
    except BaseException as caught:
        failure = caught
        try:
            if publication is not None:
                publication.rollback()
        except OSError:
            failure = core.KitError(7, "I/O error")
        if isinstance(failure, core.KitError):
            code, message = failure.code, failure.message
        elif isinstance(failure, KeyboardInterrupt):
            code, message = 130, "interrupted"
        elif isinstance(failure, OSError):
            code, message = 7, "I/O error"
        elif isinstance(failure, Exception):
            code, message = 1, "internal error"
        else:
            raise
        print(f"pack-kit: {message}", file=sys.stderr)
        return code


if __name__ == "__main__":
    sys.exit(main())
