Validate all transactions in `sample-transactions.json` without processing them.

Steps:

1. Run the validator in dry-run mode:
   ```bash
   .venv/bin/python scripts/validate_transactions.py --dry-run
   ```
   This calls `agents/transaction_validator.process_message` on every record in isolation. It writes no files, moves nothing through `shared/`, and starts no other agent. The exit code is 1 when any record is invalid.
2. Report: total count, valid count, invalid count, and the reason for every rejection.
3. Show the table of results, one row per transaction, with the transaction id, the verdict, the amount and currency, and the rejection reason where there is one.

Expected for the supplied sample data: 8 total, 6 valid, 2 invalid — TXN006 rejected as `invalid_currency` because `XYZ` is not in the ISO 4217 allow-list, and TXN007 rejected as `non_positive_amount` because `-100.00` is not greater than zero. Flag it if the numbers differ, since that means either the data or the validator changed.

To validate a different file, pass `--source path/to/file.json`.

Note: the dry run only exercises validation. It says nothing about fraud risk, compliance, or settlement — use `/run-pipeline` for the full picture.
