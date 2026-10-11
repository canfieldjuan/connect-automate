"""ADR-0013 conformance oracle only; no application/runtime execution."""

from copy import deepcopy
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from tests.test_contracts import semantic_errors, _parameter_type_matches

ROOT = Path(__file__).resolve().parents[1]
FEATURE = "fixed-parameters-v1"
HEADER = "local-connect-manifest-features"
SCHEMA_DIR = ROOT / "schemas/v2/features" / FEATURE
FIXTURE_DIR = ROOT / "fixtures/v2/features" / FEATURE
BASE = "https://local-connect.invalid/schemas/v2/"
FEATURE_BASE = BASE + "features/" + FEATURE + "/"


def load(path):
    return json.loads(path.read_text())


def derive_manifest_schema():
    """Only the parameter extension changes; inherited schema owns all else."""
    schema = deepcopy(load(ROOT / "schemas/v2/manifest.schema.json"))
    schema["$id"] = FEATURE_BASE + "manifest.schema.json"
    schema["title"] = "Negotiated fixed-parameters-v1 manifest"
    parameter = schema["$defs"]["parameter"]
    types = load(ROOT / "schemas/v2/job-request.schema.json")["properties"][
        "parameters"
    ]["additionalProperties"]["oneOf"]
    parameter["properties"]["fixed_value"] = {"oneOf": deepcopy(types)}
    parameter["allOf"] = [
        {
            "if": {"required": ["fixed_value"]},
            "then": {"properties": {"required": {"const": True}}},
        },
        *[
            {
                "if": {
                    "properties": {"value_type": {"const": kind}},
                    "required": ["value_type"],
                },
                "then": {"properties": {"fixed_value": deepcopy(value_schema)}},
            }
            for kind, value_schema in zip(("string", "integer", "boolean"), types)
        ],
    ]
    return schema


def validator(name):
    resources = [load(p) for p in (ROOT / "schemas/v2").glob("*.schema.json")]
    resources += [load(p) for p in SCHEMA_DIR.glob("*.schema.json")]
    registry = Registry().with_resources(
        (r["$id"], Resource.from_contents(r)) for r in resources
    )
    schema = next(r for r in resources if r["$id"] == name)
    return Draft202012Validator(schema, registry=registry)


def schema_errors(name, value):
    return [error.message for error in validator(name).iter_errors(value)]


def manifest_errors(manifest, extended=True):
    errors = schema_errors(
        (FEATURE_BASE if extended else BASE) + "manifest.schema.json", manifest
    )
    if errors:
        return errors
    errors += semantic_errors("v2", "manifest.schema.json", manifest)
    for cap in manifest["capabilities"]:
        if cap["id"] != "document.classify":
            continue
        if not extended:
            errors.append("classifier must be omitted from legacy discovery")
            continue
        parameters = {p["name"]: p for p in cap["parameters"]}
        if set(parameters) != {"record-version", "classifier-version"}:
            errors.append("classifier compatibility parameters differ")
            continue
        record, bundle = parameters["record-version"], parameters["classifier-version"]
        if (
            cap["version"] != "1.0"
            or record["value_type"] != "string"
            or bundle["value_type"] != "string"
            or record.get("fixed_value") != "1.0"
            or not re.fullmatch("[0-9a-f]{64}", bundle.get("fixed_value", ""))
        ):
            errors.append("classifier fixed identity is not admitted")
    return errors


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


def exchange_errors(exchange, current_manifest=None):
    errors = schema_errors(FEATURE_BASE + "exchange.schema.json", exchange)
    if errors:
        return errors
    try:
        request = header_values(exchange["request_headers"])
        response = header_values(exchange["response_headers"])
    except ValueError as error:
        return [str(error)]
    token, ack = request.get(HEADER), response.get(HEADER)
    if ack is not None and (token != FEATURE or ack != FEATURE):
        errors.append("acknowledgment does not match supported request")
    extended = token == FEATURE and ack == FEATURE
    role = exchange.get("validation_role", "producer_conformance")
    freshness_errors, directives, vary = freshness_fields(response, role)
    errors += freshness_errors
    strict = role == "producer_conformance" or extended
    if (strict or "cache-control" in response) and "no-store" not in directives:
        errors.append("manifest response must forbid storage")
    if strict and (
        HEADER not in vary
        or not {v.lower() for v in exchange["existing_vary"]}.issubset(vary)
    ):
        errors.append("manifest Vary must include feature and preserve existing fields")
    if exchange["from_cache"]:
        errors.append("manifest response cannot be reused")
    errors += manifest_errors(exchange["manifest"], extended)
    if current_manifest is not None:
        expected = deepcopy(current_manifest)
        if not extended:
            expected["capabilities"] = [
                c
                for c in expected["capabilities"]
                if c["id"] != "document.classify"
                and not any("fixed_value" in p for p in c["parameters"])
            ]
        if not frozen_json_equal(exchange["manifest"], expected):
            errors.append("rediscovery did not observe current declaration")
    return errors


