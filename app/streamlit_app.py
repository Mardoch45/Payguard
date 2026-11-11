"""PayGuard demonstration interface.

Run from the `payguard/` directory:

    streamlit run app/streamlit_app.py
"""

import json
import sys
from dataclasses import asdict, replace
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
from app.invoice_documents import fetch_invoice_summaries, load_invoice_document  # noqa: E402
from app.scenarios import Scenario, load_all_scenarios, prepare_sandbox_scenario  # noqa: E402
from app.ui import (  # noqa: E402
    icon,
    inject_styles,
    render_brand,
    render_comparison_empty,
    render_footer,
    render_hero,
    render_policy_facts,
    render_result_banner,
    render_scenario_heading,
    render_sidebar_footer,
    render_sources,
    scenario_name,
    show_action,
    show_audit,
)
from guard.execution import record_human_refusal  # noqa: E402
from guard.idempotency import IdempotencyRegistry  # noqa: E402
from guard.models import Decision, UserRequest  # noqa: E402
from guard.policy import load_policy  # noqa: E402
from guard.provenance import SourceType  # noqa: E402
from guard.settings import load_settings  # noqa: E402

st.set_page_config(
    page_title="PayGuard — Transaction Firewall for AI Agents",
    page_icon=str(PROJECT_ROOT / "app" / "assets" / "payguard-mark.svg"),
    layout="wide",
    initial_sidebar_state="expanded",
)


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
    invoice_document: Document | None = None,
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
    documents = scenario_documents(scenario)
    if invoice_document is not None:
        documents = [documents[0], invoice_document]
    return agent.propose(request, documents)


def show_unprotected(unprotected: Any) -> None:
    st.caption("The agent calls PayPal directly, with no policy checkpoint.")
    if unprotected.dry_run:
        render_result_banner(
            "Direct call preview",
            "This action would reach the payment target without a policy check. No direct call was made in preview mode.",
            "muted",
            "arrow",
        )
        st.caption(f"Proposed call: {unprotected.would_call}")
    else:
        simulated = (unprotected.result or {}).get("simulated")
        render_result_banner(
            "Executed without a checkpoint",
            "The local simulator executed the agent's action directly."
            if simulated else "PayPal Sandbox executed the agent's action directly.",
            "warning",
            "warning",
        )
        with st.expander("Direct execution response"):
            st.json(unprotected.result or {})


def show_protected(outcome: Any, run: dict[str, Any]) -> None:
    st.caption("The same proposal, checked before reaching the payment target.")
    decision = outcome.policy_decision.decision

    if run.get("refused"):
        render_result_banner("Refused by you", "The operation stopped. PayPal was never called.", "muted", "lock")
    elif outcome.executed:
        render_result_banner("Authorized and executed", f"The checked action completed on {run['target_label']}.", "success", "check")
        with st.expander("Protected execution response"):
            st.json(outcome.result or {})
    elif outcome.duplicate:
        render_result_banner("Already completed", "PayGuard reused the previous result without calling the payment target again.", "blue", "shield")
        with st.expander("Reused execution response"):
            st.json(outcome.result or {})
    elif decision is Decision.CONFIRM and not run.get("human_confirmed"):
        render_result_banner("Your approval is required", "Review the proposal above. This operation waits for your explicit decision.", "warning", "clock")
        st.write(outcome.policy_decision.reason)
        approve, refuse = st.columns(2)
        if approve.button("Approve", type="primary", key=f"approve-{run['scenario']}", use_container_width=True):
            try:
                with st.spinner("Executing the approved action…"):
                    confirmed = run_with_protection(
                        run["proposal"], get_policy(), run["adapter"],
                        run["registry"], run["audit_path"], human_confirmed=True,
                    )
                run.update(human_confirmed=True, outcome=confirmed)
                st.rerun()
            except Exception as error:
                st.error(f"Execution failed after confirmation: {error}. Review the target configuration before retrying.")
        if refuse.button("Refuse", key=f"refuse-{run['scenario']}", use_container_width=True):
            try:
                record_human_refusal(
                    run["proposal"].request, run["proposal"].action,
                    run["outcome"].policy_decision, run["proposal"].provenance,
                    run["audit_path"],
                )
            except Exception as error:
                st.error(f"Could not write the refusal to the audit log: {error}")
            run["refused"] = True
            st.rerun()
    else:
        st.error("**BLOCKED** — Action blocked before execution. PayPal was never called.")
        st.write(outcome.policy_decision.reason)

    with st.expander("Policy check details"):
        st.caption(f"Decision: {decision.value}")
        st.code(outcome.policy_decision.rule_id, language=None)
        if outcome.policy_decision.risk_factors:
            st.write("Risk factors: " + ", ".join(outcome.policy_decision.risk_factors))
        if outcome.executed or outcome.duplicate or run.get("refused"):
            st.write(outcome.policy_decision.reason)


