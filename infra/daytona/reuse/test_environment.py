"""Checks for the boundaries that make a shared-workspace benchmark meaningful."""

import pytest
from harbor.models.task.config import NetworkMode, NetworkPolicy

from infra.daytona.reuse.environment import WorkspaceEnvironment


def environment(tmp_path):
    env = object.__new__(WorkspaceEnvironment)
    env.root = tmp_path
    env.source = tmp_path / "frozen"
    env._network_policy = NetworkPolicy(network_mode="public")
    return env


def test_transfers_reject_escape(tmp_path):
    env = environment(tmp_path)
    for path in ("/root/key", "/opt/checkpoints/model", "../output", "/output/../../root/key"):
        with pytest.raises(ValueError):
            env.local_path(path)
    (tmp_path / "output").symlink_to("/etc")
    with pytest.raises(ValueError):
        env.local_path("/output/passwd")


def test_agent_mounts_do_not_expose_coordinator_or_previous_runs(tmp_path):
    env = environment(tmp_path)
    args = env.command("true", "/app")
    for hidden in ("/root", "/persist", "/workspace", "/run", "/var"):
        assert hidden not in args
    assert args[args.index("--cap-drop") + 1] == "ALL"
    assert "--unshare-pid" in args
    opt = args.index("/opt")
    assert args[opt - 1] == "--ro-bind"
    assert args[args.index("--proc") + 1] == "/proc"


def test_verifier_has_no_network(tmp_path):
    env = environment(tmp_path)
    env._network_policy.network_mode = NetworkMode.NO_NETWORK
    assert "--unshare-net" in env.command("true", "/app")


def test_only_private_trial_paths_are_transfer_targets(tmp_path):
    env = environment(tmp_path)
    assert env.local_path("/logs/agent/answer.json") == tmp_path / "logs/agent/answer.json"
    assert env.local_path("/tests/reference.npz").is_relative_to(tmp_path)
    assert env.local_path("/output").is_relative_to(tmp_path)
