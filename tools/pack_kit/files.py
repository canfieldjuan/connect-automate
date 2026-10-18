"""Bounded regular inputs and atomic create-if-absent output publication."""

from __future__ import annotations

import os
import stat
import tempfile
from contextlib import suppress
from pathlib import Path

from .core import KitError


def read_input(path: Path, limit: int) -> bytes:
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise OSError("not a regular file")
            raw = stream.read(limit + 1)
    except OSError as exc:
        raise KitError(7, "I/O error") from exc
    if len(raw) > limit:
        raise KitError(3, "input too large")
    return raw


class Publication:
    """One command's output ownership, valid until its success announcement finishes."""

    def __init__(self, path: Path):
        self.path = path
        self.staged = None

    def rollback(self) -> None:
        # Shared by primitive failures and late command failures. Never unlink a rival inode.
        if self.staged is not None:
            with suppress(FileNotFoundError):
                if os.path.samestat(self.staged, self.path.lstat()):
                    self.path.unlink()

    def write(self, content: bytes, *, inputs: tuple[Path, ...] = ()) -> None:
        temporary = None
        try:
            if os.path.lexists(self.path):
                raise KitError(7, "output exists")
            if any(self.path.resolve() == source.resolve() for source in inputs):
                raise KitError(7, "I/O error")
            fd, name = tempfile.mkstemp(prefix=".pack-kit-", dir=self.path.parent)
            temporary = Path(name)
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
                self.staged = os.fstat(stream.fileno())
            os.link(temporary, self.path)
            temporary.unlink()
            temporary = None
        except BaseException as exc:
            self.rollback()
            if isinstance(exc, FileExistsError):
                raise KitError(7, "output exists") from exc
            if isinstance(exc, OSError):
                raise KitError(7, "I/O error") from exc
            raise
        finally:
            if temporary is not None:
                with suppress(OSError):
                    temporary.unlink(missing_ok=True)


def publish(path: Path, content: bytes, *, inputs: tuple[Path, ...] = ()) -> None:
    Publication(path).write(content, inputs=inputs)
