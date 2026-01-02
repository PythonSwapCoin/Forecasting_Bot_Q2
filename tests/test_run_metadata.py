from run_metadata import collect_runtime_metadata
from logging_utils import RunLogger


def test_collect_runtime_metadata_minimal():
    logger = RunLogger()
    metadata = collect_runtime_metadata(run_kind="unit_test", run_config=None, logger=logger)
    assert metadata["run_kind"] == "unit_test"
    assert "timestamp_utc" in metadata
    assert "models" in metadata
    assert "providers" in metadata
    assert metadata.get("config") is None or isinstance(metadata.get("config"), dict)
