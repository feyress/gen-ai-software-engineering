# research-notes.md — context7 queries made during code generation

These are the library lookups Meta-Agent 2 (code generation) made through the **context7** MCP server while implementing the pipeline. Each entry records what was searched for, the Context7-compatible library ID that came back, and the specific code that changed as a result.

The queries were issued against `@upstash/context7-mcp` over stdio. `scripts/context7_query.py` is the small JSON-RPC client used to make them reproducible from the terminal:

```bash
python3 scripts/context7_query.py resolve "fastmcp" "declaring tools and resources"
python3 scripts/context7_query.py docs "/prefecthq/fastmcp" "declare a tool and a resource"
```

The two tools context7 exposes are `resolve-library-id` (name to library ID) and `query-docs` (library ID plus a focused question to documentation excerpts).

---

## Query 1: FastMCP tool and resource declaration on the installed major version

- **Search**: `fastmcp` — "declaring tools and resources on a FastMCP server in Python", then "declare a tool and a resource with a custom URI on a FastMCP server, and run it over stdio"
- **context7 library ID**: `/prefecthq/fastmcp` (4041 snippets, benchmark 84.07, versions v3.2.0 and v3.2.4). Runners-up were `/llmstxt/gofastmcp_llms-full_txt` and `/websites/gofastmcp`.
- **Why this query was necessary**: `pip install "fastmcp>=2.0"` resolved to **fastmcp 3.4.5**, a major version above the 2.x used in homework 5. Decorator APIs are exactly the kind of thing that changes across a major, and guessing would have produced a server that imports but registers nothing.
- **What came back**:

```python
from fastmcp import FastMCP

mcp = FastMCP("MyServer")

@mcp.tool
def hello(name: str) -> str:
    return f"Hello, {name}!"

@mcp.resource("ui://my-app/view.html")
def chart_view() -> str:
    return "<html>...</html>"

if __name__ == "__main__":
    mcp.run()  # Uses STDIO transport by default
```

- **Applied**: In `mcp/server.py`, `get_transaction_status` and `list_pipeline_results` are declared with the bare `@mcp.tool` decorator (no call parentheses — still valid in 3.x), the run summary is exposed as `@mcp.resource("pipeline://summary")` with a custom non-HTTP URI scheme, and the server is started with a plain `mcp.run()` under an `if __name__ == "__main__"` guard so stdio is used and the module stays importable by tests. Confirming that `mcp.run()` still defaults to stdio is what let `.mcp.json` stay as a plain `command` plus `args` entry with no transport configuration.

---

## Query 2: Decimal quantization for monetary values

- **Search**: `python decimal` — "Decimal quantize with ROUND_HALF_UP for monetary values", then "quantize a Decimal to two places with ROUND_HALF_UP for currency, and why float must not be used for money"
- **context7 library ID**: `/python/cpython` (36851 snippets, benchmark 79.64). The excerpts came from `Doc/library/decimal.md`.
- **What came back**, from the standard library's own currency guidance:

```pycon
>>> TWOPLACES = Decimal(10) ** -2       # same as Decimal('0.01')
>>> Decimal('3.214').quantize(TWOPLACES)
Decimal('3.21')
>>> Decimal('7.325').quantize(Decimal('.01'), rounding=ROUND_DOWN)
Decimal('7.32')
```

and the float trap, which is the concrete argument behind the project's never-`float` rule:

```pycon
>>> Decimal(1.1)
Decimal('1.100000000000000088817841970012523233890533447265625')
```

- **Applied**: `agents/envelope.py` derives the quantization exponent from the currency's minor unit with the documented `Decimal(10) ** -places` idiom rather than hard-coding `Decimal("0.01")`, which is what lets the same helper serve two-place currencies (USD, EUR, GBP) and zero-place JPY from the `MINOR_UNITS` table. `agents/settlement_processor.py` quantizes exactly once, at settlement, passing `rounding=ROUND_HALF_UP` explicitly instead of relying on the context default of `ROUND_HALF_EVEN`. The `Decimal(1.1)` example is why every amount is parsed from its JSON **string** form: `Decimal("1500.00")`, never `Decimal(1500.00)`.

---

## Query 3: Isolating filesystem tests with `tmp_path`

- **Search**: `pytest` — "isolate filesystem tests with the tmp_path fixture", then "tmp_path fixture to isolate tests that read and write files"
- **context7 library ID**: `/pytest-dev/pytest` (4575 snippets, benchmark 81.3, version 9.0.0). Runner-up `/websites/pytest_en_stable`.
- **What came back**:

```python
def test_with_tmp_path(tmp_path):
    assert tmp_path.exists()
    file_path = tmp_path / "my_file.txt"
    file_path.write_text("Hello")
    assert file_path.read_text() == "Hello"
```

plus `tmp_path_factory` for session-scoped directories and the `monkeypatch.chdir(tmp_path)` pattern for code that assumes a working directory.

- **Applied**: This query shaped an interface decision in the pipeline, not just the tests. Every function that touches the filesystem — `mailbox.ensure_directories`, `audit.record_event`, `results_store.list_results`, `integrator.run` — takes an explicit `root: Path` parameter instead of resolving `shared/` from the module location or the working directory. That is what makes `root=tmp_path` sufficient for isolation, so no test needs `monkeypatch.chdir` and no test can reach the real `shared/` tree. The `pytest.ini` equivalent in `pyproject.toml` sets `pythonpath = ["."]` so `tests/` can import `agents` and `integrator` without an installed package.
