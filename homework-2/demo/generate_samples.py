"""Generate realistic sample ticket files: CSV (50), JSON (20), XML (30).

Run from the homework-2 directory:  python demo/generate_samples.py
The output files are committed, so you only need this if you want to regenerate.
"""
import csv
import json
import os
import random
import xml.etree.ElementTree as ET
from xml.dom import minidom

HERE = os.path.dirname(os.path.abspath(__file__))

# (subject, description) templates grouped by the category they should imply.
TEMPLATES = {
    "account_access": [
        ("Cannot log in to my account", "I forgot my password and the 2FA reset email never arrives. I am locked out."),
        ("Locked out after password reset", "I reset my password but now cannot access my account at all. Please help."),
        ("Two-factor authentication broken", "My authenticator app stopped working and I cannot verify my login anymore."),
    ],
    "billing_question": [
        ("Charged twice on my invoice", "My last invoice shows a double charge and I would like a refund for the duplicate payment."),
        ("Question about my subscription", "I do not understand the pricing on my latest invoice and need clarification on the charge."),
        ("Refund not received", "I requested a refund last week but nothing has appeared on my credit card yet."),
    ],
    "technical_issue": [
        ("App crashes on startup", "The application crashes with a 500 error and a stack trace every time I open it."),
        ("Dashboard is very slow", "The dashboard takes forever to load and sometimes shows a blank white screen."),
        ("Export times out", "Whenever I export a report the request times out and the app freezes."),
    ],
    "bug_report": [
        ("Bug: totals are incorrect", "Steps to reproduce: open the report, the totals do not work and show the wrong number."),
        ("Defect in CSV export", "There is a defect: the CSV export is broken and produces incorrect results every time."),
        ("Regression after update", "After the latest update a feature that worked before is now broken; here are reproduction steps."),
    ],
    "feature_request": [
        ("Feature request: dark mode", "It would be nice if you could add a dark mode theme to the dashboard. A great enhancement."),
        ("Please add CSV import", "Could you add a bulk CSV import feature? This improvement would help our team a lot."),
        ("Suggestion for keyboard shortcuts", "A suggestion: it would help to have keyboard shortcuts for common actions."),
    ],
    "other": [
        ("General feedback", "Just wanted to say thanks to the support team for being so helpful and kind."),
        ("How do I get started", "I am new here and have a general question about how the dashboard layout works."),
    ],
}

# Priority-flavoured suffixes occasionally appended to vary urgency signals.
PRIORITY_SUFFIX = {
    "urgent": " This is critical and production is down for our whole team.",
    "high": " This is blocking our work and is important, please fix asap.",
    "low": " This is only a minor cosmetic issue, no rush whenever you can.",
    "medium": "",
}

SOURCES = ["web_form", "email", "api", "chat", "phone"]
DEVICES = ["desktop", "mobile", "tablet"]
FIRST = ["Alex", "Sam", "Jordan", "Taylor", "Casey", "Morgan", "Riley", "Jamie",
         "Avery", "Quinn", "Drew", "Robin", "Skyler", "Reese", "Cameron"]
LAST = ["Smith", "Johnson", "Lee", "Brown", "Garcia", "Miller", "Davis",
        "Martinez", "Lopez", "Wilson", "Clark", "Walsh", "Quinn", "Park"]


def make_ticket(i, rng):
    category = rng.choice(list(TEMPLATES.keys()))
    subject, description = rng.choice(TEMPLATES[category])
    priority = rng.choice(["urgent", "high", "medium", "low", "medium"])
    description += PRIORITY_SUFFIX[priority]
    first, last = rng.choice(FIRST), rng.choice(LAST)
    return {
        "customer_id": f"CUST-{1000 + i}",
        "customer_email": f"{first.lower()}.{last.lower()}{i}@example.com",
        "customer_name": f"{first} {last}",
        "subject": subject,
        "description": description,
        "tags": rng.sample(["login", "billing", "ui", "urgent", "mobile", "export"],
                           k=rng.randint(0, 2)),
        "metadata": {"source": rng.choice(SOURCES),
                     "device_type": rng.choice(DEVICES)},
    }


def write_csv(path, tickets):
    fields = ["customer_id", "customer_email", "customer_name", "subject",
              "description", "tags", "metadata_source", "metadata_device_type"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for t in tickets:
            writer.writerow({
                "customer_id": t["customer_id"],
                "customer_email": t["customer_email"],
                "customer_name": t["customer_name"],
                "subject": t["subject"],
                "description": t["description"],
                "tags": "|".join(t["tags"]),
                "metadata_source": t["metadata"]["source"],
                "metadata_device_type": t["metadata"]["device_type"],
            })


def write_json(path, tickets):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(tickets, fh, indent=2)
        fh.write("\n")


def write_xml(path, tickets):
    root = ET.Element("tickets")
    for t in tickets:
        te = ET.SubElement(root, "ticket")
        for key in ("customer_id", "customer_email", "customer_name",
                    "subject", "description"):
            ET.SubElement(te, key).text = t[key]
        tags = ET.SubElement(te, "tags")
        for tag in t["tags"]:
            ET.SubElement(tags, "tag").text = tag
        meta = ET.SubElement(te, "metadata")
        ET.SubElement(meta, "source").text = t["metadata"]["source"]
        ET.SubElement(meta, "device_type").text = t["metadata"]["device_type"]
    pretty = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(pretty)


def main():
    rng = random.Random(42)  # deterministic output
    tickets = [make_ticket(i, rng) for i in range(50)]
    write_csv(os.path.join(HERE, "sample_tickets.csv"), tickets[:50])
    write_json(os.path.join(HERE, "sample_tickets.json"), tickets[:20])
    write_xml(os.path.join(HERE, "sample_tickets.xml"), tickets[:30])
    print("Wrote sample_tickets.csv (50), .json (20), .xml (30)")


if __name__ == "__main__":
    main()
