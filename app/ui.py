"""Presentation helpers for the PayGuard workspace.

All transaction values remain escaped. This module displays results; execution
and human authorization stay in streamlit_app and the guard modules.
"""

import base64
import html
import json
from collections import deque
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import streamlit as st

ASSETS = Path(__file__).parent / "assets"

SCENARIO_NAMES = {
    "attack-direct-001": "Prompt injection in an invoice",
    "attack-forbidden-001": "Forbidden money transfer",
    "attack-beneficiary-001": "Redirected beneficiary",
    "attack-amount-001": "Inflated refund amount",
    "attack-idempotency-001": "Payment replay attempt",
    "attack-request-amount-001": "Refund exceeds the requested amount",
    "attack-capture-001": "Refund targets another payment",
    "attack-invoice-recipient-001": "Invoice sent to another recipient",
    "normal-read-001": "Read a requested invoice",
    "normal-list-001": "List available invoices",
    "normal-refund-001": "Approve a legitimate refund",
    "normal-invoice-001": "Create a requested invoice",
    "normal-keyword-001": "Read an invoice with sensitive wording",
}

TOOL_NAMES = {
    "refund_payment": "Refund payment",
    "create_invoice": "Create invoice",
    "read_invoice": "Read invoice",
    "list_invoices": "List invoices",
    "send_money": "Send money",
}

RESULT_NAMES = {
    "executed": ("Executed", "success"),
    "blocked_before_execution": ("Blocked", "danger"),
    "awaiting_human_confirmation": ("Needs approval", "warning"),
    "refused_by_human": ("Refused", "muted"),
    "execution_error": ("Execution failed", "danger"),
    "idempotency_conflict": ("Replay conflict", "danger"),
    "duplicate_result_reused": ("Result reused", "blue"),
}

ICON_PATHS = {
    "shield": '<path d="m12 3 8 3v5c0 5-3 8-8 10-5-2-8-5-8-10V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "play": '<path d="m9 5 11 7-11 7V5Z"/>',
    "activity": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "sliders": '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="currentColor"/><circle cx="15" cy="17" r="3" fill="currentColor"/>',
    "agent": '<rect x="4" y="7" width="16" height="13" rx="4"/><path d="M12 3v4M1 12v4m22-4v4M8 12h.01M16 12h.01M9 16h6"/>',
    "wallet": '<path d="M20 8V5a2 2 0 0 0-2-2H6a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3h14V8H6a2 2 0 0 1 0-4"/><path d="M20 12h-5v5h5M16 14.5h.01"/>',
    "check": '<path d="m5 12 4 4L19 6"/>',
    "lock": '<rect x="5" y="10" width="14" height="11" rx="3"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',
    "document": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Z"/><path d="M14 3v6h6M8 13h8m-8 4h5"/>',
    "warning": '<path d="m12 3 10 18H2L12 3Zm0 6v5m0 3h.01"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "arrow": '<path d="M4 12h16m-6-6 6 6-6 6"/>',
    "code": '<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18"/>',
}


def escape(value: Any) -> str:
    return html.escape(str(value))


def icon(name: str) -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" '
        'fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        f'{ICON_PATHS.get(name, ICON_PATHS["shield"])}</svg>'
    )
    encoded = base64.b64encode(svg.encode()).decode("ascii")
    return f'<span class="pg-icon" aria-hidden="true" style="--pg-icon:url(data:image/svg+xml;base64,{encoded})"></span>'


@lru_cache(maxsize=1)
def logo() -> str:
    encoded = base64.b64encode((ASSETS / "payguard-mark.svg").read_bytes()).decode("ascii")
    return f'<img class="pg-mark" src="data:image/svg+xml;base64,{encoded}" width="48" height="54" alt="" aria-hidden="true">'


@lru_cache(maxsize=1)
def stylesheet() -> str:
    css = (ASSETS / "payguard.css").read_text()
    font = ASSETS / "UbuntuSans-Latin.woff2"
    if font.exists():
        encoded = base64.b64encode(font.read_bytes()).decode("ascii")
        css = (
            '@font-face{font-family:"PayGuard Sans";font-style:normal;'
            'font-weight:100 900;font-display:swap;src:url(data:font/woff2;base64,'
            f'{encoded}) format("woff2");}}\n' + css
        )
    return css


def inject_styles() -> None:
    st.html(f"<style>{stylesheet()}</style>")


