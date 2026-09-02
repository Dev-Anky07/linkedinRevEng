"""Helpers for LinkedIn's RSC pagination responses.

The pager identifier is present in the details-page rehydration payload. The
tracing span is intentionally resolved afresh from that same response: it is
short-lived and must never be hard-coded.
"""

from html import unescape
import json
import re
import secrets
from typing import Any
from urllib.parse import urlencode


PAGINATION_PATH = "/flagship-web/rsc-action/actions/pagination"
LANGUAGES_PAGER_ID = "com.linkedin.sdui.pagers.profile.details.languages"
LANGUAGES_SCREEN_ID = "com.linkedin.sdui.flagshipnav.profile.ProfileLanguageDetails"
CERTIFICATIONS_PAGER_ID = "com.linkedin.sdui.pagers.profile.details.certifications"
CERTIFICATIONS_SCREEN_ID = "com.linkedin.sdui.flagshipnav.profile.ProfileCertificationDetails"
SKILLS_PAGER_ID = "com.linkedin.sdui.pagers.profile.details.skills"
SKILLS_SCREEN_ID = "com.linkedin.sdui.flagshipnav.profile.ProfileSkillDetails"


def build_pagination_path(document: str, pager_id: str) -> str | None:
    """Build a pagination path from the details-page rehydration payload.

    `parentSpanId` is a best-effort trace-context value. A live request is the
    final authority because LinkedIn can derive a child span client-side.
    """
    normalized = unescape(document).replace(r'\"', '"')
    pager_pattern = re.compile(r'"pagerId"\s*:\s*"' + re.escape(pager_id) + r'"')
    if not pager_pattern.search(normalized):
        return None

    context_pattern = re.compile(
        r'"htmlFetchSpanContext"\s*:\s*\{[^{}]*?"spanId"\s*:\s*"([^"]+)"',
        re.DOTALL,
    )
    match = context_pattern.search(normalized)
    if not match:
        return None

    return f"{PAGINATION_PATH}?{urlencode({'sduiid': pager_id, 'parentSpanId': match.group(1)})}"


def build_languages_request_body(document: str, username: str) -> dict | None:
    return build_section_request_body(document, username, LANGUAGES_PAGER_ID, LANGUAGES_SCREEN_ID)


def build_certifications_request_body(document: str, username: str) -> dict | None:
    return build_section_request_body(document, username, CERTIFICATIONS_PAGER_ID, CERTIFICATIONS_SCREEN_ID)


def build_skills_request_body(document: str, username: str) -> dict | None:
    return build_section_request_body(document, username, SKILLS_PAGER_ID, SKILLS_SCREEN_ID)


def build_section_request_body(document: str, username: str, pager_id: str, screen_id: str) -> dict | None:
    """Build a POST body from current details-page pagination metadata."""
    normalized = unescape(document).replace(r'\"', '"')
    pager_index = normalized.find(f'"pagerId":"{pager_id}"')
    if pager_index < 0:
        return None

    # The lazy-column's requestedArguments follow its pager id. Keep this
    # extraction local to that block so we never reuse another profile's id.
    pager_block = normalized[pager_index : pager_index + 12000]
    profile_id_match = re.search(r'"profileId"\s*:\s*"([^"]+)"', pager_block)
    if not profile_id_match:
        return None

    def read_number(name: str, default: int) -> int:
        match = re.search(rf'"{name}"\s*:\s*(\d+)', pager_block)
        return int(match.group(1)) if match else default

    payload = {
        "vanityName": username,
        "start": read_number("start", 0),
        "count": read_number("count", 10),
        "profileId": profile_id_match.group(1),
    }
    filter_match = re.search(r'"filter"\s*:\s*"([^"\\]+)"', pager_block)
    if filter_match:
        payload["filter"] = filter_match.group(1)
    requested_arguments = {
        "$type": "proto.sdui.actions.requests.RequestedArguments",
        "requestedStateKeys": [],
        "payload": payload,
        "requestMetadata": {"$type": "proto.sdui.common.RequestMetadata"},
    }
    return {
        "pagerId": pager_id,
        "clientArguments": {
            **requested_arguments,
            "states": [],
            "screenId": screen_id,
            "knownTemplateIds": [],
        },
        "paginationRequest": {
            "$type": "proto.sdui.actions.requests.PaginationRequest",
            "pagerId": pager_id,
            "trigger": {
                "$case": "itemDistanceTrigger",
                "itemDistanceTrigger": {
                    "$type": "proto.sdui.actions.requests.ItemDistanceTrigger",
                    "preloadDistance": 3,
                    "preloadLength": 250,
                },
            },
            "retryCount": 2,
            "requestedArguments": requested_arguments,
        },
    }


