"""Maps logical field names (used in request/draft dicts throughout this app) to real Jira
field ids. IDs are resolved dynamically from the Jira instance's own field metadata
(JiraClient.resolve_fields, called once at process startup). "acceptance" additionally falls
back to cfg.acceptance_field (a hand-maintained .env override, kept for backward compatibility)
when dynamic resolution finds no match — every other field here is dynamic-only.
A field whose name isn't found in this Jira instance (and has no fallback) is simply omitted
from any payload; a missing field must never block ticket creation (same tolerance as this
codebase's other best-effort lookups, e.g. agent.py's planner)."""

from .adf import text_to_adf

# Long-text (ADF-rendered) fields, resolved by their exact Jira display name.
EXTRA_FIELDS = {
    "acceptance": "Acceptance Criteria",
    "feature_details": "Feature Details",
    "feature_challenges": "Feature Challenges",
    "nfrs": "Non-Functional Requirements",
    "analytics_requirement": "Analytics Requirement",
    "gtm_plan": "Go-To-Market Plan",
}

# Every display name JiraClient.resolve_fields() looks up at startup.
FIELD_NAMES = list(EXTRA_FIELDS.values()) + ["Start Date", "Sprint"]


def apply_extra_fields(cfg, fields: dict, values: dict) -> None:
    """Write every logical field present in `values` into `fields`, resolved to the real
    Jira field id via cfg.field_ids ("acceptance" falls back to cfg.acceptance_field if
    dynamic resolution has no match). A logical field absent from `values`, or whose display
    name wasn't found in this Jira instance (and has no fallback), is silently skipped —
    never an error."""
    for logical, display_name in EXTRA_FIELDS.items():
        if logical not in values or values[logical] is None:
            continue
        fid = cfg.field_ids.get(display_name)
        if not fid and logical == "acceptance":
            fid = getattr(cfg, "acceptance_field", "")
        if not fid:
            continue
        fields[fid] = text_to_adf(values[logical])
    if values.get("labels"):
        fields["labels"] = list(values["labels"])
    sprint_id = cfg.field_ids.get("Sprint")
    if sprint_id and values.get("sprint"):
        fields[sprint_id] = values["sprint"]
    if values.get("priority"):
        fields["priority"] = {"name": values["priority"]}