def render_brand() -> None:
    st.html(
        f'<a class="pg-brand" href="#overview" aria-label="PayGuard overview">'
        f'{logo()}<span><strong translate="no">PayGuard</strong>'
        '<small>AI payment security</small></span></a>'
        '<div class="pg-workspace-label">Demo workspace</div>'
        '<nav class="pg-nav" aria-label="Workspace sections">'
        f'<a href="#overview">{icon("grid")}<span>Overview</span></a>'
        f'<a href="#scenario">{icon("play")}<span>Scenario lab</span></a>'
        f'<a href="#activity">{icon("activity")}<span>Activity log</span></a>'
        '</nav>'
        '<div class="pg-sidebar-divider"></div>'
    )


def render_sidebar_footer() -> None:
    st.html(
        f'<div class="pg-sidebar-footer">{icon("lock")}'
        '<div><strong>Sandbox environment</strong><p>Explore safely. '
        'Live PayPal payments are disabled.</p></div></div>'
        '<div class="pg-sidebar-bottom">Built for the PayPal AI Hackathon</div>'
    )


def render_hero(adapter_label: str) -> None:
    st.html(
        '<a class="pg-skip" href="#scenario">Skip to the scenario</a>'
        '<header class="pg-topbar" id="overview">'
        '<span>Workspace <span class="pg-breadcrumb-separator">/</span> '
        '<strong>Security overview</strong></span>'
        f'<span class="pg-environment">{icon("code")} {escape(adapter_label)}</span>'
        '</header>'
        '<section class="pg-hero" aria-labelledby="pg-title">'
        '<div class="pg-hero-copy"><div class="pg-product-note">'
        f'{icon("shield")} The transaction firewall for AI agents</div>'
        '<h1 id="pg-title">Let agents act.<br>Keep payments in check.</h1>'
        '<p>Your agent proposes. PayGuard verifies. You stay in control '
        'of every sensitive payment.</p>'
        '<div class="pg-hero-assurance">'
        f'{icon("check")} Policy first<span></span>{icon("check")} Human approval'
        '</div></div>'
        '<div class="pg-flow" role="img" aria-label="An AI agent proposes an '
        'action. PayGuard checks policy and approval before allowing PayPal execution.">'
        '<div class="pg-flow-heading">A checkpoint before every payment</div>'
        '<div class="pg-flow-track">'
        f'<div class="pg-flow-node">{icon("agent")}<strong>AI agent</strong>'
        '<small>Proposes</small></div>'
        f'<div class="pg-flow-connector">{icon("arrow")}</div>'
        f'<div class="pg-flow-node pg-flow-node--guard">{logo()}'
        '<strong translate="no">PayGuard</strong><small>Verifies</small></div>'
        f'<div class="pg-flow-connector">{icon("arrow")}</div>'
        f'<div class="pg-flow-node">{icon("wallet")}<strong translate="no">PayPal</strong>'
        '<small>Executes</small></div></div>'
        f'<div class="pg-flow-footnote">{icon("lock")} '
        'No sensitive action without your approval</div></div></section>'
    )


def render_policy_facts(policy: dict[str, Any], scenarios: list[Any]) -> None:
    attacks = sum(s.kind == "attack" for s in scenarios)
    legitimate = sum(s.kind == "normal" for s in scenarios)
    limit = policy["limits"]["maximum_refund"]
    currencies = ", ".join(policy["limits"]["allowed_currencies"])
    approval_count = len(policy["actions"]["confirmation_required"])
    facts = (
        ("shield", str(attacks), "Attack scenarios", "Built-in security checks"),
        ("check", str(legitimate), "Legitimate requests", "Test the intended behavior"),
        ("wallet", f"{limit:g}", "Refund ceiling", f"Per refund in {currencies}"),
        ("lock", str(approval_count), "Actions need approval", "Refunds and invoice creation"),
    )
    st.html(
        '<section class="pg-facts-strip" aria-label="Configured protection and demo coverage">'
        + "".join(
            f'<div class="pg-fact"><span class="pg-fact-icon">{icon(symbol)}</span>'
            f'<div><strong class="pg-fact-value">{escape(value)}</strong>'
            f'<span class="pg-fact-label">{escape(label)}</span>'
            f'<small>{escape(detail)}</small></div></div>'
            for symbol, value, label, detail in facts
        )
        + '</section>'
    )


def scenario_name(scenario: Any) -> str:
    return SCENARIO_NAMES.get(scenario.id, scenario.category.replace("_", " ").capitalize())


