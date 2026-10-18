"""python -m tools.pack_kit: repository-only authoring CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import core
from .files import publish, read_input


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse messages can echo input values. Keep diagnostics entirely structural.
        raise core.KitError(2, "usage:")


def main(argv=None) -> int:
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
                if args.command == "check":
                    core.check(raw, catalogue)
                    print("pack-kit: check passed (offline only)")
                    return 0
                result = core.sign(
                    raw, catalogue, args.key_id, args.public_key_base64url, sys.stdin.buffer
                )
                inputs += (args.fake_apps,)
                message = "signed pack"
        publish(args.out, result, inputs=inputs)
        print(f"pack-kit: {message}")
        return 0
    except core.KitError as exc:
        print(f"pack-kit: {exc.message}", file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        print("pack-kit: interrupted", file=sys.stderr)
        return 130
    except Exception:
        print("pack-kit: internal error", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