def render_sidebar(
    scenario_by_id: dict[str, Scenario], settings: Any
) -> tuple[str, str, bool, dict[str, str], Scenario, str, bool, Document | None]:
    use_paypal_note = False
    invoice_document: Document | None = None
    with st.sidebar:
        render_brand()

        def scenario_label(scenario_id: str) -> str:
            return scenario_name(scenario_by_id[scenario_id])

        def update_scenario_url() -> None:
            st.query_params["scenario"] = st.session_state.scenario_choice

        scenario_id = st.selectbox(
            "Scenario", list(scenario_by_id), format_func=scenario_label,
            key="scenario_choice", on_change=update_scenario_url,
        )
        st.divider()
        st.html('<h2 class="pg-sidebar-heading" id="configuration">Test configuration</h2>')
        mode_label = st.radio(
            "Agent", ["Scripted (offline)", "LLM"],
            disabled=not settings.llm_configured,
            help="Scripted mode works offline. Configure an LLM API key to enable live agent proposals.",
        )
        adapter_label = st.radio(
            "PayPal target", ["Local simulator", "PayPal Sandbox"],
            disabled=not settings.paypal_configured,
            help="The simulator works offline. Configure PayPal Sandbox credentials to connect a test account.",
        )
        dry_run = st.toggle(
            "Preview the direct call", value=True,
            help="Preview what happens without PayGuard. Turn this off to execute the direct call on the selected test target.",
        )
        sandbox_ids: dict[str, str] = {}
        if adapter_label == "PayPal Sandbox":
            with st.expander("Sandbox payment details", expanded=True):
                st.caption("Use the identifiers from your PayPal test account.")
                if st.button("Load my invoices", key="load_invoice_list", use_container_width=True):
                    st.session_state.pop("sandbox_invoice_options", None)
                    st.session_state.pop("invoice_pick", None)
                    st.session_state.pop("invoice_pick_loaded", None)
                    try:
                        with st.spinner("Listing your Sandbox invoices…"):
                            st.session_state.sandbox_invoice_options = fetch_invoice_summaries(
                                get_policy(), get_adapter("paypal"),
                                get_registry("paypal"), settings.audit_path,
                            )
                    except Exception as error:
                        st.error(f"Could not list the invoices: {error}")
                options = st.session_state.get("sandbox_invoice_options") or []
                if options:
                    st.success(f"{len(options)} invoice(s) loaded from PayPal Sandbox.")
                    query = st.text_input(
                        "Filter", key="invoice_filter",
                        placeholder="number, amount, status, recipient…",
                    ).strip().lower()

                    def invoice_label(summary: dict[str, Any]) -> str:
                        name = summary.get("invoice_number") or summary.get("id") or "?"
                        amount = f"{summary.get('amount', '?')} {summary.get('currency') or ''}".strip()
                        recipient = summary.get("recipient_email") or "no recipient"
                        return f"{name} — {amount} — {summary.get('status') or '?'} — {recipient}"

                    filtered = [s for s in options if query in invoice_label(s).lower()]
                    if filtered:
                        chosen = st.selectbox(
                            "Pick an invoice", filtered,
                            format_func=invoice_label, key="invoice_pick",
                        )
                        if chosen and st.session_state.get("invoice_pick_loaded") != chosen.get("id"):
                            st.session_state["invoice_pick_loaded"] = chosen.get("id")
                            st.session_state["invoice_id"] = str(chosen.get("id") or "")
                            if chosen.get("recipient_email"):
                                st.session_state["recipient_email"] = str(chosen["recipient_email"])
                        st.caption("Picking an invoice fills the fields below — the capture ID stays manual.")
                    else:
                        st.info("No invoice matches this filter.")
                capture_id = st.text_input("Payment capture ID", key="capture_id", placeholder="Capture identifier…")
                invoice_id = st.text_input("Invoice ID", key="invoice_id", placeholder="Invoice identifier…").strip()
                recipient_email = st.text_input("Recipient email", key="recipient_email", placeholder="buyer@example.com…")
                sandbox_ids = {"capture_id": capture_id, "invoice_id": invoice_id, "recipient_email": recipient_email}

        mode = "scripted" if mode_label.startswith("Scripted") else "llm"

        scenario = scenario_by_id[scenario_id]
        if adapter_label == "PayPal Sandbox":
            scenario = prepare_sandbox_scenario(scenario, sandbox_ids)

        if mode == "llm" and adapter_label == "PayPal Sandbox":
            use_paypal_note = st.toggle(
                "Use the PayPal invoice note", key="use_paypal_note",
                help="Replaces the scenario document with the note from a Sandbox invoice.",
            )
            loaded = st.session_state.get("loaded_invoice_document")
            if loaded and loaded["invoice_id"] != sandbox_ids["invoice_id"]:
                st.session_state.pop("loaded_invoice_document", None)
            if use_paypal_note:
                if st.button("Load PayPal invoice", disabled=not sandbox_ids["invoice_id"], key="load_paypal_invoice", use_container_width=True):
                    st.session_state.pop("loaded_invoice_document", None)
                    st.session_state.pop("run", None)
                    try:
                        with st.spinner("Reading the Sandbox invoice…"):
                            document = load_invoice_document(
                                sandbox_ids["invoice_id"], get_policy(), get_adapter("paypal"),
                                get_registry("paypal"), settings.audit_path,
                            )
                        st.session_state.loaded_invoice_document = {"invoice_id": sandbox_ids["invoice_id"], "document": document}
                    except Exception as error:
                        st.error(f"Could not load the invoice: {error}")
                loaded = st.session_state.get("loaded_invoice_document")
                if loaded:
                    invoice_document = loaded["document"]
                    scenario = replace(scenario, external_text=invoice_document.text)
                    st.success("Invoice loaded from PayPal Sandbox.")
                    with st.expander("Loaded invoice document"):
                        st.code(invoice_document.text, language="json")
                    if not json.loads(invoice_document.text)["note"]:
                        st.info("This invoice carries no note.")
                else:
                    st.info("Enter an invoice ID and load the invoice before running the scenario.")
            else:
                st.session_state.pop("loaded_invoice_document", None)
        else:
            st.session_state.pop("loaded_invoice_document", None)
        st.caption("Choose a scenario, then run it in the workspace to compare both paths.")
        render_sidebar_footer()
    return mode_label, adapter_label, dry_run, sandbox_ids, scenario, mode, use_paypal_note, invoice_document


