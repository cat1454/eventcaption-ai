"""The previous flat import paths remain aliases of the grouped modules."""

import importlib

import pytest


@pytest.mark.parametrize(
    ("legacy", "grouped"),
    [
        ("contract", "core.contract"),
        ("ledger", "core.ledger"),
        ("engine", "core.engine"),
        ("evaluation", "core.evaluation"),
        ("stream", "streaming.stream"),
        ("video", "streaming.video"),
        ("processing", "streaming.processing"),
        ("model", "learning.model"),
        ("adapters", "learning.adapters"),
        ("data", "learning.data"),
        ("training_data", "learning.training_data"),
        ("training", "learning.training"),
        ("training_eval", "learning.training_eval"),
        ("inference", "execution.inference"),
        ("budget", "execution.budget"),
        ("runtime", "execution.runtime"),
        ("drive_inventory", "integrations.drive_inventory"),
    ],
)
def test_legacy_module_is_same_object_as_grouped_implementation(legacy, grouped):
    old_module = importlib.import_module(f"eventcaption_ai.{legacy}")
    new_module = importlib.import_module(f"eventcaption_ai.{grouped}")

    assert old_module is new_module
