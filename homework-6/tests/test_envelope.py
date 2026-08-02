"""Tests for the shared kernel: closed sets, money tables, masking, envelopes.

Covers specification.md sections C2, C3, C5 and C7.
"""

from __future__ import annotations

import copy
from decimal import ROUND_HALF_EVEN, Decimal

import pytest

from agents import envelope as env


def test_status_set_holds_exactly_the_eight_specified_members():
    """The closed `status` set of section C3 admits nothing else."""
    assert env.STATUS == frozenset(
        {
            "received",
            "validated",
            "rejected",
            "risk_scored",
            "held",
            "cleared",
            "blocked",
            "settled",
        }
    )


def test_reason_set_holds_exactly_the_six_specified_members():
    """The closed `reason` set of section C3 admits nothing else."""
    assert env.REASON == frozenset(
        {
            "missing_field",
            "invalid_currency",
            "non_positive_amount",
            "malformed_amount",
            "sanctioned_counterparty",
            "manual_review_required",
        }
    )


def test_risk_level_and_message_type_sets_match_the_specification():
    """`risk_level` and `message_type` are closed at three members each."""
    assert env.RISK_LEVEL == frozenset({"low", "medium", "high"})
    assert env.MESSAGE_TYPE == frozenset({"transaction", "result", "summary"})


def test_held_is_terminal_alongside_rejected_blocked_and_settled():
    """Section C3 makes `held` terminal for the batch, so it routes to results."""
    assert env.TERMINAL_STATUSES == frozenset(
        {"rejected", "blocked", "settled", "held"}
    )
    assert env.Status.RISK_SCORED not in env.TERMINAL_STATUSES
    assert env.Status.CLEARED not in env.TERMINAL_STATUSES
    assert env.Status.VALIDATED not in env.TERMINAL_STATUSES


def test_currency_allow_list_minor_units_and_fx_table_cover_the_same_currencies():
    """Every allow-listed currency has both a minor unit and an FX rate."""
    assert env.CURRENCY_ALLOW_LIST == frozenset({"USD", "EUR", "GBP", "JPY"})
    assert set(env.MINOR_UNITS) == env.CURRENCY_ALLOW_LIST
    assert set(env.FX_TABLE) == env.CURRENCY_ALLOW_LIST
    assert env.BASE_CURRENCY == "USD"
    assert env.DOMESTIC_COUNTRY == "US"
    assert env.FX_RATES_AS_OF == "2026-03-16"


@pytest.mark.parametrize(
    ("currency", "rate", "minor_unit"),
    [
        ("USD", Decimal("1.000000"), 2),
        ("EUR", Decimal("1.080000"), 2),
        ("GBP", Decimal("1.270000"), 2),
        ("JPY", Decimal("0.006700"), 0),
    ],
)
def test_fx_table_holds_the_specified_rate_and_minor_unit(currency, rate, minor_unit):
    """Section C5 fixes each rate and minor unit exactly."""
    assert env.FX_TABLE[currency] == rate
    assert str(env.FX_TABLE[currency]) == str(rate)
    assert env.MINOR_UNITS[currency] == minor_unit


def test_no_fx_rate_is_a_float():
    """A binary float in the FX table would poison every conversion."""
    for rate in env.FX_TABLE.values():
        assert isinstance(rate, Decimal)
        assert not isinstance(rate, float)


def test_utc_now_iso_is_second_precision_utc_with_a_z_suffix(iso_utc):
    """Timestamps are asserted on shape, never on value."""
    assert iso_utc.match(env.utc_now_iso())


@pytest.mark.parametrize(
    ("account", "expected"),
    [
        ("ACC-1001", "ACC-****01"),
        ("ACC-9999", "ACC-****99"),
        ("ACC-123456789", "ACC-****89"),
        ("IBAN-GB-4471", "IBAN-GB-****71"),
        ("ACC-1", "ACC-****"),
        ("ACC-", "ACC-****"),
        ("12345", "****45"),
        ("A", "****"),
        ("", "****"),
        (None, "****"),
    ],
)
def test_mask_account_keeps_the_prefix_and_the_last_two_characters(account, expected):
    """Section C7: keep through the final hyphen plus the last two characters."""
    assert env.mask_account(account) == expected


