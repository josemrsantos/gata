import json
import logging
from unittest.mock import MagicMock

from google.genai.errors import ServerError

from agents.agent_image_evaluator import (
    _build_eval_prompt,
    _parse_evaluation,
    evaluate,
)
from core.types import (
    CartoonConcept,
    CartoonLayout,
    EnrichedBrief,
    PanelConcept,
)

# -- fixtures --

_BRIEF = EnrichedBrief(
    target_audience="Portuguese millennials",
    output_language="Portuguese",
    tone="dry wit",
    cultural_angle="Housing crisis as feudal landlordism",
    culturally_loaded_references=["Salazar", "Carnation Revolution"],
)

_CONCEPT = CartoonConcept(
    full_text="Gata stares at a sign reading 'Renda: 2000€' on the newsroom board",
    image_prompt="Gata stares at a sign reading 'Renda: 2000€' on the newsroom board",
    iteration=1,
)

_MULTI_CONCEPT = CartoonConcept(
    full_text="",
    image_prompt="",
    iteration=0,
    panels=[
        PanelConcept(
            scene="Gata reads headline", caption="Mais uma vez.", beat="setup"
        ),
        PanelConcept(
            scene="Gata flips the board", caption="Feito.", beat="punchline"
        ),
    ],
)

_LAYOUT_2H = CartoonLayout(panels=2, direction="horizontal")

_FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20

_APPROVED_JSON = {
    "artifacts": [],
    "is_funny": True,
    "funny_notes": "The visual lands without the caption.",
    "verdict": "APPROVED",
}

_ARTIFACT_JSON = {
    "artifacts": ["Duplicate caption text in bottom-left and top-right corners"],
    "is_funny": True,
    "funny_notes": "Funny concept, but the duplicate text ruins it.",
    "verdict": "REJECTED",
}

_NOT_FUNNY_JSON = {
    "artifacts": [],
    "is_funny": False,
    "funny_notes": "The image is competent but merely illustrative, not funny.",
    "verdict": "REJECTED",
}

_DEFAULT_MODELS = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"]


def _make_response(json_dict: dict, usage_metadata=None) -> MagicMock:
    resp = MagicMock()
    resp.text = json.dumps(json_dict)
    resp.usage_metadata = usage_metadata
    return resp


def _make_provider(model_id: str, response=None, *, side_effect=None):
    """Create a mock GeminiProvider for evaluate() tests."""
    provider = MagicMock()
    provider.model_id = model_id
    provider.compute_cost.return_value = 0.0
    if side_effect is not None:
        provider.client.models.generate_content.side_effect = side_effect
    elif response is not None:
        provider.client.models.generate_content.return_value = response
    return provider


def _make_providers(response=None, *, side_effect=None):
    """Create a standard 3-provider chain for tests that only care about the first."""
    return [
        _make_provider("gemini-2.5-pro", response, side_effect=side_effect),
        _make_provider("gemini-2.5-flash"),
        _make_provider("gemini-2.0-flash"),
    ]


def _write_fake_image(tmp_path) -> str:
    path = tmp_path / "cartoon.png"
    path.write_bytes(_FAKE_PNG)
    return str(path)


# ---------------------------------------------------------------------------
# Happy path — APPROVED
# ---------------------------------------------------------------------------


def test_evaluate_approved_when_no_artifacts_and_funny(tmp_path):
    # evaluate() must return APPROVED when Gemini finds no artifacts and rates it funny.
    image_path = _write_fake_image(tmp_path)
    providers = _make_providers(_make_response(_APPROVED_JSON))
    result, _tel = evaluate(image_path, _CONCEPT, _BRIEF, providers)
    assert result.verdict == "APPROVED"
    assert result.artifacts == []
    assert result.is_funny is True


# ---------------------------------------------------------------------------
# REJECTED — artifacts found
# ---------------------------------------------------------------------------


