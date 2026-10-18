"""Explicit synthetic source declarations; never derived from a candidate workflow."""

from typing import Annotated

from pydantic import Field, StrictInt, ValidationError

from connect_automate.automate import SourceBinding
from connect_automate.automate.definition import MAX_NAME_LENGTH
from connect_automate.automate.events import Event

from .core import SPEC_LIMIT, KitError, StrictModel, json_object


class NamedBinding(SourceBinding):
    name: Annotated[str, Field(strict=True, min_length=1, max_length=MAX_NAME_LENGTH)]


class EventCatalogue(StrictModel):
    format_version: Annotated[StrictInt, Field(ge=1, le=1)]
    binding: NamedBinding
    matching_event: Event

    def bindings(self):
        return {self.binding.name: self.binding.model_dump(mode="json", exclude={"name"})}

    def event_bytes(self):
        from .core import canonical

        return canonical(self.matching_event.model_dump(mode="json"))


def parse_catalogue(raw):
    data = json_object(raw, SPEC_LIMIT)
    try:
        return EventCatalogue.model_validate(data)
    except ValidationError:
        raise KitError(3, "invalid input") from None
