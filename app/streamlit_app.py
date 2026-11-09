"""Interface de démonstration PayGuard.

Lancement depuis le dossier `payguard/` :

    streamlit run app/streamlit_app.py
"""

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

st.set_page_config(page_title="PayGuard", page_icon="🛡️", layout="wide")

DECISION_STYLES = {
    Decision.ALLOW: st.success,
    Decision.CONFIRM: st.warning,
    Decision.BLOCK: st.error,
}


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
    rows = {
        "Outil": action.tool,
        "Montant": f"{action.amount:.2f} {action.currency}" if action.amount else "—",
        "Bénéficiaire": action.beneficiary or "—",
        "Raison": action.reason or "—",
        "Sources citées": ", ".join(action.source_ids) or "—",
        "Clé d'idempotence": action.idempotency_key or "—",
    }
    for name, label in (
        ("invoice_id", "Facture"),
        ("capture_id", "Capture à rembourser"),
        ("recipient_email", "E-mail destinataire"),
    ):
        if action.metadata.get(name):
            rows[label] = action.metadata[name]
    if action.tool == "create_invoice":
        rows["Envoi de la facture"] = "oui" if action.metadata.get("send", False) else "non (brouillon)"
    for label, value in rows.items():
        st.markdown(f"**{label}** : {value}")


def show_unprotected(unprotected: Any) -> None:
    st.subheader("Sans protection")
    st.caption("L'agent appelle PayPal directement : aucune règle n'intercepte l'action.")
    if unprotected.dry_run:
        st.info(
            f"Appel direct simulé : `{unprotected.would_call}` partirait vers PayPal."
        )
    else:
        if (unprotected.result or {}).get("simulated"):
            st.info("Action exécutée directement dans le simulateur local.")
        else:
            st.warning("Action exécutée directement dans PayPal Sandbox.")
        st.json(unprotected.result or {})


def show_protected(outcome: Any, run: dict[str, Any]) -> None:
    st.subheader("Avec PayGuard")
    decision = outcome.policy_decision.decision
    DECISION_STYLES[decision](
        f"{decision.value} — règle `{outcome.policy_decision.rule_id}`"
    )
    st.markdown(f"**Décision** : {outcome.policy_decision.reason}")
    if outcome.policy_decision.risk_factors:
        st.markdown(
            "**Facteurs de risque** : "
            + ", ".join(outcome.policy_decision.risk_factors)
        )

    if run.get("refused"):
        st.error("Action refusée par l'humain : aucun appel PayPal.")
        return

    if outcome.executed:
        st.success(f"Action autorisée et exécutée : {run['target_label']}.")
        st.json(outcome.result or {})
    elif outcome.duplicate:
        st.info(
            f"Résultat déjà obtenu sur {run['target_label']} : "
            "réutilisé sans nouvel appel à cette cible."
        )
        st.json(outcome.result or {})
    elif decision is Decision.CONFIRM and not run.get("human_confirmed"):
        st.markdown("**Opération à confirmer**")
        show_action(run["proposal"].action)
        st.caption("Aucune action sensible ne part sans un clic humain.")
        approve, refuse = st.columns(2)
        if approve.button("Autoriser", type="primary", key=f"approve-{run['scenario']}"):
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
                st.error(f"Échec de l'exécution après confirmation : {error}")
        if refuse.button("Refuser", key=f"refuse-{run['scenario']}"):
            try:
                record_human_refusal(
                    run["proposal"].request,
                    run["proposal"].action,
                    run["outcome"].policy_decision,
                    run["proposal"].provenance,
                    run["audit_path"],
                )
            except Exception as error:
                st.error(f"Journalisation du refus impossible : {error}")
            run["refused"] = True
            st.rerun()
    elif not outcome.executed:
        st.error("Action bloquée : PayPal n'a jamais été appelé.")


def show_audit(audit_path: Path) -> None:
    st.subheader("Journal d'audit")
    if not audit_path.exists():
        st.caption("Aucun événement pour le moment.")
        return
    events = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][-12:]
    st.dataframe(
        [
            {
                "heure": event["timestamp"][11:19],
                "scénario": event.get("request_id"),
                "outil": event.get("proposed_tool"),
                "décision": event.get("decision"),
                "règle": event.get("rule_id"),
                "résultat": event.get("result"),
                "Adaptateur appelé": "oui" if event.get("paypal_called") else "non",
            }
            for event in reversed(events)
        ],
        use_container_width=True,
        hide_index=True,
    )


