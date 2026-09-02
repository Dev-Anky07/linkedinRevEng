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
    """Build the POST JSON body from current details-page pagination metadata."""
    normalized = unescape(document).replace(r'\"', '"')
    pager_index = normalized.find(f'"pagerId":"{LANGUAGES_PAGER_ID}"')
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
    requested_arguments = {
        "$type": "proto.sdui.actions.requests.RequestedArguments",
        "requestedStateKeys": [],
        "payload": payload,
        "requestMetadata": {"$type": "proto.sdui.common.RequestMetadata"},
    }
    return {
        "pagerId": LANGUAGES_PAGER_ID,
        "clientArguments": {
            **requested_arguments,
            "states": [],
            "screenId": LANGUAGES_SCREEN_ID,
            "knownTemplateIds": [],
        },
        "paginationRequest": {
            "$type": "proto.sdui.actions.requests.PaginationRequest",
            "pagerId": LANGUAGES_PAGER_ID,
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
    """Derive page-context headers from the current Languages HTML response."""
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

    anchor_key = "d_flagship3_profile_view_base_languages_details"
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
