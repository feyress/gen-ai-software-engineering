"""Decides whether a scored transaction may proceed to settlement.

Governed by specification.md sections C3 and C9. Screens the destination
account against a sanctions deny-list and raises the currency-transaction-report
flag at the 10,000 USD-equivalent threshold.

`SANCTIONS_DENY_LIST` holds invented test-only values. No real sanctions list
ships with this project and, by design, none of the eight sample destination
accounts appears in it, so an empty `blocked` count in the run summary is the
expected result rather than a gap.
"""

from __future__ import annotations

import copy
from decimal import Decimal

from agents.envelope import (
    MessageType,
    Reason,
    Status,
    build_envelope,
    mask_account,
    usd_equivalent,
    utc_now_iso,
)

AGENT_NAME = "compliance_checker"

SANCTIONS_DENY_LIST: frozenset[str] = frozenset({"ACC-4242", "ACC-6666", "ACC-7000"})

CTR_THRESHOLD = Decimal("10000.00")


def process_message(message: dict) -> dict:
    """Screen one risk-scored envelope and return a blocked or cleared envelope."""
    data = copy.deepcopy(message.get("data", {}))
    destination = data.get("destination_account")

    if destination in SANCTIONS_DENY_LIST:
        data["status"] = Status.BLOCKED
        data["reason"] = Reason.SANCTIONED_COUNTERPARTY
        data["reason_detail"] = (
            f"destination {mask_account(destination)} is on the sanctions deny-list"
        )
        return build_envelope(
            source_agent=AGENT_NAME,
            target_agent="results",
            message_type=MessageType.RESULT,
            data=data,
        )

    amount_usd = usd_equivalent(Decimal(data["amount"]), data["currency"])
    data["status"] = Status.CLEARED
    data["ctr_required"] = amount_usd >= CTR_THRESHOLD
    data["screened_at"] = utc_now_iso()
    return build_envelope(
        source_agent=AGENT_NAME,
        target_agent="settlement_processor",
        message_type=MessageType.TRANSACTION,
        data=data,
    )