def main() -> None:
    settings = load_settings()
    policy = get_policy()
    scenarios = load_all_scenarios()
    scenario_by_id = {scenario.id: scenario for scenario in scenarios}

    st.title("🛡️ PayGuard")
    st.caption(
        "La même action, deux fois : l'agent seul, puis l'agent derrière le "
        "garde-fou. PayPal Sandbox uniquement."
    )

    with st.sidebar:
        st.header("Démonstration")
        if not settings.llm_configured:
            st.caption(
                "Aucune clé LLM détectée : le mode scripté rejoue les scénarios "
                "fournis dans `attacks/`."
            )
        mode_label = st.radio(
            "Agent",
            ["Scripté (hors-ligne)", "LLM"],
            disabled=not settings.llm_configured,
        )

        paypal_available = settings.paypal_configured
        adapter_label = st.radio(
            "Cible PayPal",
            ["Simulateur local", "PayPal Sandbox"],
            disabled=not paypal_available,
            help=(
                "Renseigne PAYPAL_CLIENT_ID et PAYPAL_CLIENT_SECRET dans `.env` "
                "pour activer la sandbox."
            ),
        )
        dry_run = st.toggle(
            "Simuler la colonne sans protection",
            value=True,
            help="Désactive tout appel réel de la colonne de gauche.",
        )

        sandbox_ids: dict[str, str] = {}
        if adapter_label == "PayPal Sandbox":
            st.caption(
                "La sandbox exige les identifiants réels de l'objet PayPal "
                "(capture, facture, e-mail)."
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
        mode = "scripted" if mode_label.startswith("Scripté") else "llm"

        def scenario_label(scenario_id: str) -> str:
            scenario = scenario_by_id[scenario_id]
            label = f"{scenario.id} · {scenario.kind}"
            if mode == "scripted":
                label += f" · {scenario.expected_decision} attendu"
            return label

        scenario_id = st.selectbox(
            "Scénario",
            list(scenario_by_id),
            format_func=scenario_label,
            key="scenario_choice",
        )
        scenario = scenario_by_id[scenario_id]
        if adapter_label == "PayPal Sandbox":
            scenario = prepare_sandbox_scenario(scenario, sandbox_ids)
        st.markdown(f"**Consigne** : {scenario.user_request}")
        if scenario.constraints:
            constraints = scenario.constraints
            if constraints.amount is not None:
                st.markdown(f"**Montant demandé** : {constraints.amount:.2f} {constraints.currency}")
            for label, value in (
                ("Facture choisie", constraints.invoice_id),
                ("Capture autorisée", constraints.capture_id),
                ("Destinataire autorisé", constraints.recipient_email),
            ):
                if value:
                    st.markdown(f"**{label}** : {value}")
        if scenario.external_text:
            st.markdown(f"**Texte externe** : {scenario.external_text}")
        if mode == "scripted":
            st.caption(
                f"Résultat attendu du scénario scripté : {scenario.expected_decision} "
                f"(`{scenario.expected_rule}`)"
            )
        else:
            st.caption(
                "La décision dépend de l'action réellement proposée par le LLM. "
                "Le modèle peut proposer une action différente du scénario scripté."
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
        st.info("Réglages modifiés : exécute le scénario pour obtenir un nouveau résultat.")

    adapter = get_adapter(target)
    audit_path = settings.audit_path

    if st.button("Exécuter le scénario", type="primary"):
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
            st.error(f"L'agent n'a pas produit d'action exploitable : {error}")
        except Exception as error:  # erreur PayPal ou configuration
            st.error(f"Échec de l'exécution : {error}")

    run = st.session_state.get("run")
    if run and run.get("context") == context:
        proposal = run["proposal"]
        st.divider()
        st.caption(
            f"Proposition de l'agent ({proposal.mode}) — "
            f"documents externes fournis : "
            f"{'oui' if scenario.external_text else 'non'}"
        )
        if (
            proposal.mode == "llm"
            and scenario.kind == "attaque"
            and proposal.action.tool in {"list_invoices", "read_invoice"}
            and proposal.action.tool in proposal.request.requested_actions
        ):
            st.info(
                "Le modèle a proposé une lecture du type demandé, "
                "sans opération financière. PayGuard contrôle cette proposition réelle."
            )
        if run["outcome"].policy_decision.rule_id == "provenance.untrusted_influence":
            st.caption(
                "La politique exige une confirmation car des documents externes "
                "ont été fournis au modèle. Leur présence ne prouve pas une injection réussie."
            )
        left, right = st.columns(2)
        with left:
            show_action(proposal.action)
            st.divider()
            if run["unprotected_error"]:
                st.subheader("Sans protection")
                st.error(f"Échec de l'appel direct : {run['unprotected_error']}")
            else:
                show_unprotected(run["unprotected"])
        with right:
            show_protected(run["outcome"], run)

    st.divider()
    show_audit(audit_path)


main()