def test_evaluate_rejected_when_artifacts_found(tmp_path):
    # evaluate() must return REJECTED when Gemini reports rendering artifacts.
    image_path = _write_fake_image(tmp_path)
    providers = _make_providers(_make_response(_ARTIFACT_JSON))
    result, _tel = evaluate(image_path, _CONCEPT, _BRIEF, providers)
    assert result.verdict == "REJECTED"
    assert len(result.artifacts) > 0


def test_evaluate_artifacts_list_preserved(tmp_path):
    # evaluate() must propagate artifact descriptions exactly as Gemini reports them.
    image_path = _write_fake_image(tmp_path)
    providers = _make_providers(_make_response(_ARTIFACT_JSON))
    result, _tel = evaluate(image_path, _CONCEPT, _BRIEF, providers)
    assert "Duplicate caption text" in result.artifacts[0]


# ---------------------------------------------------------------------------
# REJECTED — not funny
# ---------------------------------------------------------------------------


def test_evaluate_rejected_when_not_funny(tmp_path):
    # evaluate() must return REJECTED when Gemini rates is_funny as false.
    image_path = _write_fake_image(tmp_path)
    providers = _make_providers(_make_response(_NOT_FUNNY_JSON))
    result, _tel = evaluate(image_path, _CONCEPT, _BRIEF, providers)
    assert result.verdict == "REJECTED"
    assert result.is_funny is False
    assert result.artifacts == []


# ---------------------------------------------------------------------------
# _parse_evaluation derives verdict from fields, not from model's verdict field
# ---------------------------------------------------------------------------


def test_parse_evaluation_derives_verdict_not_trusting_model():
    # _parse_evaluation must derive the verdict from data, not from the model's verdict
    # field — prevents APPROVED slipping through when artifacts are also listed.
    raw = json.dumps({
        "artifacts": ["Gata is wearing a hat"],
        "is_funny": True,
        "funny_notes": "Still funny despite the hat.",
        "verdict": "APPROVED",  # model claims APPROVED but there are artifacts
    })
    result = _parse_evaluation(raw, "gemini-2.5-pro")
    assert result.verdict == "REJECTED"


def test_parse_evaluation_approved_only_when_both_conditions_pass():
    # _parse_evaluation sets APPROVED only when artifacts is empty AND is_funny is true.
    raw = json.dumps({
        "artifacts": [],
        "is_funny": True,
        "funny_notes": "Lands well.",
        "verdict": "APPROVED",
    })
    result = _parse_evaluation(raw, "gemini-2.5-flash")
    assert result.verdict == "APPROVED"


# ---------------------------------------------------------------------------
# Provider fallback
# ---------------------------------------------------------------------------


def test_evaluate_falls_back_on_api_error(tmp_path):
    # evaluate() must try the next provider when the current one raises an API error.
    image_path = _write_fake_image(tmp_path)
    p1 = _make_provider(
        "gemini-2.5-pro",
        side_effect=ServerError(503, {"error": {"message": "overloaded"}}),
    )
    p2 = _make_provider("gemini-2.5-flash", _make_response(_APPROVED_JSON))
    result, _tel = evaluate(image_path, _CONCEPT, _BRIEF, [p1, p2])
    assert result.verdict == "APPROVED"
    assert p1.client.models.generate_content.call_count == 1
    assert p2.client.models.generate_content.call_count == 1


def test_evaluate_exhausts_all_providers_before_failing_open(tmp_path):
    # evaluate() must try every provider in the chain before defaulting to APPROVED.
    image_path = _write_fake_image(tmp_path)
    providers = [
        _make_provider(
            m,
            side_effect=ServerError(503, {"error": {"message": "overloaded"}}),
        )
        for m in _DEFAULT_MODELS
    ]
    result, _tel = evaluate(image_path, _CONCEPT, _BRIEF, providers)
    assert all(p.client.models.generate_content.call_count == 1 for p in providers)
    assert result.verdict == "APPROVED"


# ---------------------------------------------------------------------------
# Fail open — all providers exhausted or parse failure
# ---------------------------------------------------------------------------


