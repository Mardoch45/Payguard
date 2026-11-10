from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402
import streamlit as st  # noqa: E402

from adapters.fake import FakePayPalAdapter  # noqa: E402
from agent.llm import AgentError, LLMAgent  # noqa: E402
from agent.models import AgentProposal  # noqa: E402
from agent.proposal import build_action, build_provenance  # noqa: E402
from guard.models import Decision  # noqa: E402

APP_PATH = Path(__file__).parents[1] / "app" / "streamlit_app.py"


def test_app_boots_and_runs_a_scenario() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=30)
    app.run()

    assert not app.exception
    assert app.radio[0].disabled
    assert app.radio[1].disabled
    run_buttons = [button for button in app.button if "Run scenario" in button.label]
    assert run_buttons

    run_buttons[0].click().run()

    assert not app.exception
    assert any("Without PayGuard" in header.value for header in app.subheader)


@pytest.fixture
def configured_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("LLM_API_KEY", "test-llm-key")
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "test-paypal-id")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "test-paypal-secret")
    monkeypatch.setenv("PAYGUARD_AUDIT_PATH", str(tmp_path / "audit.jsonl"))

    def propose_read(self, request, documents):
        action = build_action("list_invoices", {"sources": ["consigne-utilisateur"]}, request)
        return AgentProposal(request, action, build_provenance(action.source_ids, documents), mode="llm")

    monkeypatch.setattr(LLMAgent, "propose", propose_read)

    class RecordingSandboxAdapter:
        def __init__(self):
            self.calls = []

        def execute(self, action):
            self.calls.append(action)
            return {"backend": "sandbox-test", "invoices": [], "simulated": False}

    sandbox = RecordingSandboxAdapter()
    monkeypatch.setattr("adapters.paypal.PayPalSandboxAdapter", lambda client: sandbox)
    st.cache_resource.clear()
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    yield app, sandbox
    st.cache_resource.clear()


def execute_scenario(app):
    return next(button for button in app.button if button.label == "Run scenario").click().run()


def test_llm_decision_uses_real_proposal_and_external_exposure(configured_app) -> None:
    app, sandbox = configured_app
    app.radio[0].set_value("LLM").run()

    assert all("BLOCK" not in option for option in app.selectbox[0].options)
    execute_scenario(app)

    assert not app.exception
    run = app.session_state["run"]
    assert run["proposal"].action.tool == "list_invoices"
    assert run["outcome"].policy_decision.decision is Decision.CONFIRM
    assert run["adapter"].calls == []
    assert sandbox.calls == []
    assert any("external documents provided: yes" in caption.value for caption in app.caption)
    assert any("no financial operation" in message.value for message in app.info)
    next(button for button in app.button if button.label == "Approve").click().run()
    assert not app.exception
    assert app.session_state["run"]["outcome"].executed


def test_switching_agent_mode_hides_old_result(configured_app) -> None:
    app, _ = configured_app
    app.radio[0].set_value("LLM").run()
    execute_scenario(app)

    app.radio[0].set_value("Scripted (offline)").run()

    assert not app.exception
    assert not any(header.value == "With PayGuard" for header in app.subheader)
    assert app.selectbox[0].value == "attack-direct-001"
    execute_scenario(app)
    assert app.session_state["run"]["proposal"].action.tool == "refund_payment"
    assert app.session_state["run"]["outcome"].policy_decision.decision is Decision.BLOCK


def test_simulator_result_is_not_reused_in_sandbox(configured_app) -> None:
    app, sandbox = configured_app
    app.radio[0].set_value("LLM").run()
    app.selectbox[0].select("normal-list-001").run()
    execute_scenario(app)
    fake_result = app.session_state["run"]["outcome"].result
    assert fake_result["simulated"] is True

    app.radio[1].set_value("PayPal Sandbox").run()
    assert not any(header.value == "With PayGuard" for header in app.subheader)
    execute_scenario(app)

    assert not app.exception
    assert len(sandbox.calls) == 1
    assert app.session_state["run"]["outcome"].executed
    assert app.session_state["run"]["outcome"].result["backend"] == "sandbox-test"

    app.radio[1].set_value("Local simulator").run()
    execute_scenario(app)
    assert app.session_state["run"]["outcome"].executed
    assert not app.session_state["run"]["outcome"].duplicate
    assert app.session_state["run"]["outcome"].result["simulated"] is True
    assert app.session_state["run"]["outcome"].result["id"] != fake_result["id"]
    assert len(sandbox.calls) == 1


