"""HubSpot CRM: list open deals and filter by staleness.

Uses ``hs_lastmodifieddate`` as a proxy for deal activity (upgrade later to
engagements API for true touch tracking).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Iterable

from hubspot import HubSpot
from hubspot.crm.companies import (
    BatchReadInputSimplePublicObjectId as CompanyBatchReadInput,
)
from hubspot.crm.companies import SimplePublicObjectId as CompanySimplePublicObjectId
from hubspot.crm.companies.exceptions import ApiException as CompaniesApiException
from hubspot.crm.contacts import (
    BatchReadInputSimplePublicObjectId as ContactBatchReadInput,
)
from hubspot.crm.contacts import SimplePublicObjectId as ContactSimplePublicObjectId
from hubspot.crm.contacts.exceptions import ApiException as ContactsApiException
from hubspot.crm.deals.exceptions import ApiException as DealsApiException

from config.settings import settings
from graph.state import DealInfo

LOGGER = logging.getLogger(__name__)

_DEAL_PROPS = (
    "dealname",
    "amount",
    "dealstage",
    "pipeline",
    "hs_lastmodifieddate",
    "hs_is_closed",
)

_DEFAULT_PAGE_LIMIT = 100
_DEFAULT_MAX_PAGES = 50


def _use_mock() -> bool:
    return os.getenv("HUBSPOT_USE_MOCK", "").lower() in ("1", "true", "yes")


class HubSpotIntegrationError(RuntimeError):
    """Raised when HubSpot returns an error we do not recover from."""


def _client() -> HubSpot:
    return HubSpot(access_token=settings.hubspot_api_key)


def _parse_hubspot_datetime(value: str | None) -> datetime | None:
    if value is None or value == "":
        return None
    value = value.strip()
    try:
        if value.isdigit():
            ms = int(value)
            return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, OSError):
        return None


def _props(deal: Any) -> dict[str, str]:
    raw = getattr(deal, "properties", None) or {}
    if hasattr(raw, "to_dict"):
        raw = raw.to_dict()
    return raw if isinstance(raw, dict) else {}


def _associations_dict(deal: Any) -> dict[str, Any]:
    raw = getattr(deal, "associations", None)
    if raw is None:
        return {}
    if hasattr(raw, "to_dict"):
        raw = raw.to_dict()
    return raw if isinstance(raw, dict) else {}


def _first_assoc_id(deal: Any, *keys: str) -> str | None:
    assoc = _associations_dict(deal)
    for key in keys:
        coll = assoc.get(key)
        if coll is None:
            continue
        results = getattr(coll, "results", None)
        if results is None and isinstance(coll, dict):
            results = coll.get("results")
        if not results:
            continue
        first = results[0]
        rid = getattr(first, "id", None)
        if rid is None and isinstance(first, dict):
            rid = first.get("id")
        if rid:
            return str(rid)
    return None


def _chunked(ids: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(ids), size):
        yield ids[i : i + size]


def _batch_read_contacts(client: HubSpot, ids: list[str]) -> dict[str, dict[str, str]]:
    if not ids:
        return {}
    out: dict[str, dict[str, str]] = {}
    for chunk in _chunked(list(dict.fromkeys(ids)), 100):
        body = ContactBatchReadInput(
            properties_with_history=[],
            inputs=[ContactSimplePublicObjectId(id=x) for x in chunk],
            properties=["email", "firstname", "lastname"],
        )
        try:
            response = client.crm.contacts.batch_api.read(body)
        except ContactsApiException as exc:
            LOGGER.warning("Contact batch read failed: %s", exc)
            continue
        for row in response.results or []:
            pid = str(row.id)
            p = row.properties or {}
            email = (p.get("email") or "").strip()
            fn = (p.get("firstname") or "").strip()
            ln = (p.get("lastname") or "").strip()
            name = (fn + " " + ln).strip()
            out[pid] = {"email": email, "name": name}
    return out


def _batch_read_companies(client: HubSpot, ids: list[str]) -> dict[str, dict[str, str]]:
    if not ids:
        return {}
    out: dict[str, dict[str, str]] = {}
    for chunk in _chunked(list(dict.fromkeys(ids)), 100):
        body = CompanyBatchReadInput(
            properties_with_history=[],
            inputs=[CompanySimplePublicObjectId(id=x) for x in chunk],
            properties=["name", "domain", "website"],
        )
        try:
            response = client.crm.companies.batch_api.read(body)
        except CompaniesApiException as exc:
            LOGGER.warning("Company batch read failed: %s", exc)
            continue
        for row in response.results or []:
            pid = str(row.id)
            p = row.properties or {}
            name = (p.get("name") or "").strip()
            domain = (p.get("domain") or "").strip()
            web = (p.get("website") or "").strip()
            website = web or (f"https://{domain}" if domain else "")
            out[pid] = {"name": name, "website": website or None}
    return out


def _mock_stalled_deals() -> list[DealInfo]:
    return [
        DealInfo.from_hubspot_dict(
            {
                "deal_id": "mock-deal-1",
                "company_name": "Mock Industries",
                "contact_name": "Alex Buyer",
                "contact_email": "abdullah.corextech@gmail.com",
                "deal_value": 25000.0,
                "current_stage": "appointmentscheduled",
                "days_since_activity": settings.stale_deal_days + 3,
                "last_activity_type": "last_modified",
                "company_website": "https://example.com",
            }
        )
    ]


def get_stalled_deals(days_threshold: int | None = None) -> list[DealInfo]:
    """
    Return non-closed deals whose ``hs_lastmodifieddate`` is older than
    ``days_threshold`` days (defaults to ``settings.stale_deal_days``).

    Set env ``HUBSPOT_USE_MOCK=true`` to skip API calls (fixture deal).
    """
    threshold = days_threshold if days_threshold is not None else settings.stale_deal_days

    if _use_mock():
        LOGGER.info("HUBSPOT_USE_MOCK enabled; returning fixture deals")
        return _mock_stalled_deals()

    client = _client()
    raw_deals: list[Any] = []
    after: str | None = None

    for page_idx in range(_DEFAULT_MAX_PAGES):
        try:
            page = client.crm.deals.basic_api.get_page(
                limit=_DEFAULT_PAGE_LIMIT,
                after=after,
                properties=list(_DEAL_PROPS),
                associations=["contacts", "companies"],
            )
        except DealsApiException as exc:
            raise HubSpotIntegrationError("HubSpot deals list failed") from exc

        batch = page.results or []
        raw_deals.extend(batch)
        next_after = None
        if page.paging and page.paging.next and page.paging.next.after:
            next_after = page.paging.next.after
        if not next_after:
            break
        after = next_after
        if not batch:
            break
        if page_idx == _DEFAULT_MAX_PAGES - 1:
            LOGGER.warning("Stopped at max_pages=%s", _DEFAULT_MAX_PAGES)

    contact_ids: list[str] = []
    company_ids: list[str] = []
    for d in raw_deals:
        cid = _first_assoc_id(d, "contacts", "contact")
        if cid:
            contact_ids.append(cid)
        co = _first_assoc_id(d, "companies", "company")
        if co:
            company_ids.append(co)

    contacts = _batch_read_contacts(client, contact_ids)
    companies = _batch_read_companies(client, company_ids)

    now = datetime.now(timezone.utc)
    stalled: list[DealInfo] = []

    for deal in raw_deals:
        deal_id = str(deal.id)
        p = _props(deal)

        if (p.get("hs_is_closed") or "").lower() == "true":
            continue

        modified = _parse_hubspot_datetime(p.get("hs_lastmodifieddate"))
        if modified is None:
            days_since = threshold + 1
            LOGGER.warning(
                "Deal %s missing hs_lastmodifieddate; treating as stalled",
                deal_id,
            )
        else:
            delta = now - modified
            days_since = max(delta.days, 0)

        if days_since < threshold:
            continue

        amount_raw = p.get("amount") or "0"
        try:
            deal_value = float(amount_raw)
        except (TypeError, ValueError):
            deal_value = 0.0

        contact_id = _first_assoc_id(deal, "contacts", "contact")
        company_id = _first_assoc_id(deal, "companies", "company")

        cinfo = contacts.get(contact_id, {}) if contact_id else {}
        coinfo = companies.get(company_id, {}) if company_id else {}

        company_name = (coinfo.get("name") or p.get("dealname") or "").strip()
        contact_email = (cinfo.get("email") or "").strip()
        contact_name = (cinfo.get("name") or "").strip()
        website = coinfo.get("website")

        stalled.append(
            DealInfo.from_hubspot_dict(
                {
                    "deal_id": deal_id,
                    "company_name": company_name,
                    "contact_name": contact_name,
                    "contact_email": contact_email,
                    "deal_value": deal_value,
                    "current_stage": (p.get("dealstage") or "").strip(),
                    "days_since_activity": days_since,
                    "last_activity_type": "last_modified",
                    "company_website": website,
                }
            )
        )

    stalled.sort(key=lambda d: d.deal_value, reverse=True)
    return stalled


# HubSpot association: note -> deal
_NOTE_TO_DEAL_ASSOCIATION_TYPE_ID = 214


def add_deal_note(deal_id: str, note_body: str) -> str:
    """
    Attach a CRM note to a deal.

    Set ``HUBSPOT_USE_MOCK=true`` to skip the API call.
    """
    body = note_body.strip()
    if not body:
        raise HubSpotIntegrationError("Note body is required")

    if _use_mock():
        LOGGER.info(
            "HUBSPOT_USE_MOCK enabled; would add note to deal %s",
            deal_id,
        )
        return "mock-note-id"

    from hubspot.crm.objects.notes import SimplePublicObjectInputForCreate

    client = _client()
    timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    payload = SimplePublicObjectInputForCreate(
        properties={
            "hs_timestamp": str(timestamp_ms),
            "hs_note_body": body,
        },
        associations=[
            {
                "to": {"id": deal_id},
                "types": [
                    {
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": _NOTE_TO_DEAL_ASSOCIATION_TYPE_ID,
                    }
                ],
            }
        ],
    )

    try:
        result = client.crm.objects.notes.basic_api.create(
            simple_public_object_input_for_create=payload
        )
    except Exception as exc:
        raise HubSpotIntegrationError(f"HubSpot note create failed for deal {deal_id}") from exc

    note_id = str(result.id)
    LOGGER.info("Added HubSpot note %s on deal %s", note_id, deal_id)
    return note_id