def test_evaluate_all_providers_exhausted_defaults_to_approved(tmp_path):
    # evaluate() must default to APPROVED rather than raising when all providers fail,
    # so a transient API outage never blocks the pipeline.
    image_path = _write_fake_image(tmp_path)
    providers = [
        _make_provider(m, side_effect=Exception("network error"))
        for m in _DEFAULT_MODELS
    ]
    result, _tel = evaluate(image_path, _CONCEPT, _BRIEF, providers)
    assert result.verdict == "APPROVED"
    assert "unavailable" in result.funny_notes


def test_evaluate_parse_failure_defaults_to_approved(tmp_path):
    # _parse_evaluation must default to APPROVED on malformed JSON so the pipeline
    # is not blocked by a garbled model response.
    image_path = _write_fake_image(tmp_path)
    bad_resp = MagicMock()
    bad_resp.text = "this is not JSON at all"
    bad_resp.usage_metadata = None
    providers = _make_providers(bad_resp)
    result, _tel = evaluate(image_path, _CONCEPT, _BRIEF, providers)
    assert result.verdict == "APPROVED"


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------


def test_evaluate_returns_telemetry_with_correct_agent_name(tmp_path):
    # evaluate() must tag its AgentTelemetry with agent_name="Image Evaluator".
    image_path = _write_fake_image(tmp_path)
    providers = _make_providers(_make_response(_APPROVED_JSON))
    _result, tel = evaluate(image_path, _CONCEPT, _BRIEF, providers)
    assert tel.agent_name == "Image Evaluator"


def test_evaluate_records_model_used(tmp_path):
    # evaluate() must record which Gemini model produced the evaluation in model_used.
    image_path = _write_fake_image(tmp_path)
    providers = _make_providers(_make_response(_APPROVED_JSON))
    result, _tel = evaluate(image_path, _CONCEPT, _BRIEF, providers)
    assert result.model_used == _DEFAULT_MODELS[0]


def test_evaluate_records_token_usage(tmp_path):
    # evaluate() must record token counts from Gemini usage_metadata in telemetry.
    image_path = _write_fake_image(tmp_path)
    meta = MagicMock()
    meta.prompt_token_count = 200
    meta.candidates_token_count = 80
    providers = _make_providers(_make_response(_APPROVED_JSON, usage_metadata=meta))
    _result, tel = evaluate(image_path, _CONCEPT, _BRIEF, providers)
    assert tel.calls[0].input_tokens == 200
    assert tel.calls[0].output_tokens == 80


# ---------------------------------------------------------------------------
# Prompt content
# ---------------------------------------------------------------------------


def test_eval_prompt_contains_target_audience():
    # _build_eval_prompt must include the target audience so the model can judge
    # funniness relative to who will actually see the cartoon.
    prompt = _build_eval_prompt(_CONCEPT, _BRIEF, None)
    assert _BRIEF.target_audience in prompt


def test_eval_prompt_contains_cultural_angle():
    # _build_eval_prompt must include the cultural angle so the model checks whether
    # the image carries the right satirical context for the community.
    prompt = _build_eval_prompt(_CONCEPT, _BRIEF, None)
    assert _BRIEF.cultural_angle in prompt


def test_eval_prompt_contains_gata_character():
    # _build_eval_prompt must include Gata's character description so the model can
    # detect character integrity failures such as wrong colour or added accessories.
    prompt = _build_eval_prompt(_CONCEPT, _BRIEF, None)
    assert "calico" in prompt.lower()


def test_eval_prompt_includes_concept_text():
    # _build_eval_prompt must include the intended concept so the model can check
    # whether load-bearing visual elements are actually present in the image.
    prompt = _build_eval_prompt(_CONCEPT, _BRIEF, None)
    assert "Renda" in prompt


def test_eval_prompt_multi_panel_includes_each_scene():
    # _build_eval_prompt must expand multi-panel concepts into per-panel scenes so
    # the model evaluates each panel's content individually.
    prompt = _build_eval_prompt(_MULTI_CONCEPT, _BRIEF, _LAYOUT_2H)
    assert "Gata reads headline" in prompt
    assert "Gata flips the board" in prompt


