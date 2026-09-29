"""The two dev deployment phases share one Azure CLI parameter contract."""

import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "deploy_dev.sh"
GIT_BASH = Path("C:/Program Files/Git/bin/bash.exe")
BASH = str(GIT_BASH) if os.name == "nt" and GIT_BASH.exists() else shutil.which("bash")

CONFIG = {
    "GITHUB_RUN_ID": "12345",
    "GITHUB_RUN_ATTEMPT": "2",
    "BACKEND_DIGEST": "sha256:" + "a" * 64,
    "WEB_DIGEST": "sha256:" + "b" * 64,
    "REGISTRY_NAME": "vctregistry",
    "VAULT_NAME": "vct-vault",
    "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": "pk_test_example",
    "CLERK_ISSUER": "https://clerk.example.test",
}


@pytest.fixture
def run_deploy(tmp_path):
    if not BASH:
        pytest.skip("Bash is required for the deployment script")
    fake_az = tmp_path / "az"
    fake_az.write_text("#!/usr/bin/env bash\nprintf '%s\\n' AZ_CALLED \"$@\"\n", encoding="utf-8")
    fake_az.chmod(0o755)

    def run(*args, config=CONFIG):
        env = os.environ.copy()
        env.update(config)
        for key in CONFIG.keys() - config.keys():
            env.pop(key, None)
        env["PATH"] = str(tmp_path) + os.pathsep + env["PATH"]
        return subprocess.run(
            [BASH, str(SCRIPT), *args], cwd=ROOT, env=env,
            capture_output=True, text=True, check=False,
        )

    return run


@pytest.mark.parametrize(
    ("phase", "name", "enabled"),
    [("baseline", "vct-base-12345-2", "false"),
     ("activation", "vct-active-12345-2", "true")],
)
def test_phase_passes_exact_deployment_contract(run_deploy, phase, name, enabled):
    result = run_deploy(phase)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "AZ_CALLED", "deployment", "group", "create",
        "--resource-group", "VCT_Connect_Service_Bus",
        "--name", name,
        "--template-file", "infra/azure/main.bicep",
        "--parameters",
        f"backendImageDigest={CONFIG['BACKEND_DIGEST']}",
        f"webImageDigest={CONFIG['WEB_DIGEST']}",
        f"enableProcessing={enabled}",
        f"registryName={CONFIG['REGISTRY_NAME']}",
        f"vaultName={CONFIG['VAULT_NAME']}",
        f"clerkPublishableKey={CONFIG['NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY']}",
        f"clerkIssuer={CONFIG['CLERK_ISSUER']}",
        "--only-show-errors", "--output", "none",
    ]


@pytest.mark.parametrize("missing", CONFIG)
def test_missing_configuration_fails_before_azure(run_deploy, missing):
    config = {key: value for key, value in CONFIG.items() if key != missing}
    result = run_deploy("baseline", config=config)
    assert result.returncode != 0
    assert result.stdout == ""
    assert f"Missing required deployment variable: {missing}" in result.stderr


@pytest.mark.parametrize("args", [(), ("unknown",), ("baseline", "extra")])
def test_invalid_phase_fails_before_azure(run_deploy, args):
    result = run_deploy(*args)
    assert result.returncode != 0
    assert result.stdout == ""
    assert "Usage:" in result.stderr or "Invalid deployment phase" in result.stderr


def test_invalid_digest_fails_before_azure(run_deploy):
    result = run_deploy("activation", config={**CONFIG, "WEB_DIGEST": "latest"})
    assert result.returncode != 0
    assert result.stdout == ""
    assert "Invalid image digest" in result.stderr


@pytest.mark.parametrize("identifier", ["GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"])
@pytest.mark.parametrize("invalid", ["abc", "1-2"])
def test_nonnumeric_run_identifier_fails_before_azure(run_deploy, identifier, invalid):
    result = run_deploy("baseline", config={**CONFIG, identifier: invalid})
    assert result.returncode != 0
    assert result.stdout == ""
    assert "Invalid deployment run identifier" in result.stderr


def test_workflow_validates_shared_bindings_and_orders_deployment_phases():
    workflow = (ROOT / ".github" / "workflows" / "deploy-dev.yml").read_text(encoding="utf-8")
    job_env = re.search(r"^    env:\n((?:      [^\n]*\n)+)    steps:", workflow, re.MULTILINE)
    assert job_env is not None
    for key, expression in {
        "REGISTRY_NAME": "AZURE_REGISTRY_NAME",
        "VAULT_NAME": "AZURE_KEY_VAULT_NAME",
        "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
        "CLERK_ISSUER": "CLERK_ISSUER",
    }.items():
        assert f"      {key}: ${{{{ vars.{expression} }}}}" in job_env.group(1)
        assert key in workflow.split("- name: Validate deployment configuration", 1)[1].split("- uses: azure/login", 1)[0]

    assert workflow.index("- name: Validate deployment configuration") < workflow.index(
        "- name: Build, push, and resolve image digests"
    )
    for digest in ("BACKEND_DIGEST", "WEB_DIGEST"):
        assert f'echo "{digest}=${digest}" >> "$GITHUB_ENV"' in workflow

    assert (
        workflow.index("run: bash scripts/deploy_dev.sh baseline")
        < workflow.index("run: python scripts/wait_container_job.py")
        < workflow.index("run: bash scripts/deploy_dev.sh activation")
    )
