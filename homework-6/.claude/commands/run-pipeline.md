Run the multi-agent banking pipeline end-to-end.

Steps:

1. Check that `sample-transactions.json` exists in this folder. If it is missing, stop and report it — there is nothing to process.
2. Clear the `shared/` directories so the run starts clean:
   ```bash
   find shared -name '*.json' -delete && rm -f shared/audit-log.jsonl
   ```
3. Run the pipeline:
   ```bash
   .venv/bin/python integrator.py
   ```
4. Show a summary of results from `shared/results/`. Read `shared/results/pipeline-summary.json` and report `total_transactions`, `counts_by_status`, `settled_totals_by_currency`, and `settled_total_base`.
5. Report any transaction that was rejected, held, or blocked, together with its `reason` and `reason_detail`, from the `exceptions` array of the summary.

Then verify the run against the contract, and say explicitly whether each check passed:

- Every transaction in `sample-transactions.json` has a matching `shared/results/<transaction_id>.json`.
- `shared/input/`, `shared/processing/`, and `shared/output/` hold no `.json` files afterwards. Anything left behind means a transaction was lost in flight.
- The outcomes match the table in `specification.md` section D: TXN001, TXN003, TXN004, and TXN008 settled; TXN002 and TXN005 held; TXN006 and TXN007 rejected. TXN004 settles to exactly `"540.00"` USD and the base total is exactly `"15239.99"`.
- `shared/audit-log.jsonl` contains one line per status change and no unmasked account number:
  ```bash
  grep -c 'ACC-[0-9]' shared/audit-log.jsonl   # must be 0
  ```

If any check fails, report which one and what the actual value was. Do not summarise a failed run as a success.
