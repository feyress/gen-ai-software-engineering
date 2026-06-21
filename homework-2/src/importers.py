"""Bulk import parsers for CSV, JSON and XML ticket files (Task 1).

Each parser turns raw file text into a list of *create-payload* dicts shaped
like the JSON body of ``POST /tickets``. Whole-file problems (invalid JSON,
broken XML, unknown format) raise ``ImportError`` with a meaningful message;
per-record validation is handled by the caller via ``validators.validate_create``.
"""
import csv
import io
import json
import xml.etree.ElementTree as ET

SUPPORTED_FORMATS = ("csv", "json", "xml")

# Flat column / element names that belong inside the nested ``metadata`` object.
_META_FIELDS = ("source", "browser", "device_type")
# Character that separates multiple tags inside a single CSV cell / XML text.
_TAG_SEPARATOR = "|"


class ImportError_(ValueError):
    """Raised when an entire file cannot be parsed (not a per-record issue)."""


def _split_tags(raw):
    if raw is None or raw == "":
        return []
    return [t.strip() for t in str(raw).split(_TAG_SEPARATOR) if t.strip()]


def _normalize_flat(row):
    """Turn a flat row (CSV/loosely-shaped JSON) into the nested payload shape.

    Recognises ``metadata_<field>`` and ``tags`` columns. Empty strings are
    dropped so that "absent" and "blank" behave the same for validation.
    """
    payload = {}
    metadata = {}
    for key, value in row.items():
        if key is None:
            continue
        key = key.strip()
        if isinstance(value, str):
            value = value.strip()
        if value in (None, ""):
            continue
        if key == "tags":
            payload["tags"] = _split_tags(value)
        elif key.startswith("metadata_") and key[len("metadata_"):] in _META_FIELDS:
            metadata[key[len("metadata_"):]] = value
        else:
            payload[key] = value
    if metadata:
        payload["metadata"] = metadata
    return payload


def parse_csv(text):
    """Parse CSV text into a list of payload dicts. Blank rows are skipped."""
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ImportError_("CSV file is empty or has no header row")
    records = []
    for row in reader:
        # Skip fully-empty rows produced by trailing newlines.
        if not any((v or "").strip() for v in row.values()):
            continue
        records.append(_normalize_flat(row))
    return records


def parse_json(text):
    """Parse JSON text into a list of payload dicts.

    Accepts either a top-level array or an object with a ``tickets`` array.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ImportError_(f"Invalid JSON: {exc.msg} (line {exc.lineno})")
    if isinstance(data, dict) and "tickets" in data:
        data = data["tickets"]
    if not isinstance(data, list):
        raise ImportError_("JSON must be an array of tickets or {'tickets': [...]}")
    records = []
    for item in data:
        if not isinstance(item, dict):
            raise ImportError_("Each ticket in the JSON array must be an object")
        records.append(_normalize_flat(item))
    return records


def _xml_ticket_to_payload(elem):
    payload = {}
    metadata = {}
    for child in elem:
        tag = child.tag
        if tag == "metadata":
            for meta_child in child:
                if meta_child.tag in _META_FIELDS and (meta_child.text or "").strip():
                    metadata[meta_child.tag] = meta_child.text.strip()
        elif tag == "tags":
            tags = [t.text.strip() for t in child if (t.text or "").strip()]
            if tags:
                payload["tags"] = tags
        else:
            text = (child.text or "").strip()
            if text:
                payload[tag] = text
    if metadata:
        payload["metadata"] = metadata
    return payload


def parse_xml(text):
    """Parse XML text into a list of payload dicts.

    Expects a root element containing ``<ticket>`` children.
    """
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ImportError_(f"Invalid XML: {exc}")
    tickets = root.findall("ticket") or (
        [root] if root.tag == "ticket" else []
    )
    if not tickets:
        raise ImportError_("No <ticket> elements found in XML")
    return [_xml_ticket_to_payload(t) for t in tickets]


_PARSERS = {"csv": parse_csv, "json": parse_json, "xml": parse_xml}


def detect_format(filename=None, explicit=None):
    """Resolve the import format from an explicit value or a file extension."""
    if explicit:
        fmt = explicit.lower().lstrip(".")
        if fmt not in SUPPORTED_FORMATS:
            raise ImportError_(f"Unsupported format: {explicit}")
        return fmt
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[1].lower()
        if ext in SUPPORTED_FORMATS:
            return ext
    raise ImportError_(
        "Could not determine import format; pass ?format=csv|json|xml "
        "or upload a .csv/.json/.xml file"
    )


def parse(fmt, text):
    """Dispatch to the parser for ``fmt``. Raises ImportError_ on bad format."""
    if fmt not in _PARSERS:
        raise ImportError_(f"Unsupported format: {fmt}")
    return _PARSERS[fmt](text)