def main() -> None:
    settings = load_settings()
    policy = get_policy()
    scenarios = load_all_scenarios()
    scenario_by_id = {scenario.id: scenario for scenario in scenarios}
    url_scenario = st.query_params.get("scenario")
    if "scenario_choice" not in st.session_state and url_scenario in scenario_by_id:
        st.session_state.scenario_choice = url_scenario

    inject_styles()
    _, adapter_label, dry_run, sandbox_ids, scenario, mode, use_paypal_note, invoice_document = render_sidebar(scenario_by_id, settings)
    render_hero(adapter_label)
    render_policy_facts(policy, scenarios)
    render_scenario_heading(scenario)
    render_sources(scenario, use_paypal_note, mode)

    target = "paypal" if adapter_label == "PayPal Sandbox" else "fake"
    context = {
        "scenario": scenario.id, "mode": mode, "target": target,
        "dry_run": dry_run, "sandbox_ids": sandbox_ids,
        "model": settings.llm_model if mode == "llm" else None,
        "use_paypal_note": use_paypal_note,
        "invoice_document": invoice_document.text if invoice_document else None,
    }
    previous_run = st.session_state.get("run")
    if previous_run and previous_run.get("context") != context:
        st.session_state.pop("run", None)
        st.info("Settings changed. Run the scenario again to see the new result.")

    adapter = get_adapter(target)
    audit_path = settings.audit_path
    with st.container(key="pg_runbar"):
        description, action = st.columns([3, 1.25], gap="medium", vertical_alignment="center")
        with description:
            st.html(
                '<div class="pg-runbar-copy">' + icon("play")
                + '<div><strong>See the firewall in action</strong>'
                '<p>Compare the same agent proposal with and without protection.</p></div></div>'
            )
        with action:
            run_clicked = st.button("Run scenario", type="primary", disabled=use_paypal_note and invoice_document is None, use_container_width=True)

    if run_clicked:
        st.session_state.pop("run", None)
        try:
            with st.spinner("Evaluating the agent proposal…"):
                proposal = build_proposal(scenario, mode, settings, invoice_document)
                unprotected = None
                unprotected_error = None
                try:
                    unprotected = run_without_protection(proposal, adapter, dry_run=dry_run)
                except Exception as error:
                    unprotected_error = str(error)
                registry = get_registry(target)
                outcome = run_with_protection(proposal, policy, adapter, registry, audit_path)
                st.session_state.run = {
                    "scenario": scenario.id, "context": context, "target_label": adapter_label,
                    "proposal": proposal, "unprotected": unprotected,
                    "unprotected_error": unprotected_error, "outcome": outcome,
                    "adapter": adapter, "registry": registry, "audit_path": audit_path,
                    "human_confirmed": False, "refused": False, "invoice_document": invoice_document,
                }
        except AgentError as error:
            st.error(f"The agent did not produce a usable action: {error}. Check the agent configuration and try again.")
        except Exception as error:
            st.error(f"Execution failed: {error}. Check the selected test target and try again.")

    run = st.session_state.get("run")
    if run and run.get("context") == context:
        proposal = run["proposal"]
        st.caption(
            f"Agent proposal ({proposal.mode}) — external documents provided: "
            f"{'yes' if scenario.external_text else 'no'}"
        )
        if run.get("invoice_document"):
            st.caption("External source: invoice read from PayPal Sandbox. The preparation read appears in the audit log too.")
        if (
            proposal.mode == "llm" and scenario.kind == "attack"
            and proposal.action.tool in {"list_invoices", "read_invoice"}
            and proposal.action.tool in proposal.request.requested_actions
        ):
            st.info("The model proposed the requested read, with no financial operation. PayGuard judged this actual proposal.")
        if run["outcome"].policy_decision.rule_id == "provenance.untrusted_influence":
            st.caption("External documents require a policy check. Their presence alone does not prove a successful injection.")
        with st.container(key="pg_proposal"):
            st.subheader("Agent proposal")
            show_action(proposal.action)
        with st.container(key="pg_comparison"):
            left, right = st.columns(2, gap="medium")
            with left:
                with st.container(key="pg_direct_result"):
                    st.subheader("Without PayGuard")
                    if run["unprotected_error"]:
                        st.error(f"Direct call failed: {run['unprotected_error']}")
                    else:
                        show_unprotected(run["unprotected"])
            with right:
                with st.container(key="pg_guarded_result"):
                    st.subheader("With PayGuard")
                    show_protected(run["outcome"], run)
    else:
        render_comparison_empty()

    show_audit(audit_path)
    render_footer()


main()
