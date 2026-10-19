"""The deploy scripts, run against fake podman and podman-compose commands."""

import os
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
UPGRADE = ROOT / "docker" / "upgrade.sh"
DEPLOY = ROOT / "scripts" / "deploy.sh"

FAKE_COMPOSE = """#!/bin/sh
echo "podman-compose $*" >>"$FAKE_LOG"
case "$*" in
    *healthz*)
        image=$(sed -n 's/^METRA_IMAGE=//p' .env)
        [ "$image" != "$FAKE_BROKEN" ]
        ;;
esac
"""
FAKE_PODMAN = """#!/bin/sh
echo "podman $*" >>"$FAKE_LOG"
"""


def write_tool(folder, name, body):
    path = folder / name
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def install(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_tool(bin_dir, "podman-compose", FAKE_COMPOSE)
    write_tool(bin_dir, "podman", FAKE_PODMAN)
    write_tool(bin_dir, "sleep", "#!/bin/sh\n")
    folder = tmp_path / "metra"
    folder.mkdir()
    (folder / "compose.yaml").write_text("services: {}\n")
    env = folder / ".env"
    env.write_text("METRA_SECRET_KEY=secret\nMETRA_IMAGE=metra:0.1.0\n")
    env.chmod(0o600)
    (tmp_path / "metra-0.2.0.tar.gz").write_bytes(b"")
    return tmp_path


def upgrade(install, *args, broken=""):
    env = {
        **os.environ,
        "PATH": f"{install / 'bin'}:{os.environ['PATH']}",
        "FAKE_LOG": str(install / "log"),
        "FAKE_BROKEN": broken,
    }
    return subprocess.run(
        ["sh", str(UPGRADE), *args], capture_output=True, text=True, env=env, cwd=install
    )


def test_upgrade_backs_up_and_switches_image(install):
    result = upgrade(install, "0.2.0", "metra-0.2.0.tar.gz", "metra")

    assert result.returncode == 0, result.stderr
    env = install / "metra" / ".env"
    assert env.read_text() == "METRA_SECRET_KEY=secret\nMETRA_IMAGE=metra:0.2.0\n"
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    log = (install / "log").read_text()
    assert log.index("manage.py backup") < log.index("podman load")
    assert "up -d --force-recreate web worker" in log


def test_upgrade_goes_back_when_unhealthy(install):
    result = upgrade(install, "0.2.0", "metra-0.2.0.tar.gz", "metra", broken="metra:0.2.0")

    assert result.returncode == 1
    assert "going back to metra:0.1.0" in result.stderr
    assert "METRA_IMAGE=metra:0.1.0" in (install / "metra" / ".env").read_text()


@pytest.mark.parametrize("version", ["v0.2.0", "0.2.", "latest", ""])
def test_upgrade_refuses_bad_versions(install, version):
    result = upgrade(install, version, "metra-0.2.0.tar.gz", "metra")

    assert result.returncode == 2
    assert not (install / "log").exists()


@pytest.mark.parametrize("args", [[], ["v0.2.0"], ["-d", "/root", "0.2.0"]])
def test_deploy_refuses_bad_arguments(args):
    result = subprocess.run(["sh", str(DEPLOY), *args], capture_output=True, text=True)

    assert result.returncode == 2