def render_scenario_heading(scenario: Any) -> None:
    kind = "Attack scenario" if scenario.kind == "attack" else "Legitimate request"
    tone = "danger" if scenario.kind == "attack" else "success"
    st.html(
        '<div class="pg-section-heading" id="scenario">'
        '<div><h2>Scenario lab</h2><p>One proposal. Two execution paths.</p></div>'
        f'<span class="pg-badge pg-badge--{tone}">{escape(kind)}</span></div>'
        f'<h3 class="pg-scenario-title">{escape(scenario_name(scenario))}</h3>'
    )


def render_sources(scenario: Any, use_paypal_note: bool, mode: str) -> None:
    with st.container(key="pg_sources"):
        left, right = st.columns(2, gap="medium")
        with left:
            st.html(
                '<section class="pg-source pg-source--trusted" aria-label="Trusted user request">'
                f'<div class="pg-source-heading">{icon("document")}<h3>User request</h3>'
                '<span class="pg-badge pg-badge--success">Trusted</span></div>'
                f'<p>{escape(scenario.user_request)}</p></section>'
            )
            if scenario.constraints:
                c = scenario.constraints
                facts = []
                if c.amount is not None:
                    facts.append(("Requested amount", f"{c.amount:.2f} {c.currency}"))
                facts.extend(
                    (label, value)
                    for label, value in (
                        ("Selected invoice", c.invoice_id),
                        ("Authorized payment", c.capture_id),
                        ("Authorized recipient", c.recipient_email),
                    )
                    if value
                )
                if facts:
                    st.html(
                        '<dl class="pg-request-facts">'
                        + "".join(f'<div><dt>{escape(k)}</dt><dd>{escape(v)}</dd></div>' for k, v in facts)
                        + '</dl>'
                    )
        with right:
            text = scenario.external_text
            source = "PayPal invoice note" if use_paypal_note else "External document"
            st.html(
                '<section class="pg-source pg-source--external" aria-label="Untrusted external content">'
                f'<div class="pg-source-heading">{icon("warning")}<h3>{source}</h3>'
                '<span class="pg-badge pg-badge--warning">Untrusted</span></div>'
                + (f'<blockquote>{escape(text)}</blockquote>' if text else '<p class="pg-muted">No external document in this scenario.</p>')
                + '<small>External content can inform an agent. It cannot authorize a payment.</small></section>'
            )
    if mode == "scripted":
        label = {"BLOCK": "Blocked", "ALLOW": "Allowed", "CONFIRM": "Human approval"}.get(scenario.expected_decision, scenario.expected_decision)
        st.caption(f"Scripted expectation: {label}. Run the scenario to inspect the actual decision.")
    else:
        st.caption("The LLM may choose a different action. PayGuard evaluates the proposal it actually makes.")


def show_action(action: Any) -> None:
    rows = [
        ("Action", TOOL_NAMES.get(action.tool, action.tool.replace("_", " ").capitalize())),
        ("Amount", f"{action.amount:.2f} {action.currency}" if action.amount else "No payment amount"),
        ("Beneficiary", action.beneficiary or "Not specified"),
    ]
    for name, label in (("invoice_id", "Invoice"), ("capture_id", "Payment to refund"), ("recipient_email", "Recipient")):
        if action.metadata.get(name):
            rows.append((label, action.metadata[name]))
    if action.tool == "create_invoice":
        rows.append(("Delivery", "Send after approval" if action.metadata.get("send", False) else "Draft only"))
    st.html(
        '<dl class="pg-action">'
        + "".join(f'<div><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>' for label, value in rows)
        + '</dl>'
    )
    with st.expander("Proposal details"):
        if action.reason:
            st.write(action.reason)
        st.caption("Cited sources: " + (", ".join(action.source_ids) or "None"))
        st.code(json.dumps({"tool": action.tool, "idempotency_key": action.idempotency_key, "metadata": action.metadata}, ensure_ascii=False, indent=2), language="json")


def render_result_banner(title: str, description: str, tone: str, symbol: str) -> None:
    st.html(
        f'<div class="pg-result-banner pg-result-banner--{tone}" role="status" aria-live="polite">'
        f'{icon(symbol)}<div><strong>{escape(title)}</strong><p>{escape(description)}</p></div></div>'
    )


