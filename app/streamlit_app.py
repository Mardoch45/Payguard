"""PayGuard demonstration interface.

Run from the `payguard/` directory:

    streamlit run app/streamlit_app.py
"""

import html
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapters.fake import FakePayPalAdapter  # noqa: E402
from adapters.paypal import PayPalClient, PayPalSandboxAdapter  # noqa: E402
from agent.llm import AgentError, LLMAgent  # noqa: E402
from agent.models import AgentProposal, Document  # noqa: E402
from agent.scripted import ScriptedAgent  # noqa: E402
from app.demo import run_with_protection, run_without_protection  # noqa: E402
from app.scenarios import Scenario, load_all_scenarios, prepare_sandbox_scenario  # noqa: E402
from guard.execution import record_human_refusal  # noqa: E402
from guard.idempotency import IdempotencyRegistry  # noqa: E402
from guard.models import Decision, UserRequest  # noqa: E402
from guard.policy import load_policy  # noqa: E402
from guard.provenance import SourceType  # noqa: E402
from guard.settings import load_settings  # noqa: E402

st.set_page_config(
    page_title="PayGuard — Transaction Firewall for AI Agents",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DECISION_ALERTS = {
    Decision.ALLOW: st.success,
    Decision.CONFIRM: st.warning,
    Decision.BLOCK: st.error,
}

DECISION_VERBS = {
    Decision.ALLOW: "ALLOWED",
    Decision.CONFIRM: "CONFIRMATION REQUIRED",
    Decision.BLOCK: "BLOCKED",
}

RESULT_COLORS = {
    "executed": "pg-res-executed",
    "blocked_before_execution": "pg-res-blocked",
    "awaiting_human_confirmation": "pg-res-pending",
    "refused_by_human": "pg-res-pending",
    "execution_error": "pg-res-blocked",
    "idempotency_conflict": "pg-res-blocked",
    "duplicate_result_reused": "pg-res-duplicate",
}

PAGE_CSS = """
<style>
.stApp {
    background:
        radial-gradient(1100px 520px at 18% -8%, rgba(0, 120, 200, 0.14), transparent 60%),
        radial-gradient(900px 420px at 95% 0%, rgba(61, 214, 140, 0.05), transparent 55%),
        #0A0F1E;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"], footer, #MainMenu { display: none; }
.block-container { padding-top: 1.4rem; max-width: 1500px; }

/* ---------- hero ---------- */
.pg-hero {
    padding: 1.15rem 1.5rem;
    border: 1px solid rgba(148, 163, 184, 0.15);
    border-radius: 16px;
    background:
        linear-gradient(135deg, rgba(0, 130, 210, 0.16), rgba(10, 15, 30, 0.10) 50%),
        rgba(17, 26, 48, 0.65);
}
.pg-hero-title {
    display: flex; align-items: center; gap: 0.75rem;
    font-size: 2.05rem; font-weight: 800; letter-spacing: -0.02em; color: #F2F5FB;
}
.pg-shield { filter: drop-shadow(0 0 16px rgba(0, 160, 233, 0.55)); }
.pg-hero-sub { color: #9FB0CE; margin-top: 0.4rem; font-size: 0.97rem; }
.pg-hero-sub strong { color: #C9D6EC; font-weight: 650; }
.pg-chips { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.9rem; }
.pg-chip {
    font-size: 0.7rem; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase;
    padding: 0.3rem 0.75rem; border-radius: 999px; color: #7FC8F0;
    border: 1px solid rgba(0, 160, 233, 0.35); background: rgba(0, 160, 233, 0.08);
}
.pg-chip--green {
    color: #6FE3A8; border-color: rgba(61, 214, 140, 0.35); background: rgba(61, 214, 140, 0.08);
}
.pg-chip--amber {
    color: #F5B54A; border-color: rgba(245, 181, 74, 0.35); background: rgba(245, 181, 74, 0.08);
}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D1526 0%, #0A0F1E 100%);
    border-right: 1px solid rgba(148, 163, 184, 0.12);
    width: 312px; min-width: 312px;
}
.pg-label {
    font-size: 0.7rem; font-weight: 800; letter-spacing: 0.16em;
    text-transform: uppercase; color: #8FA3C8; margin: 0.3rem 0 0.35rem;
}
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] [data-testid="stRadio"] label {
    background: rgba(148, 163, 184, 0.06);
    border: 1px solid transparent; border-radius: 9px;
    padding: 0.32rem 0.6rem; transition: border-color 0.15s ease;
}
[data-testid="stSidebar"] .stRadio label:hover {
    border-color: rgba(0, 160, 233, 0.35);
}
.pg-quote {
    border-left: 2px solid rgba(0, 160, 233, 0.5);
    padding: 0.35rem 0.8rem; margin: 0.15rem 0 0.4rem;
    color: #D7E1F2; font-style: italic;
}
.pg-untrusted {
    border: 1px dashed rgba(229, 72, 77, 0.55);
    background: rgba(229, 72, 77, 0.07);
    border-radius: 10px; padding: 0.55rem 0.8rem; margin: 0.15rem 0 0.5rem;
    color: #F3C2C3;
}
.pg-facts { color: #C9D6EC; font-size: 0.88rem; }
.pg-facts strong { color: #8FA3C8; font-weight: 700; }

/* ---------- cards ---------- */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 14px;
    border: 1px solid rgba(148, 163, 184, 0.16);
    background: linear-gradient(180deg, rgba(18, 26, 48, 0.72), rgba(13, 20, 38, 0.55));
}
[data-testid="stVerticalBlockBorderWrapper"] h2 {
    font-size: 1.02rem; font-weight: 750; letter-spacing: 0.01em; color: #F2F5FB;
}

/* ---------- alerts & buttons ---------- */
[data-testid="stAlert"] { border-radius: 10px; }
.stElementContainer:has(> [data-testid="stButton"]) { width: 100%; }
[data-testid="stButton"] { width: 100%; }
[data-testid="stButton"] .stElementContainer { width: 100%; }
[data-testid="stButton"] button,
.stButton > button,
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-secondary"] {
    width: 100%; border-radius: 10px; font-weight: 650;
    transition: transform 0.12s ease, box-shadow 0.12s ease;
}
.stButton > button[kind="primary"],
[data-testid="stBaseButton-primary"] {
    border: 1px solid rgba(0, 160, 233, 0.55) !important;
    box-shadow: 0 6px 18px rgba(0, 145, 220, 0.22);
}
[data-testid="stButton"] button:hover,
.stButton > button:hover,
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-secondary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 22px rgba(0, 145, 220, 0.3);
}

/* ---------- action table ---------- */
.pg-action { width: 100%; border-collapse: collapse; font-size: 0.87rem; }
.pg-action td {
    padding: 0.36rem 0.5rem; border-bottom: 1px solid rgba(148, 163, 184, 0.1);
    vertical-align: top; color: #E2E9F5;
}
.pg-action td:first-child {
    color: #8FA3C8; font-weight: 700; width: 11rem;
    text-transform: uppercase; font-size: 0.67rem; letter-spacing: 0.11em; padding-top: 0.5rem;
}
.pg-action tr:last-child td { border-bottom: none; }
.pg-code {
    font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
    background: rgba(148, 163, 184, 0.1); border: 1px solid rgba(148, 163, 184, 0.16);
    border-radius: 6px; padding: 0.04rem 0.4rem; font-size: 0.78rem; color: #BCD3F0;
}
.pg-risk {
    display: inline-block; margin: 0.15rem 0.3rem 0.15rem 0; padding: 0.13rem 0.65rem;
    border-radius: 999px; font-size: 0.72rem; font-weight: 700;
    color: #F5B54A; background: rgba(245, 181, 74, 0.1); border: 1px solid rgba(245, 181, 74, 0.4);
}

/* ---------- audit terminal ---------- */
.pg-terminal {
    background: #060A13; border: 1px solid rgba(148, 163, 184, 0.17);
    border-radius: 12px; padding: 0.95rem 1.1rem 1.05rem;
    font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
    font-size: 0.8rem; overflow-x: auto;
}
.pg-term-head {
    display: flex; align-items: center; gap: 0.6rem;
    color: #8FA3C8; font-size: 0.67rem; letter-spacing: 0.17em;
    text-transform: uppercase; font-weight: 800; margin-bottom: 0.65rem;
}
.pg-term-path { color: #5D6F92; letter-spacing: 0.04em; text-transform: none; font-weight: 600; }
.pg-dot {
    width: 0.55rem; height: 0.55rem; border-radius: 50%; background: #3DD68C;
    box-shadow: 0 0 10px rgba(61, 214, 140, 0.85); animation: pg-pulse 2.2s infinite;
}
@keyframes pg-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
.pg-term-row {
    display: grid;
    grid-template-columns: 4.8rem 11.5rem 9rem 6rem 13.5rem 13.5rem 7rem;
    gap: 0.7rem; padding: 0.34rem 0; color: #C7D2E8;
    border-bottom: 1px dashed rgba(148, 163, 184, 0.09); min-width: 66rem;
}
.pg-term-row span {
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.pg-term-row:last-child { border-bottom: none; }
.pg-term-row--head {
    color: #6E7FA3; text-transform: uppercase; font-size: 0.63rem; letter-spacing: 0.13em;
    border-bottom: 1px solid rgba(148, 163, 184, 0.2); font-weight: 800;
}
.pg-res { font-weight: 700; }
.pg-res-executed { color: #3DD68C; }
.pg-res-blocked { color: #FF6B6E; }
.pg-res-pending { color: #F5B54A; }
.pg-res-duplicate { color: #5AB8F0; }
.pg-called-yes { color: #3DD68C; font-weight: 700; }
.pg-called-no { color: #5A6C8F; font-weight: 700; }
.pg-empty { color: #6E7FA3; font-style: italic; }
</style>
"""


def inject_css() -> None:
    st.markdown(PAGE_CSS, unsafe_allow_html=True)


def render_hero() -> None:
    chips = "".join(
        f'<span class="pg-chip{cls}">{text}</span>'
        for text, cls in (
            ("Deny by default", ""),
            ("Human confirmation", ""),
            ("Idempotent execution", ""),
            ("JSONL audit trail", ""),
            ("PayPal Sandbox only", " pg-chip--green"),
        )
    )
    st.markdown(
        f"""
        <div class="pg-hero">
            <div class="pg-hero-title"><span class="pg-shield">🛡️</span> PayGuard</div>
            <div class="pg-hero-sub">
                The transaction firewall for AI agents. Every proposal is
                <strong>evaluated against policy</strong> before PayPal is touched:
                risky operations <strong>wait for a human</strong>, replays are
                <strong>blocked</strong>, and every attempt is <strong>audited</strong>.
            </div>
            <div class="pg-chips">{chips}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def pg_label(text: str) -> str:
    return f'<div class="pg-label">{html.escape(text)}</div>'


def pg_section(text: str) -> None:
    st.markdown(pg_label(text), unsafe_allow_html=True)


@st.cache_resource
def get_policy() -> dict[str, Any]:
    return load_policy(PROJECT_ROOT / "policies" / "policy.yaml")


@st.cache_resource
def get_adapter(name: str) -> Any:
    settings = load_settings()
    if name == "paypal":
        return PayPalSandboxAdapter(
            PayPalClient(
                settings.paypal_client_id,
                settings.paypal_client_secret,
                settings.paypal_base_url,
            )
        )
    return FakePayPalAdapter()


def get_registry(target: str) -> IdempotencyRegistry:
    if "registries_by_target" not in st.session_state:
        st.session_state.registries_by_target = {}
    registries = st.session_state.registries_by_target
    if target not in registries:
        registries[target] = IdempotencyRegistry()
    return registries[target]


def scenario_documents(scenario: Scenario) -> list[Document]:
    documents = [
        Document("consigne-utilisateur", SourceType.USER, scenario.user_request)
    ]
    if scenario.external_text:
        untrusted = scenario.provenance.get("untrusted_source_ids") or [
            f"{scenario.id}-note"
        ]
        documents.append(
            Document(str(untrusted[0]), SourceType.THIRD_PARTY, scenario.external_text)
        )
    return documents


def build_proposal(
    scenario: Scenario,
    mode: str,
    settings: Any,
) -> AgentProposal:
    if mode == "scripted":
        return ScriptedAgent.from_scenario(
            {
                "id": scenario.id,
                "user_request": scenario.user_request,
                "requested_actions": list(scenario.requested_actions),
                "external_text": scenario.external_text,
                "proposed_action": scenario.proposed_action,
                "provenance": scenario.provenance,
                "constraints": asdict(scenario.constraints) if scenario.constraints else None,
            }
        ).propose(
            UserRequest(
                text=scenario.user_request,
                requested_actions=frozenset(scenario.requested_actions),
                request_id=scenario.id,
                constraints=scenario.constraints,
            ),
            scenario_documents(scenario),
        )

    agent = LLMAgent(
        settings.llm_base_url,
        settings.llm_api_key,
        settings.llm_model,
    )
    request = UserRequest(
        text=scenario.user_request,
        requested_actions=frozenset(scenario.requested_actions),
        request_id=scenario.id,
        constraints=scenario.constraints,
    )
    return agent.propose(request, scenario_documents(scenario))


def show_action(action: Any) -> None:
    rows: list[tuple[str, str]] = [
        ("Tool", f'<span class="pg-code">{html.escape(action.tool)}</span>'),
        (
            "Amount",
            f"{action.amount:.2f} {html.escape(action.currency)}"
            if action.amount
            else "—",
        ),
        ("Beneficiary", html.escape(action.beneficiary or "—")),
        ("Reason", html.escape(action.reason or "—")),
        (
            "Cited sources",
            ", ".join(html.escape(source) for source in action.source_ids) or "—",
        ),
        (
            "Idempotency key",
            f'<span class="pg-code">{html.escape(action.idempotency_key)}</span>'
            if action.idempotency_key
            else "—",
        ),
    ]
    for name, label in (
        ("invoice_id", "Invoice"),
        ("capture_id", "Capture to refund"),
        ("recipient_email", "Recipient e-mail"),
    ):
        if action.metadata.get(name):
            rows.append(
                (
                    label,
                    f'<span class="pg-code">{html.escape(str(action.metadata[name]))}</span>',
                )
            )
    if action.tool == "create_invoice":
        rows.append(
            (
                "Invoice delivery",
                "yes — send on approval"
                if action.metadata.get("send", False)
                else "no — draft only",
            )
        )
    body = "".join(
        f"<tr><td>{html.escape(label)}</td><td>{value}</td></tr>"
        for label, value in rows
    )
    st.markdown(
        f'<table class="pg-action">{body}</table>', unsafe_allow_html=True
    )


def show_unprotected(unprotected: Any) -> None:
    st.caption("The agent calls PayPal directly — no rule intercepts the action.")
    if unprotected.dry_run:
        st.info(
            f"Simulated direct call: `{unprotected.would_call}` would go to PayPal."
        )
    else:
        if (unprotected.result or {}).get("simulated"):
            st.info("Action executed directly in the local simulator.")
        else:
            st.warning("Action executed directly in PayPal Sandbox.")
        st.json(unprotected.result or {})


def show_protected(outcome: Any, run: dict[str, Any]) -> None:
    st.caption("The same action, evaluated by policy before anything reaches PayPal.")
    decision = outcome.policy_decision.decision
    DECISION_ALERTS[decision](
        f"**{DECISION_VERBS[decision]}** — rule `{outcome.policy_decision.rule_id}`"
    )
    st.markdown(f"{html.escape(outcome.policy_decision.reason)}")
    if outcome.policy_decision.risk_factors:
        chips = "".join(
            f'<span class="pg-risk">{html.escape(factor)}</span>'
            for factor in outcome.policy_decision.risk_factors
        )
        st.markdown(
            f'<div><span class="pg-label">Risk factors</span><div>{chips}</div></div>',
            unsafe_allow_html=True,
        )

    if run.get("refused"):
        st.error("Action refused by the human — PayPal was never called.")
        return

    if outcome.executed:
        st.success(f"Authorized and executed on {run['target_label']}.")
        st.json(outcome.result or {})
    elif outcome.duplicate:
        st.info(
            f"Result already obtained on {run['target_label']} — "
            "reused without a new call to that target."
        )
        st.json(outcome.result or {})
    elif decision is Decision.CONFIRM and not run.get("human_confirmed"):
        st.markdown("**Operation awaiting human confirmation**")
        show_action(run["proposal"].action)
        st.caption("No sensitive action leaves without a human click.")
        approve, refuse = st.columns(2)
        if approve.button("Approve", type="primary", key=f"approve-{run['scenario']}"):
            try:
                confirmed = run_with_protection(
                    run["proposal"],
                    get_policy(),
                    run["adapter"],
                    run["registry"],
                    run["audit_path"],
                    human_confirmed=True,
                )
                run.update(human_confirmed=True, outcome=confirmed)
                st.rerun()
            except Exception as error:
                st.error(f"Execution failed after confirmation: {error}")
        if refuse.button("Refuse", key=f"refuse-{run['scenario']}"):
            try:
                record_human_refusal(
                    run["proposal"].request,
                    run["proposal"].action,
                    run["outcome"].policy_decision,
                    run["proposal"].provenance,
                    run["audit_path"],
                )
            except Exception as error:
                st.error(f"Could not write the refusal to the audit log: {error}")
            run["refused"] = True
            st.rerun()
    elif not outcome.executed:
        st.error("Action blocked — PayPal was never called.")


def show_audit(audit_path: Path) -> None:
    st.subheader("Audit log")
    header = (
        '<div class="pg-term-head"><span class="pg-dot"></span> live '
        f'<span class="pg-term-path">· {html.escape(str(audit_path))}</span></div>'
    )
    if not audit_path.exists():
        st.markdown(
            f'<div class="pg-terminal">{header}<div class="pg-empty">'
            "No events yet — run a scenario to see the trail.</div></div>",
            unsafe_allow_html=True,
        )
        return
    events = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][-12:]

    head_row = (
        '<div class="pg-term-row pg-term-row--head">'
        "<span>time</span><span>scenario</span><span>tool</span>"
        "<span>decision</span><span>rule</span><span>result</span>"
        "<span>paypal</span></div>"
    )
    body_rows = []
    for event in reversed(events):
        result = str(event.get("result", ""))
        color_class = RESULT_COLORS.get(result, "pg-res-duplicate")
        called = bool(event.get("paypal_called"))
        body_rows.append(
            "<div class='pg-term-row'>"
            f"<span>{html.escape(event['timestamp'][11:19])}</span>"
            f"<span>{html.escape(str(event.get('request_id')))}</span>"
            f"<span>{html.escape(str(event.get('proposed_tool')))}</span>"
            f"<span>{html.escape(str(event.get('decision')))}</span>"
            f"<span>{html.escape(str(event.get('rule_id')))}</span>"
            f"<span class='pg-res {color_class}'>{html.escape(result)}</span>"
            f"<span class='{'pg-called-yes' if called else 'pg-called-no'}'>"
            f"{'● called' if called else '○ untouched'}</span>"
            "</div>"
        )
    st.markdown(
        f'<div class="pg-terminal">{header}{head_row}{"".join(body_rows)}</div>',
        unsafe_allow_html=True,
    )


def render_sidebar(
    scenario_by_id: dict[str, Scenario], settings: Any
) -> tuple[str, str, bool, dict[str, str], Scenario, str]:
    with st.sidebar:
        if not settings.llm_configured:
            st.caption(
                "No LLM key detected — scripted mode replays the scenarios "
                "bundled in `attacks/`."
            )
        pg_section("Agent")
        mode_label = st.radio(
            "Agent",
            ["Scripted (offline)", "LLM"],
            disabled=not settings.llm_configured,
            label_visibility="collapsed",
        )

        pg_section("PayPal target")
        adapter_label = st.radio(
            "PayPal target",
            ["Local simulator", "PayPal Sandbox"],
            disabled=not settings.paypal_configured,
            help=(
                "Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in `.env` "
                "to enable the sandbox."
            ),
            label_visibility="collapsed",
        )
        dry_run = st.toggle(
            "Simulate the unprotected column",
            value=True,
            help="Disables any real call made by the left column.",
        )

        sandbox_ids: dict[str, str] = {}
        if adapter_label == "PayPal Sandbox":
            st.caption(
                "The sandbox requires the real PayPal object identifiers "
                "(capture, invoice, e-mail)."
            )
            capture_id = st.text_input("capture_id", key="capture_id")
            invoice_id = st.text_input("invoice_id", key="invoice_id")
            recipient_email = st.text_input("recipient_email", key="recipient_email")
            sandbox_ids = {
                "capture_id": capture_id,
                "invoice_id": invoice_id,
                "recipient_email": recipient_email,
            }

        st.divider()
        mode = "scripted" if mode_label.startswith("Scripted") else "llm"

        def scenario_label(scenario_id: str) -> str:
            scenario = scenario_by_id[scenario_id]
            label = f"{scenario.id} · {scenario.kind}"
            if mode == "scripted":
                label += f" · {scenario.expected_decision} expected"
            return label

        pg_section("Scenario")
        scenario_id = st.selectbox(
            "Scenario",
            list(scenario_by_id),
            format_func=scenario_label,
            key="scenario_choice",
            label_visibility="collapsed",
        )
        scenario = scenario_by_id[scenario_id]
        if adapter_label == "PayPal Sandbox":
            scenario = prepare_sandbox_scenario(scenario, sandbox_ids)

        pg_section("User request")
        st.markdown(f'<div class="pg-quote">{html.escape(scenario.user_request)}</div>', unsafe_allow_html=True)
        if scenario.constraints:
            constraints = scenario.constraints
            facts = []
            if constraints.amount is not None:
                facts.append(
                    f"<strong>Requested amount</strong> — "
                    f"{constraints.amount:.2f} {constraints.currency}"
                )
            for label, value in (
                ("Selected invoice", constraints.invoice_id),
                ("Authorized capture", constraints.capture_id),
                ("Authorized recipient", constraints.recipient_email),
            ):
                if value:
                    facts.append(f"<strong>{label}</strong> — {value}")
            if facts:
                st.markdown(
                    f'<div class="pg-facts">{"".join(f + "<br/>" for f in facts)}</div>',
                    unsafe_allow_html=True,
                )
        if scenario.external_text:
            pg_section("Untrusted external text")
            st.markdown(
                f'<div class="pg-untrusted">{html.escape(scenario.external_text)}</div>',
                unsafe_allow_html=True,
            )
        if mode == "scripted":
            st.caption(
                f"Expected outcome (scripted): {scenario.expected_decision} "
                f"(`{scenario.expected_rule}`)"
            )
        else:
            st.caption(
                "The decision applies to the action the LLM actually proposes. "
                "The model may propose something different from the scripted case."
            )
    return mode_label, adapter_label, dry_run, sandbox_ids, scenario, mode


def main() -> None:
    settings = load_settings()
    policy = get_policy()
    scenarios = load_all_scenarios()
    scenario_by_id = {scenario.id: scenario for scenario in scenarios}

    inject_css()
    render_hero()
    _, adapter_label, dry_run, sandbox_ids, scenario, mode = render_sidebar(
        scenario_by_id, settings
    )

    target = "paypal" if adapter_label == "PayPal Sandbox" else "fake"
    context = {
        "scenario": scenario.id,
        "mode": mode,
        "target": target,
        "dry_run": dry_run,
        "sandbox_ids": sandbox_ids,
        "model": settings.llm_model if mode == "llm" else None,
    }
    previous_run = st.session_state.get("run")
    if previous_run and previous_run.get("context") != context:
        st.session_state.pop("run", None)
        st.info("Settings changed — run the scenario again for a fresh result.")

    adapter = get_adapter(target)
    audit_path = settings.audit_path

    if st.button("Run scenario", type="primary"):
        st.session_state.pop("run", None)
        try:
            proposal = build_proposal(
                scenario,
                mode,
                settings,
            )
            unprotected = None
            unprotected_error = None
            try:
                unprotected = run_without_protection(
                    proposal, adapter, dry_run=dry_run
                )
            except Exception as error:
                unprotected_error = str(error)
            registry = get_registry(target)
            outcome = run_with_protection(
                proposal,
                policy,
                adapter,
                registry,
                audit_path,
            )
            st.session_state.run = {
                "scenario": scenario.id,
                "context": context,
                "target_label": adapter_label,
                "proposal": proposal,
                "unprotected": unprotected,
                "unprotected_error": unprotected_error,
                "outcome": outcome,
                "adapter": adapter,
                "registry": registry,
                "audit_path": audit_path,
                "human_confirmed": False,
                "refused": False,
            }
        except AgentError as error:
            st.error(f"The agent did not produce a usable action: {error}")
        except Exception as error:  # PayPal or configuration error
            st.error(f"Execution failed: {error}")

    run = st.session_state.get("run")
    if run and run.get("context") == context:
        proposal = run["proposal"]
        st.divider()
        st.caption(
            f"Agent proposal ({proposal.mode}) — "
            f"external documents provided: "
            f"{'yes' if scenario.external_text else 'no'}"
        )
        if (
            proposal.mode == "llm"
            and scenario.kind == "attack"
            and proposal.action.tool in {"list_invoices", "read_invoice"}
            and proposal.action.tool in proposal.request.requested_actions
        ):
            st.info(
                "The model proposed the requested read, with no financial "
                "operation. PayGuard judged this actual proposal."
            )
        if run["outcome"].policy_decision.rule_id == "provenance.untrusted_influence":
            st.caption(
                "Policy requires confirmation because external documents were "
                "supplied to the model. Their presence alone does not prove a "
                "successful injection."
            )
        pg_section("Agent proposal")
        proposal_card = st.container(border=True)
        with proposal_card:
            show_action(proposal.action)
        left, right = st.columns(2)
        with left:
            with st.container(border=True):
                st.subheader("Without PayGuard")
                if run["unprotected_error"]:
                    st.error(f"Direct call failed: {run['unprotected_error']}")
                else:
                    show_unprotected(run["unprotected"])
        with right:
            with st.container(border=True):
                st.subheader("With PayGuard")
                show_protected(run["outcome"], run)
    else:
        with st.container(border=True):
            st.markdown(
                "**Nothing executed yet.** Pick an agent, a target and a "
                "scenario in the sidebar, then click **Run scenario**. The "
                "same agent proposal is played twice: once against PayPal "
                "directly, once through the PayGuard policy engine — so you "
                "can compare exactly what the firewall changes."
            )

    st.divider()
    show_audit(audit_path)


main()