def fixed_values_match(request, manifest):
    cap = next(
        c
        for c in manifest["capabilities"]
        if request["capability"] == {"id": c["id"], "version": c["version"]}
    )
    for parameter in cap["parameters"]:
        if "fixed_value" not in parameter:
            continue
        value = request["parameters"].get(parameter["name"])
        if not _parameter_type_matches(
            parameter["value_type"], value
        ) or not wire_equal(value, parameter["fixed_value"]):
            return False
    return True


def wire_equal(left, right):
    """JSON value equality with distinct booleans and numeric value semantics."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is bool and type(right) is bool and left == right
    if isinstance(left, dict) or isinstance(right, dict):
        return (
            isinstance(left, dict)
            and isinstance(right, dict)
            and left.keys() == right.keys()
            and all(wire_equal(left[k], right[k]) for k in left)
        )
    if isinstance(left, list) or isinstance(right, list):
        return (
            isinstance(left, list)
            and isinstance(right, list)
            and len(left) == len(right)
            and all(wire_equal(a, b) for a, b in zip(left, right))
        )
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    return type(left) is type(right) and left == right


def frozen_json_equal(left, right):
    """Compare frozen fixture snapshots, preserving numeric forms and booleans.

    This deterministic test serialization is not a provider digest algorithm.
    The vectors do not decide owner-defined numeric-spelling equivalence.
    """
    return json.dumps(
        left, sort_keys=True, separators=(",", ":"), allow_nan=False
    ) == json.dumps(right, sort_keys=True, separators=(",", ":"), allow_nan=False)


def same_request(left, right):
    """Replay identical frozen snapshots; production identity stays owner-defined."""
    return frozen_json_equal(left, right)


def decision(kind, request=None):
    result = {"decision": kind, "starts_work": kind == "accept"}
    if request is not None:
        result["bound_parameters"] = deepcopy(request["parameters"])
    if kind == "fixed_mismatch":
        result.update(http_status=409, code="FIXED_PARAMETER_MISMATCH", retryable=False)
    if kind == "conflict":
        result.update(code="JOB_CONFLICT")
    return result


def admission_outcome(context):
    """One ordered admission model reused by snapshots and event traces."""
    manifest, request, existing = (
        context["manifest"],
        context["request"],
        context["existing"],
    )
    if existing is not None:
        if not same_request(request, existing["request"]):
            return decision("conflict")
        if existing["status"] != "failed":
            return decision("replay", existing["request"])
    if semantic_errors("v2", "job-request.schema.json", request, manifest):
        return decision("invalid_request")
    if not fixed_values_match(request, manifest):
        return decision("fixed_mismatch")
    return decision("accept", request)


def admission_errors(context):
    errors = schema_errors(FEATURE_BASE + "admission.schema.json", context)
    if errors:
        return errors
    errors += manifest_errors(context["manifest"])
    existing = context["existing"]
    if existing is not None:
        errors += manifest_errors(existing["manifest"])
        if existing["request"]["job_id"] != context["request"]["job_id"]:
            errors.append("existing snapshot names a different job")
        if not errors:
            errors += semantic_errors(
                "v2",
                "job-request.schema.json",
                existing["request"],
                existing["manifest"],
            )
            if not errors and not fixed_values_match(
                existing["request"], existing["manifest"]
            ):
                errors.append("snapshot was not admitted under recorded identity")
    return errors


def sequence_result(sequence):
    errors = schema_errors(FEATURE_BASE + "sequence.schema.json", sequence)
    if errors:
        return errors, None
    manifest = sequence["initial_manifest"]
    errors += manifest_errors(manifest)
    jobs, outcomes = {}, []
    if errors:
        return errors, None
    for event in sequence["events"]:
        kind = event["kind"]
        if kind == "rotate":
            manifest = event["manifest"]
            errors += manifest_errors(manifest)
        elif kind == "discover":
            errors += exchange_errors(event["exchange"], manifest)
            outcomes.append({"decision": "discover_current"})
        elif kind == "mark_failed":
            if event["job_id"] not in jobs:
                errors.append("cannot fail an unaccepted model job")
            else:
                jobs[event["job_id"]]["status"] = "failed"
        else:
            request = event["request"]
            context = {
                "manifest": manifest,
                "request": request,
                "existing": jobs.get(request["job_id"]),
            }
            errors += admission_errors(context)
            if errors:
                return errors, None
            outcome = admission_outcome(context)
            outcomes.append(outcome)
            if outcome["decision"] == "accept":
                jobs[request["job_id"]] = {
                    "manifest": deepcopy(manifest),
                    "request": deepcopy(request),
                    "status": "accepted",
                }
        if errors:
            return errors, None
    return [], outcomes


def vector_result(vector):
    value, kind = vector["input"], vector["kind"]
    if kind == "manifest":
        return manifest_errors(value), None
    if kind == "exchange":
        return exchange_errors(value), None
    if kind == "admission":
        errors = admission_errors(value)
        return errors, None if errors else admission_outcome(value)
    if kind == "sequence":
        return sequence_result(value)
    if kind == "refusal":
        return schema_errors(FEATURE_BASE + "refusal.schema.json", value), None
    raise ValueError("unknown fixture kind")