def build_languages_rsc_headers(document: str) -> dict[str, str] | None:
    return build_section_rsc_headers(document, "d_flagship3_profile_view_base_languages_details")


def build_certifications_rsc_headers(document: str) -> dict[str, str] | None:
    return build_section_rsc_headers(document, "d_flagship3_profile_view_base_certifications_details")


def build_skills_rsc_headers(document: str) -> dict[str, str] | None:
    return build_section_rsc_headers(document, "d_flagship3_profile_view_base_skills_details")


def build_section_rsc_headers(document: str, anchor_key: str) -> dict[str, str] | None:
    """Derive page-context headers from the current section details-page HTML."""
    meta_match = re.search(
        r'<meta[^>]+name=["\']como-t["\'][^>]+content=["\']([^"\']+)["\']',
        document,
        re.IGNORECASE,
    )
    if not meta_match:
        # HTML attributes can be emitted in the opposite order.
        meta_match = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']como-t["\']',
            document,
            re.IGNORECASE,
        )
    if not meta_match:
        return None

    try:
        context = json.loads(unescape(meta_match.group(1)))
        page_forest_id = context["pageForestId"]
        tracking_id = context["trackingId"]
        application_instance = context["appTrackingId"]
        application_version = context["serviceVersion"]
    except (KeyError, json.JSONDecodeError):
        return None

    headers = {
        "x-li-anchor-page-key": anchor_key,
        "x-li-application-instance": application_instance,
        "x-li-application-version": application_version,
        "x-li-page-instance": f"urn:li:page:{anchor_key};{tracking_id}",
        "x-li-page-instance-tracking-id": tracking_id,
        "x-li-pageforestid": page_forest_id,
        "x-li-rsc-stream": "true",
        "x-li-track": json.dumps(
            {
                "clientVersion": application_version,
                "mpVersion": application_version,
                "osName": "web",
                "timezone": "Asia/Calcutta",
                "timezoneOffset": 5.5,
                "deviceFormFactor": "DESKTOP",
                "mpName": "web",
            },
            separators=(",", ":"),
        ),
    }
    if re.fullmatch(r"[0-9a-fA-F]{32}", page_forest_id):
        child_span_id = secrets.token_hex(8)
        headers["x-li-traceparent"] = f"00-{page_forest_id}-{child_span_id}-00"
        headers["x-li-tracestate"] = f"LinkedIn={child_span_id}"
    return headers


def parse_languages_rsc(payload: str) -> list[dict[str, str]]:
    """Extract name/proficiency pairs from a React Flight/RSC response."""
    paragraph_texts: list[str] = []
    for line in payload.splitlines():
        if ":" not in line:
            continue
        _, raw_value = line.split(":", 1)
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            continue
        _collect_paragraph_text(value, paragraph_texts)

    proficiency_pattern = re.compile(
        r"^(Native or bilingual|Full professional|Professional working|Limited working|Elementary) proficiency$",
        re.IGNORECASE,
    )
    languages: list[dict[str, str]] = []
    for index, text in enumerate(paragraph_texts[:-1]):
        proficiency = paragraph_texts[index + 1]
        if text != "Languages" and proficiency_pattern.match(proficiency):
            languages.append({"name": text, "proficiency": proficiency})
    return languages


