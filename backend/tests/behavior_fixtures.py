"""Synthetic escape configuration over the fixture circuit (no dataset, no biology)."""

from __future__ import annotations

from app.behavior import EscapeCircuitConfig
from app.behavior.escape_config import DecoderParams, ExtractorParams, StimulusMappingParams
from app.circuits import Circuit, CircuitExtractor
from tests.circuit_fixtures import fixture_graph

SYNTHETIC_CIRCUIT_ID = "synthetic_escape_fixture"


def synthetic_escape_config(**overrides) -> EscapeCircuitConfig:
    base = dict(
        config_version="synthetic_escape_test",
        circuit_id=SYNTHETIC_CIRCUIT_ID,
        synthetic=True,
        dataset="synthetic_tiny_connectome",
        dataset_version="fixture-v1",
        canonical_selection_rule="all fixture neurons (synthetic; no status filter)",
        biological_status="UNSUPPORTED",
        research_document="none (synthetic test)",
        sensory_cell_types=["SYN_input_A", "SYN_input_B"],
        output_cell_types=["SYN_output_L", "SYN_output_R"],
        sensory_groups={"L": ["syn_001"], "R": ["syn_002"]},
        output_groups={"L": ["syn_006"], "R": ["syn_007"]},
        extractor=ExtractorParams(
            max_hops=2, min_synapses=1, max_neurons=50, restrict_to_target_paths=True
        ),
        stimulus_mapping=StimulusMappingParams(
            mapping_gain=1.0, duration_steps=5, rule="synthetic test rule"
        ),
        decoder=DecoderParams(min_output_spikes=1, rule="synthetic test rule"),
        simulation_steps=20,
    )
    base.update(overrides)
    return EscapeCircuitConfig(**base)


def synthetic_escape_circuit(config: EscapeCircuitConfig | None = None) -> Circuit:
    config = config or synthetic_escape_config()
    return CircuitExtractor(fixture_graph()).extract(
        config.extractor_config(), circuit_id=config.circuit_id
    )
