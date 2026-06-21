"""In-memory storage for transactions and derived account views.

The store owns all mutable state. Balances and summaries are computed on demand
by scanning the transaction list — there is no separate account entity.
"""
from datetime import datetime


def _involves(txn, account):
    return txn["fromAccount"] == account or txn["toAccount"] == account


class TransactionStore:
    def __init__(self):
        self._txns = []

    # --- writes ---------------------------------------------------------
    def add(self, txn):
        self._txns.append(txn)
        return txn

    # --- reads ----------------------------------------------------------
    def all(self):
        return list(self._txns)

    def get(self, txn_id):
        return next((t for t in self._txns if t["id"] == txn_id), None)

    def filter(self, account=None, txn_type=None, dt_from=None, dt_to=None):
        results = []
        for txn in self._txns:
            if account is not None and not _involves(txn, account):
                continue
            if txn_type is not None and txn["type"] != txn_type:
                continue
            if dt_from is not None or dt_to is not None:
                ts = datetime.fromisoformat(txn["timestamp"])
                if dt_from is not None and ts < dt_from:
                    continue
                if dt_to is not None and ts > dt_to:
                    continue
            results.append(txn)
        return results

    def account_currency(self, account):
        """Currency bound to an account (its first transaction's), or None."""
        for txn in self._txns:
            if _involves(txn, account):
                return txn["currency"]
        return None

    def balance(self, account):
        total = 0.0
        for txn in self._txns:
            if txn["status"] != "completed":
                continue
            if txn["toAccount"] == account:
                total += txn["amount"]
            if txn["fromAccount"] == account:
                total -= txn["amount"]
        return {
            "accountId": account,
            "balance": round(total, 2),
            "currency": self.account_currency(account),
        }

    def summary(self, account):
        deposits = 0.0
        withdrawals = 0.0
        count = 0
        most_recent = None
        for txn in self._txns:
            if not _involves(txn, account):
                continue
            count += 1
            if most_recent is None or txn["timestamp"] > most_recent:
                most_recent = txn["timestamp"]
            if txn["status"] == "completed":
                if txn["toAccount"] == account:
                    deposits += txn["amount"]
                if txn["fromAccount"] == account:
                    withdrawals += txn["amount"]
        return {
            "accountId": account,
            "totalDeposits": round(deposits, 2),
            "totalWithdrawals": round(withdrawals, 2),
            "transactionCount": count,
            "mostRecentTimestamp": most_recent,
            "currency": self.account_currency(account),
        }
