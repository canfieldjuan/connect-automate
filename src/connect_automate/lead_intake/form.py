"""Structural extraction for the signed synthetic form template."""

from pydantic import Field

from .source import FormSnapshot, _Closed


class FormInputError(ValueError):
    def __init__(self):
        super().__init__("invalid lead form structure")


class FormFields(_Closed):
    name: str = Field(repr=False)
    email: str = Field(repr=False)
    message: str = Field(repr=False)


class _HeaderBlock(_Closed):
    name: str = Field(alias="Name")
    email: str = Field(alias="Email")


def parse_synthetic_form(snapshot: FormSnapshot) -> FormFields:
    """Consume two header lines and then the message marker, retaining body framing.

    A single ASCII space after each colon is an optional separator. Every byte
    after that separator in Message belongs to the field, including newlines.
    """
    try:
        snapshot = FormSnapshot.model_validate(snapshot)
        remainder = snapshot.part.content_bytes().decode("utf-8")
        headers = {}
        for _ in range(2):
            line, _, remainder = remainder.partition("\n")
            label, colon, value = line.removesuffix("\r").partition(":")
            if not colon or "\r" in value:
                raise FormInputError()
            headers[label] = value.removeprefix(" ")
        # The closed two-field schema requires one of each label. With exactly
        # two lines, duplicate labels leave one required header missing.
        header = _HeaderBlock.model_validate(headers)
        label, colon, message = remainder.partition(":")
        if label == "Message" and colon:
            return FormFields(**header.model_dump(), message=message.removeprefix(" "))
    except (ValueError, TypeError, RecursionError):
        pass
    raise FormInputError()
