"""Checked shared HTTP grammar; origin and source hashes in manifest_policy_sources.json."""
import re
from pathlib import Path

FEATURE = "fixed-parameters-v1"
HEADER = "local-connect-manifest-features"
FIXTURE_DIR = Path(__file__).parent / "manifest_policy"

def header_values(headers):
    normalized = {}
    for name, value in headers.items():
        key = name.lower()
        if key in normalized:
            raise ValueError("ambiguous duplicate header name")
        normalized[key] = value
    return normalized


# RFC 9110 sections 5.6.2-5.6.4; RFC 9111 section 5.2.
# These are byte-valued HTTP fields represented as Python strings.
HTTP_TOKEN = r"[!#$%&'*+.^_`|~0-9A-Za-z-]+"
HTTP_OWS = r"[ \t]*"
HTTP_OBS_TEXT = r"\x80-\xff"
HTTP_QDTEXT = rf"[\x09\x20\x21\x23-\x5b\x5d-\x7e{HTTP_OBS_TEXT}]"
HTTP_QUOTED_PAIR = rf"\\[\x09\x20-\x7e{HTTP_OBS_TEXT}]"
HTTP_QUOTED_STRING = rf'"(?:{HTTP_QDTEXT}|{HTTP_QUOTED_PAIR})*"'
HTTP_ARGUMENT = rf"(?:{HTTP_TOKEN}|{HTTP_QUOTED_STRING})"
HTTP_CACHE_DIRECTIVE = rf"({HTTP_TOKEN})(?:=({HTTP_ARGUMENT}))?"
HTTP_DELTA_SECONDS = r"[0-9]+"


def freshness_rules():
    text = (FIXTURE_DIR / "README.md").read_text()
    table = text.split("<!-- freshness-rule-table -->", 1)[1].split(
        "<!-- /freshness-rule-table -->", 1
    )[0]
    rules = {}
    for line in table.splitlines():
        if not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells[0] in {"Member", "---"}:
            continue
        name, sender, recipient, citation, prefix = cells
        if name in rules:
            raise ValueError("duplicate freshness policy row")
        rules[name] = {
            "producer_conformance": sender,
            "consumer_admission": recipient,
            "citation": citation,
            "vector_prefix": prefix,
        }
    return rules


def directive_argument_valid(argument, rule, role):
    if rule == "forbidden":
        return argument is None
    if argument is None:
        return rule.startswith("optional-fields-")
    quoted = argument.startswith('"')
    value = re.sub(r"\\(.)", r"\1", argument[1:-1]) if quoted else argument
    if rule.startswith("required-delta-"):
        if quoted and rule == "required-delta-token":
            return False
        return re.fullmatch(HTTP_DELTA_SECONDS, value) is not None
    if rule.startswith("optional-fields-"):
        if not quoted and rule == "optional-fields-quoted":
            return False
        if value == "":
            return True
        try:
            return bool(http_list_members(value, HTTP_TOKEN, role, "Vary-list"))
        except ValueError:
            return False
    raise ValueError("unknown directive policy")


def http_list_members(value, member, role, field="Cache-Control-list"):
    """One list owner counts only separators outside validated quoted members."""
    pattern = re.compile(
        rf"{HTTP_OWS}(?P<member>{member})?{HTTP_OWS}(?P<separator>,|\Z)"
    )
    limit = int(freshness_rules()[field][role].removeprefix("empty-limit:"))
    position, empty_count, members = 0, 0, []
    while True:
        match = pattern.match(value, position)
        if match is None:
            raise ValueError("malformed list member")
        item = match.group("member")
        if item is None:
            empty_count += 1
            if empty_count > limit:
                raise ValueError("empty list element limit exceeded")
        else:
            members.append(item)
        if not match.group("separator"):
            return members
        position = match.end()


def freshness_fields(response, role="producer_conformance"):
    """One grammar owner; freshness obligations belong to exchange_errors."""
    errors, directives, vary = [], set(), set()
    if "cache-control" in response:
        try:
            members = http_list_members(
                response["cache-control"], HTTP_CACHE_DIRECTIVE, role
            )
        except ValueError:
            errors.append("malformed Cache-Control")
        else:
            for member in members:
                name, argument = re.fullmatch(HTTP_CACHE_DIRECTIVE, member).groups()
                name = name.lower()
                directives.add(name)
                rule = freshness_rules().get(name)
                if rule is not None and not directive_argument_valid(
                    argument, rule[role], role
                ):
                    errors.append("malformed recognized cache directive")
    if "vary" in response:
        try:
            members = http_list_members(response["vary"], HTTP_TOKEN, role, "Vary-list")
        except ValueError:
            errors.append("malformed Vary")
        else:
            vary = {member.lower() for member in members}
            if "*" in vary and len(members) != 1:
                errors.append("malformed Vary")
    return errors, directives, vary