def test_payment_results_remain_separate_between_simulator_and_sandbox(configured_app) -> None:
    app, sandbox = configured_app
    app.selectbox[0].select("normal-refund-001").run()
    execute_scenario(app)
    next(button for button in app.button if button.label == "Approve").click().run()
    fake_result = app.session_state["run"]["outcome"].result
    assert fake_result["simulated"] is True

    app.radio[1].set_value("PayPal Sandbox").run()
    app.text_input(key="capture_id").set_value("CAPTURE-TEST-001").run()
    execute_scenario(app)
    next(button for button in app.button if button.label == "Approve").click().run()

    assert not app.exception
    assert len(sandbox.calls) == 1
    assert app.session_state["run"]["outcome"].result["backend"] == "sandbox-test"

    app.radio[1].set_value("Local simulator").run()
    execute_scenario(app)
    next(button for button in app.button if button.label == "Approve").click().run()
    assert app.session_state["run"]["outcome"].duplicate
    assert app.session_state["run"]["outcome"].result == fake_result
    assert len(sandbox.calls) == 1


def test_failed_llm_run_does_not_display_previous_success(
    configured_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, _ = configured_app
    app.radio[0].set_value("LLM").run()
    app.selectbox[0].select("normal-list-001").run()
    execute_scenario(app)

    def fail(*args, **kwargs):
        raise AgentError("model unavailable in test")

    monkeypatch.setattr(LLMAgent, "propose", fail)
    execute_scenario(app)

    assert not app.exception
    assert not any(header.value == "With PayGuard" for header in app.subheader)
    assert any("model unavailable in test" in error.value for error in app.error)


def test_unprotected_error_does_not_hide_guard_decision(
    configured_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, _ = configured_app

    def fail(*args, **kwargs):
        raise RuntimeError("direct call failed in test")

    monkeypatch.setattr(FakePayPalAdapter, "execute", fail)
    app.toggle[0].set_value(False).run()
    execute_scenario(app)

    assert not app.exception
    assert app.session_state["run"]["outcome"].policy_decision.decision is Decision.BLOCK
    assert any("direct call failed in test" in error.value for error in app.error)
    assert any("BLOCK" in error.value for error in app.error)


def test_under_limit_amount_attack_is_visible_and_blocked(configured_app) -> None:
    app, sandbox = configured_app
    app.selectbox[0].select("attack-request-amount-001").run()
    execute_scenario(app)

    assert not app.exception
    run = app.session_state["run"]
    assert run["proposal"].request.constraints.amount == 5.00
    assert run["proposal"].action.amount == 15.00
    assert run["outcome"].policy_decision.rule_id == "intent.amount_mismatch"
    assert run["adapter"].calls == []
    assert sandbox.calls == []
    assert all(button.label != "Approve" for button in app.button)
    assert any("5.00 USD" in line.value for line in app.markdown)


@pytest.mark.parametrize("proposed_capture", ["CAPTURE-OTHER", None])
def test_model_capture_is_never_replaced_with_the_authorized_selection(
    configured_app, monkeypatch: pytest.MonkeyPatch, proposed_capture
) -> None:
    app, sandbox = configured_app

    def propose_refund(self, request, documents):
        arguments = {
            "amount": 15, "currency": "USD", "beneficiary": "sandbox-buyer-001",
            "sources": ["consigne-utilisateur"], "capture_id": proposed_capture,
        }
        action = build_action("refund_payment", arguments, request)
        return AgentProposal(request, action, build_provenance(action.source_ids, documents), mode="llm")

    monkeypatch.setattr(LLMAgent, "propose", propose_refund)
    app.radio[0].set_value("LLM").run()
    app.radio[1].set_value("PayPal Sandbox").run()
    app.text_input(key="capture_id").set_value("CAPTURE-SELECTED").run()
    app.selectbox[0].select("normal-refund-001").run()
    execute_scenario(app)

    assert not app.exception
    run = app.session_state["run"]
    assert run["proposal"].request.constraints.capture_id == "CAPTURE-SELECTED"
    assert run["proposal"].action.metadata.get("capture_id") == proposed_capture
    assert run["outcome"].policy_decision.decision is Decision.BLOCK
    assert run["outcome"].policy_decision.rule_id == "intent.capture_id_mismatch"
    assert sandbox.calls == []
    assert all(button.label != "Approve" for button in app.button)