def test_eval_prompt_multi_panel_mentions_layout():
    # _build_eval_prompt must state the panel count and direction when a layout is
    # provided so the model knows the expected image format.
    prompt = _build_eval_prompt(_MULTI_CONCEPT, _BRIEF, _LAYOUT_2H)
    assert "2" in prompt
    assert "horizontal" in prompt


# ---------------------------------------------------------------------------
# Concept fidelity check (Stage 023)
# ---------------------------------------------------------------------------

_FIDELITY_FAILURE_JSON = {
    "artifacts": [
        "Fidelity failure: intended chicken-joke spider diagram,"
        " image shows British weather cycle"
    ],
    "is_funny": True,
    "funny_notes": "Weather cycle is funny but it is not the approved concept.",
    "verdict": "REJECTED",
}


def test_eval_prompt_contains_fidelity_check_section():
    # _build_eval_prompt must include an explicit fidelity check section so the model
    # knows to compare the image against the specific intended concept, not just theme.
    prompt = _build_eval_prompt(_CONCEPT, _BRIEF, None)
    assert "CONCEPT FIDELITY CHECK" in prompt


def test_eval_prompt_warns_thematic_similarity_not_sufficient():
    # _build_eval_prompt must explicitly state that thematic similarity is not enough,
    # so the model catches cases where the image model substituted a different visual.
    prompt = _build_eval_prompt(_CONCEPT, _BRIEF, None)
    assert "Thematic similarity is NOT sufficient" in prompt


def test_eval_prompt_instructs_fidelity_failure_prefix():
    # _build_eval_prompt must instruct the model to prefix wrong-concept entries with
    # "Fidelity failure:" so they are distinguishable from technical artifacts in logs.
    prompt = _build_eval_prompt(_CONCEPT, _BRIEF, None)
    assert "Fidelity failure" in prompt


def test_evaluate_rejected_on_fidelity_failure(tmp_path):
    # evaluate() must return REJECTED when Gemini reports a fidelity failure, so a
    # plausible-but-wrong image triggers regeneration just like a technical artifact.
    image_path = _write_fake_image(tmp_path)
    providers = _make_providers(_make_response(_FIDELITY_FAILURE_JSON))
    result, _tel = evaluate(image_path, _CONCEPT, _BRIEF, providers)
    assert result.verdict == "REJECTED"
    assert any("Fidelity failure" in a for a in result.artifacts)


def test_evaluate_fidelity_failure_preserved_in_artifacts(tmp_path):
    # evaluate() must preserve the full fidelity failure description in the artifacts
    # list so operators can diagnose exactly what the image model substituted.
    image_path = _write_fake_image(tmp_path)
    providers = _make_providers(_make_response(_FIDELITY_FAILURE_JSON))
    result, _tel = evaluate(image_path, _CONCEPT, _BRIEF, providers)
    assert "chicken-joke spider diagram" in result.artifacts[0]


def test_eval_prompt_fidelity_section_precedes_funniness():
    # The fidelity check must appear before the funniness check in the prompt so the
    # model resolves the objective question (right concept?) before the subjective one.
    prompt = _build_eval_prompt(_CONCEPT, _BRIEF, None)
    fidelity_pos = prompt.index("CONCEPT FIDELITY CHECK")
    funniness_pos = prompt.index("FUNNINESS CHECK")
    assert fidelity_pos < funniness_pos


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def test_evaluate_logs_verdict_at_info(tmp_path, caplog):
    # evaluate() must log the verdict at INFO level so operators can trace evaluation
    # results without enabling DEBUG.
    image_path = _write_fake_image(tmp_path)
    providers = _make_providers(_make_response(_APPROVED_JSON))
    caplog.set_level(logging.INFO, logger="agents.agent_image_evaluator")
    evaluate(image_path, _CONCEPT, _BRIEF, providers)
    assert any("APPROVED" in r.message for r in caplog.records)