def test_mask_length_is_fixed_so_it_cannot_leak_the_account_length():
    """Four asterisks whatever was masked, so a short account is indistinguishable."""
    short = env.mask_account("ACC-1001")
    long = env.mask_account("ACC-100000000001")
    assert short.count("*") == long.count("*") == 4
    assert len(short) == len(long)


def test_mask_accounts_scrubs_every_account_shaped_token_in_free_text():
    """Free text bound for a log passes each account through `mask_account`."""
    masked = env.mask_accounts("transfer ACC-1001 -> ACC-2001 failed")
    assert "ACC-1001" not in masked
    assert "ACC-2001" not in masked
    assert masked == "transfer ACC-****01 -> ACC-****01 failed"


@pytest.mark.parametrize("text", ["", None, "no account here"])
def test_mask_accounts_leaves_text_without_an_account_untouched(text):
    """Nothing account-shaped means nothing to change."""
    assert env.mask_accounts(text) == text


def test_usd_equivalent_multiplies_without_quantizing():
    """Conversion keeps full precision; quantizing happens once, at settlement."""
    assert env.usd_equivalent(Decimal("500.00"), "EUR") == Decimal("540.000000")
    assert env.usd_equivalent(Decimal("9999.99"), "USD") == Decimal("9999.990000")
    assert env.usd_equivalent(Decimal("1"), "JPY") == Decimal("0.006700")


def test_quantize_money_rounds_half_up_where_half_even_would_round_down():
    """Section B4 requires ROUND_HALF_UP; the decimal default would give 0.12."""
    value = Decimal("0.125")
    assert env.quantize_money(value, "USD") == Decimal("0.13")
    assert value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN) == Decimal("0.12")


def test_quantize_money_uses_the_zero_minor_unit_of_jpy():
    """JPY has no minor unit, so it quantizes to whole units."""
    assert env.quantize_money(Decimal("1234.5"), "JPY") == Decimal("1235")
    assert str(env.quantize_money(Decimal("1234.4"), "JPY")) == "1234"


def test_build_envelope_produces_the_six_contract_keys():
    """Section C2 fixes the envelope shape at exactly six top-level keys."""
    message = env.build_envelope(
        "integrator", "transaction_validator", "transaction", {"transaction_id": "T1"}
    )
    assert set(message) == {
        "message_id",
        "timestamp",
        "source_agent",
        "target_agent",
        "message_type",
        "data",
    }
    assert message["source_agent"] == "integrator"
    assert message["target_agent"] == "transaction_validator"
    assert message["message_type"] == "transaction"


def test_build_envelope_deep_copies_data_so_the_caller_cannot_alias_it():
    """A later mutation of the source payload must not reach the envelope."""
    payload = {"transaction_id": "T1", "metadata": {"channel": "api"}}
    message = env.build_envelope("a", "b", "transaction", payload)
    original = copy.deepcopy(message["data"])

    payload["metadata"]["channel"] = "branch"
    message["data"]["metadata"]["country"] = "DE"

    assert message["data"]["metadata"]["channel"] == "api"
    assert "country" not in payload["metadata"]
    assert original == {"transaction_id": "T1", "metadata": {"channel": "api"}}


def test_build_envelope_mints_a_fresh_message_id_each_time():
    """Every hop gets its own identifier."""
    first = env.build_envelope("a", "b", "transaction", {})
    second = env.build_envelope("a", "b", "transaction", {})
    assert first["message_id"] != second["message_id"]
    assert len(first["message_id"]) == 36


def test_build_envelope_honours_an_explicit_message_id():
    """A caller may pin the id so a derived reference is reproducible."""
    message = env.build_envelope("a", "b", "transaction", {}, message_id="fixed-id")
    assert message["message_id"] == "fixed-id"