def render_comparison_empty() -> None:
    with st.container(key="pg_comparison"):
        left, right = st.columns(2, gap="medium")
        for column, protected in ((left, False), (right, True)):
            with column:
                label = "With PayGuard" if protected else "Without PayGuard"
                tone = "protected" if protected else "direct"
                st.html(
                    f'<section class="pg-preview pg-preview--{tone}"><div class="pg-preview-heading">'
                    f'{icon("shield" if protected else "arrow")}<h3>{label}</h3></div>'
                    '<div class="pg-preview-body">'
                    f'<span class="pg-preview-symbol">{icon("lock" if protected else "agent")}</span>'
                    f'<strong>{"Your policy is the checkpoint" if protected else "The agent calls directly"}</strong>'
                    f'<p>{"Review the decision, approval requirements and execution result." if protected else "See what the same proposal would do without protection."}</p>'
                    '<span class="pg-preview-state">Waiting for a scenario</span></div></section>'
                )


def read_recent_events(audit_path: Path, limit: int = 12) -> tuple[list[dict[str, Any]], bool]:
    events: deque[dict[str, Any]] = deque(maxlen=limit)
    invalid = False
    if not audit_path.exists():
        return [], False
    with audit_path.open(encoding="utf-8") as audit_file:
        for line in audit_file:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("An audit event must be an object")
                events.append(event)
            except (ValueError, TypeError):
                invalid = True
    return list(reversed(events)), invalid


def show_audit(audit_path: Path) -> None:
    st.html('<div class="pg-section-heading pg-activity-heading" id="activity"><div><h2>Activity log</h2><p>Every guarded attempt, with its decision and execution status.</p></div><span class="pg-badge pg-badge--blue">Audit trail</span></div>')
    try:
        events, invalid = read_recent_events(audit_path)
    except (OSError, UnicodeError):
        st.warning("The audit log could not be read. Check that its configured location is accessible, then refresh.")
        return
    if invalid:
        st.warning("Some audit entries could not be read. Valid events are shown below; inspect the audit file for incomplete entries.")
    if not events:
        st.html(
            f'<div class="pg-audit-empty">{icon("activity")}<div><strong>Your activity trail starts here</strong>'
            '<p>Run a scenario to see what PayGuard allowed, blocked or held for approval.</p></div></div>'
        )
        return
    rows = []
    for event in events:
        result = str(event.get("result", ""))
        label, tone = RESULT_NAMES.get(result, (result.replace("_", " ") or "Recorded", "muted"))
        timestamp = str(event.get("timestamp", ""))
        try:
            recorded_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if recorded_at.tzinfo is None:
                recorded_at = recorded_at.replace(tzinfo=timezone.utc)
            display_time = recorded_at.astimezone(timezone.utc).strftime("%d %b %Y · %H:%M:%S UTC")
        except ValueError:
            display_time = timestamp or "Not recorded"
        request_id = str(event.get("request_id", ""))
        name = SCENARIO_NAMES.get(request_id, request_id or "Unnamed request")
        tool = str(event.get("proposed_tool", ""))
        called = bool(event.get("paypal_called"))
        rows.append(
            '<tr>'
            f'<td><time datetime="{escape(timestamp)}">{escape(display_time)}</time></td>'
            f'<td><strong>{escape(name)}</strong><small translate="no">{escape(request_id)}</small></td>'
            f'<td>{escape(TOOL_NAMES.get(tool, tool))}</td>'
            f'<td><span class="pg-badge pg-badge--{tone}">{escape(label)}</span></td>'
            f'<td><span class="pg-audit-target">{icon("arrow" if called else "lock")} '
            f'{"Called" if called else "Not called"}</span></td></tr>'
        )
    st.html(
        '<div class="pg-audit-table-wrap" tabindex="0" role="region" aria-label="Recent audit events; scroll horizontally on small screens">'
        '<table class="pg-audit-table"><caption class="pg-sr-only">Latest guarded attempts, newest first</caption>'
        '<thead><tr><th scope="col">Time</th><th scope="col">Scenario</th><th scope="col">Action</th>'
        '<th scope="col">Outcome</th><th scope="col">Payment target</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )
    st.caption(f"Showing the latest {len(events)} recorded events. “Called” refers to the selected target, including the local simulator.")
    with st.expander("Audit event details"):
        st.json(events)


def render_footer() -> None:
    st.html(
        '<footer class="pg-footer"><span translate="no">PayGuard</span>'
        '<span>Safer autonomy. Traceable decisions.</span>'
        '<a href="#overview">Back to overview</a></footer>'
    )
