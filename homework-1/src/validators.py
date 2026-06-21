"""Validation logic and shared constants for the transactions API.

All functions here are pure: they take plain data and return errors. They never
touch Flask or the store directly (the store is reached only through an injected
``get_account_currency`` callable), which keeps them easy to unit-test.
"""
import re
from datetime import datetime, time, timezone
from decimal import Decimal, InvalidOperation

# ISO 4217 currency codes we accept. A curated subset — enough to be realistic
# without pretending to be exhaustive.
CURRENCIES = {
    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD",
    "CNY", "INR", "SEK", "NOK", "NZD", "SGD", "HKD",
}

TYPES = {"deposit", "withdrawal", "transfer"}
STATUSES = {"pending", "completed", "failed"}

ACCOUNT_RE = re.compile(r"^ACC-[A-Za-z0-9]{5}$")

# Which account fields are mandatory for each transaction type.
REQUIRED_ACCOUNTS = {
    "transfer": ("fromAccount", "toAccount"),
    "deposit": ("toAccount",),
    "withdrawal": ("fromAccount",),
}


def _is_real_number(value):
    # bool is a subclass of int — reject it explicitly so True/False aren't amounts.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _amount_errors(amount):
    if amount is None:
        return [{"field": "amount", "message": "Amount is required"}]
    if not _is_real_number(amount):
        return [{"field": "amount", "message": "Amount must be a number"}]
    if amount <= 0:
        return [{"field": "amount", "message": "Amount must be a positive number"}]
    try:
        exponent = Decimal(str(amount)).as_tuple().exponent
    except InvalidOperation:
        return [{"field": "amount", "message": "Amount must be a number"}]
    if isinstance(exponent, int) and exponent < -2:
        return [{"field": "amount",
                 "message": "Amount must have at most 2 decimal places"}]
    return []


def _account_errors(payload, txn_type):
    errors = []
    required = REQUIRED_ACCOUNTS.get(txn_type, ())
    for field in ("fromAccount", "toAccount"):
        value = payload.get(field)
        present = bool(value)
        if field in required and not present:
            errors.append({"field": field,
                           "message": f"{field} is required for a {txn_type}"})
        elif present and not ACCOUNT_RE.match(str(value)):
            errors.append({"field": field,
                           "message": f"{field} must match the format ACC-XXXXX"})
    return errors


def _currency_consistency_errors(payload, currency, get_account_currency):
    """Reject a transaction whose currency differs from an account's established one."""
    errors = []
    for field in ("fromAccount", "toAccount"):
        account = payload.get(field)
        if not account:
            continue
        existing = get_account_currency(account)
        if existing is not None and existing != currency:
            errors.append({
                "field": "currency",
                "message": (f"Account {account} already uses {existing}; "
                            f"transactions must use the same currency"),
            })
    return errors


def validate_create(payload, get_account_currency=lambda _account: None):
    """Return a list of ``{field, message}`` errors for a create payload.

    An empty list means the payload is valid. ``get_account_currency`` maps an
    account id to its already-established currency (or ``None`` if unseen).
    """
    if not isinstance(payload, dict):
        return [{"field": "body", "message": "Request body must be a JSON object"}]

    errors = []
    errors += _amount_errors(payload.get("amount"))

    currency = payload.get("currency")
    if currency is None:
        errors.append({"field": "currency", "message": "Currency is required"})
    elif currency not in CURRENCIES:
        errors.append({"field": "currency",
                       "message": "Invalid currency code (must be a valid ISO 4217 code)"})

    txn_type = payload.get("type")
    if txn_type is None:
        errors.append({"field": "type", "message": "Type is required"})
    elif txn_type not in TYPES:
        errors.append({"field": "type",
                       "message": "Type must be one of: deposit, withdrawal, transfer"})

    status = payload.get("status")
    if status is not None and status not in STATUSES:
        errors.append({"field": "status",
                       "message": "Status must be one of: pending, completed, failed"})

    errors += _account_errors(payload, txn_type)

    # Only check currency binding once the currency itself is valid.
    if currency in CURRENCIES:
        errors += _currency_consistency_errors(payload, currency, get_account_currency)

    return errors


def _parse_boundary(raw, *, end_of_day):
    """Parse a date filter value into a UTC-aware datetime.

    Accepts a date (``YYYY-MM-DD``) or a full ISO 8601 datetime. A bare date used
    as the ``to`` boundary expands to the end of that day so the range is inclusive.
    Raises ``ValueError`` on anything unparseable.
    """
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        raise ValueError(f"Invalid date '{raw}'; expected YYYY-MM-DD or ISO 8601")

    date_only = len(raw) == 10
    if date_only and end_of_day:
        parsed = datetime.combine(parsed.date(), time.max)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def parse_filters(args):
    """Validate and normalise query-string filters for GET /transactions.

    Returns a dict matching ``TransactionStore.filter``'s keyword arguments.
    Raises ``ValueError`` with a human-readable message on invalid input.
    """
    txn_type = args.get("type")
    if txn_type is not None and txn_type not in TYPES:
        raise ValueError("Type must be one of: deposit, withdrawal, transfer")

    dt_from = _parse_boundary(args["from"], end_of_day=False) if args.get("from") else None
    dt_to = _parse_boundary(args["to"], end_of_day=True) if args.get("to") else None

    return {
        "account": args.get("accountId"),
        "txn_type": txn_type,
        "dt_from": dt_from,
        "dt_to": dt_to,
    }
