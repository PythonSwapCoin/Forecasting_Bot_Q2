from config import baseline_config_dict, load_run_config
from research_config import get_research_flags


def test_baseline_profile_defaults():
    cfg = load_run_config()
    assert cfg.profile == "baseline"
    assert cfg.enable_replay_mode is False
    assert cfg.enable_evidence_lake is False
    assert cfg.enable_smoke_tests is False
    assert cfg.enable_diagnostics is True
    assert cfg.research_source
    assert isinstance(cfg.research_flags, dict)
    assert cfg.research_flags["DEFAULT_RESEARCH_SOURCE"] == cfg.research_source


def test_baseline_config_dict_matches():
    cfg_dict = baseline_config_dict()
    for key in ("profile", "enable_replay_mode", "enable_evidence_lake"):
        assert key in cfg_dict
    assert cfg_dict["profile"] == "baseline"
    flags = get_research_flags()
    for flag_key, flag_val in flags.items():
        assert cfg_dict["research_flags"][flag_key] == flag_val