def parse_certifications_rsc(payload: str) -> list[dict[str, str | None]]:
    """Extract certification cards from a React Flight/RSC pagination response.

    LinkedIn represents each card's title and issuer as adjacent paragraph
    elements. Issue date and credential ID are rendered via referenced text
    components, so the walker resolves those references in document order.
    """
    events = _collect_certification_events(payload)
    certifications: list[dict[str, str | None]] = []
    current: dict[str, str | None] | None = None

    def finish_current() -> None:
        nonlocal current
        if current and current.get("name") and current.get("issuer"):
            certifications.append(current)
        current = None

    for kind, text in events:
        if kind == "title":
            finish_current()
            current = {"name": text, "issuer": None, "issuedDate": None, "credentialId": None}
        elif kind == "issuer" and current and current["issuer"] is None:
            current["issuer"] = text
        elif kind == "issued" and current:
            current["issuedDate"] = text.removeprefix("Issued ")
        elif kind == "credential_id" and current:
            current["credentialId"] = text.removeprefix("Credential ID ")

    finish_current()
    return certifications


def parse_skills_rsc(payload: str) -> list[str]:
    """Extract skill titles from a React Flight/RSC pagination response."""
    skills: list[str] = []
    for line in payload.splitlines():
        if ":" not in line:
            continue
        _, raw_value = line.split(":", 1)
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            continue
        if not _has_skill_component(value):
            continue
        text_values: list[str] = []
        _collect_text_prop_values(value, text_values)
        # The first text component is the skill title. Later text components
        # can describe an endorsement or the role where it was used.
        if text_values:
            skills.append(text_values[0])

    # Definitions can be referenced more than once; retain first occurrence.
    return list(dict.fromkeys(skill for skill in skills if skill))


def _collect_certification_events(payload: str) -> list[tuple[str, str]]:
    definitions: dict[str, Any] = {}
    root: Any = None
    for line in payload.splitlines():
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            continue
        definitions[key] = value
        if key == "0":
            root = value

    events: list[tuple[str, str]] = []

    def walk(value: Any, resolving: set[str]) -> None:
        if isinstance(value, str):
            reference = re.fullmatch(r"\$L([0-9a-z]+)", value)
            if reference and reference.group(1) in definitions and reference.group(1) not in resolving:
                walk(definitions[reference.group(1)], resolving | {reference.group(1)})
            return

        if isinstance(value, list):
            if len(value) == 4 and value[0] == "$" and value[1] == "p" and isinstance(value[3], dict):
                props = value[3]
                text = _read_text(props.get("children"))
                if text:
                    # The title paragraph is visually styled; an issuer is the
                    # following unstyled paragraph. Orphan paragraphs are media
                    # captions and are ignored by the state machine above.
                    events.append(("title" if props.get("style") else "issuer", text))
            for item in value:
                walk(item, resolving)
            return

        if isinstance(value, dict):
            text_props = value.get("textProps")
            if isinstance(text_props, dict):
                text = _read_text(text_props.get("children"))
                if text.startswith("Issued "):
                    events.append(("issued", text))
                elif text.startswith("Credential ID "):
                    events.append(("credential_id", text))
            for item in value.values():
                walk(item, resolving)

    if root is not None:
        walk(root, set())
    return events


def _read_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return "".join(value).strip()
    return ""


def _has_skill_component(value: Any) -> bool:
    if isinstance(value, dict):
        component_key = value.get("componentKey") or value.get("componentkey")
        if isinstance(component_key, str) and component_key.startswith("com.linkedin.sdui.profile.skill("):
            return True
        return any(_has_skill_component(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_skill_component(item) for item in value)
    return False


def _collect_text_prop_values(value: Any, output: list[str]) -> None:
    if isinstance(value, dict):
        text_props = value.get("textProps")
        if isinstance(text_props, dict):
            text = _read_text(text_props.get("children"))
            if text:
                output.append(text)
        for item in value.values():
            _collect_text_prop_values(item, output)
    elif isinstance(value, list):
        for item in value:
            _collect_text_prop_values(item, output)


def _collect_paragraph_text(value: Any, output: list[str]) -> None:
    if isinstance(value, list):
        if len(value) == 4 and value[0] == "$" and value[1] == "p" and isinstance(value[3], dict):
            children = value[3].get("children")
            if isinstance(children, list) and all(isinstance(item, str) for item in children):
                output.append("".join(children).strip())
        for item in value:
            _collect_paragraph_text(item, output)
    elif isinstance(value, dict):
        for item in value.values():
            _collect_paragraph_text(item, output)
