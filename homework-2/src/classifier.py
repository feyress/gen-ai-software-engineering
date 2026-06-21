"""Rule-based auto-classification of support tickets (Task 2).

Pure and deterministic: ``classify`` looks for keyword signals in the ticket's
subject + description and returns a category, priority, a confidence score in
[0, 1], a human-readable reasoning string, and the keywords it matched. No
network or LLM calls — every decision is reproducible and unit-testable.
"""

# Keyword signals per category. Order matters only for tie-breaking, which we
# resolve by (match count, this declaration order).
CATEGORY_KEYWORDS = {
    "account_access": [
        "login", "log in", "log-in", "sign in", "password", "passcode",
        "2fa", "two-factor", "two factor", "mfa", "locked out", "can't access",
        "cannot access", "account access", "reset password", "credentials",
        "authentication", "verify", "verification code",
    ],
    "billing_question": [
        "billing", "payment", "invoice", "refund", "charge", "charged",
        "subscription", "credit card", "receipt", "pricing", "overcharged",
        "transaction", "renewal", "plan", "discount", "coupon",
    ],
    "bug_report": [
        "bug", "defect", "reproduce", "reproduction", "steps to reproduce",
        "regression", "broken", "doesn't work", "does not work", "not working",
        "incorrect result", "unexpected result",
    ],
    "technical_issue": [
        "error", "crash", "crashed", "exception", "timeout", "500",
        "stack trace", "fails", "failure", "freeze", "frozen", "hang",
        "slow", "lag", "loading", "blank screen", "white screen",
    ],
    "feature_request": [
        "feature request", "feature", "enhancement", "suggestion", "suggest",
        "would be nice", "please add", "could you add", "improvement",
        "wish", "request to add", "it would help",
    ],
}

# Priority signals. Each tier maps to keyword phrases; first matching tier
# (urgent > high > low) wins, otherwise medium.
PRIORITY_KEYWORDS = {
    "urgent": ["can't access", "cannot access", "critical", "production down",
               "outage", "security", "data loss", "breach", "down for everyone"],
    "high": ["important", "blocking", "blocker", "asap", "as soon as possible"],
    "low": ["minor", "cosmetic", "suggestion", "typo", "nitpick", "whenever you can"],
}

# Categories whose category signal also nudges priority a notch (used only
# in reasoning text, not the priority decision itself).
_DEFAULT_CATEGORY = "other"
_DEFAULT_PRIORITY = "medium"


def _find_keywords(text, keywords):
    """Return the subset of ``keywords`` that appear in ``text`` (lowercased)."""
    return [kw for kw in keywords if kw in text]


def _pick_category(text):
    """Return (category, matched_keywords). Highest match count wins."""
    best_category = _DEFAULT_CATEGORY
    best_matches = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        matches = _find_keywords(text, keywords)
        if len(matches) > len(best_matches):
            best_category = category
            best_matches = matches
    return best_category, best_matches


def _pick_priority(text):
    """Return (priority, matched_keywords) using the urgent>high>low ladder."""
    for priority in ("urgent", "high", "low"):
        matches = _find_keywords(text, PRIORITY_KEYWORDS[priority])
        if matches:
            return priority, matches
    return _DEFAULT_PRIORITY, []


def _confidence(category, category_matches, priority_matches):
    """Map keyword evidence to a confidence score in [0, 1].

    More distinct category keyword hits => higher confidence. A bare "other"
    classification (no signal at all) gets a deliberately low score.
    """
    if category == _DEFAULT_CATEGORY and not category_matches:
        # No category signal — low confidence regardless of priority hits.
        return round(0.2 + 0.05 * len(priority_matches), 2)
    # 0.5 baseline for one hit, +0.15 per extra hit, capped at 0.95.
    score = 0.5 + 0.15 * (len(category_matches) - 1)
    if priority_matches:
        score += 0.05
    return round(min(score, 0.95), 2)


def classify(subject, description):
    """Classify a ticket from its subject and description.

    Returns a dict: ``category``, ``priority``, ``confidence`` (0-1),
    ``reasoning`` (str), and ``keywords`` (sorted, de-duplicated list).
    """
    text = f"{subject or ''} {description or ''}".lower()

    category, category_matches = _pick_category(text)
    priority, priority_matches = _pick_priority(text)
    confidence = _confidence(category, category_matches, priority_matches)

    all_keywords = sorted(set(category_matches) | set(priority_matches))

    if category_matches:
        cat_reason = (
            f"matched {len(category_matches)} '{category}' keyword(s): "
            f"{', '.join(category_matches)}"
        )
    else:
        cat_reason = "no category keywords matched; defaulted to 'other'"
    if priority_matches:
        pri_reason = (
            f"priority '{priority}' from keyword(s): {', '.join(priority_matches)}"
        )
    else:
        pri_reason = "priority defaulted to 'medium' (no priority keywords)"

    return {
        "category": category,
        "priority": priority,
        "confidence": confidence,
        "reasoning": f"{cat_reason}; {pri_reason}.",
        "keywords": all_keywords,
    }
