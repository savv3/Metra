"""Encrypted upload of backups with rclone.

rclone is configured entirely through environment variables passed to the
subprocess, so no config file with credentials is ever written. The backups
go through an rclone "crypt" remote: file contents and names are encrypted
with METRA_BACKUP_ENCRYPTION_PASSWORD before they leave the server.
Secrets are never put on the command line, where other processes could see them.
"""

import os
import subprocess

from .archive import archive_time, is_archive_name

BASE = "SCRREMOTE"
CRYPT = "scrcrypt"
TIMEOUT = 60 * 60
TYPES = {"s3", "sftp", "ftps"}


class RcloneError(Exception):
    pass


class Remote:
    def __init__(self, config, runner=subprocess.run):
        self.config = config
        self.type = config["remote_type"]
        self.runner = runner
        if self.type not in TYPES:
            raise RcloneError(
                f"METRA_BACKUP_REMOTE_TYPE must be one of s3, sftp or ftps, not {self.type!r}."
            )
        if not config["encryption_password"]:
            raise RcloneError("Set METRA_BACKUP_ENCRYPTION_PASSWORD to upload backups.")
        if self.type in ("sftp", "ftps") and not config["host"]:
            raise RcloneError("Set METRA_BACKUP_HOST for SFTP and FTPS backups.")
        self._env = None

    @classmethod
    def from_config(cls, config, runner=subprocess.run):
        return cls(config, runner) if config["remote_type"] else None

    def describe(self):
        """Where backups go, for the status panel. Never includes credentials."""
        place = self.config["s3_endpoint"] if self.type == "s3" else self.config["host"]
        parts = [self.type.upper(), place, self.config["remote_path"]]
        return " ".join(part for part in parts if part) + " (encrypted)"

    def secrets(self):
        keys = ["encryption_password", "password", "s3_secret_access_key", "s3_access_key_id"]
        return [self.config[key] for key in keys if self.config[key]]

    def scrub(self, text):
        for secret in self.secrets():
            text = text.replace(secret, "***")
        return text

    def _obscure(self, value):
        # rclone stores passwords "obscured"; "-" reads the value from stdin.
        result = self._call(["rclone", "obscure", "-"], input=value)
        return result.strip()

    def env(self):
        if self._env is not None:
            return self._env
        c = self.config
        options = {}
        if self.type == "s3":
            options = {
                "TYPE": "s3",
                "PROVIDER": c["s3_provider"],
                "ENV_AUTH": "false",
                "ACCESS_KEY_ID": c["s3_access_key_id"],
                "SECRET_ACCESS_KEY": c["s3_secret_access_key"],
                "ENDPOINT": c["s3_endpoint"],
                "REGION": c["s3_region"],
            }
        else:
            options = {
                "TYPE": "sftp" if self.type == "sftp" else "ftp",
                "HOST": c["host"],
                "USER": c["user"],
                "PORT": c["port"],
            }
            if self.type == "ftps":
                options["EXPLICIT_TLS"] = "true"
            if c["password"]:
                options["PASS"] = self._obscure(c["password"])
            if self.type == "sftp" and c["sftp_key_file"]:
                options["KEY_FILE"] = c["sftp_key_file"]
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("RCLONE_", "METRA_BACKUP_", "SCR_BACKUP_"))
        }
        env.update({f"RCLONE_CONFIG_{BASE}_{k}": v for k, v in options.items() if v})
        env.update(
            {
                f"RCLONE_CONFIG_{CRYPT.upper()}_TYPE": "crypt",
                f"RCLONE_CONFIG_{CRYPT.upper()}_REMOTE": f"{BASE.lower()}:{c['remote_path']}",
                f"RCLONE_CONFIG_{CRYPT.upper()}_PASSWORD": self._obscure(c["encryption_password"]),
            }
        )
        self._env = env
        return env

    def _call(self, command, input=None, env=None):
        try:
            result = self.runner(
                command,
                input=input,
                env=env,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
                check=True,
            )
        except FileNotFoundError:
            raise RcloneError("rclone is not installed.") from None
        except subprocess.CalledProcessError as error:
            message = (error.stderr or "").strip() or f"exit code {error.returncode}"
            raise RcloneError(self.scrub(f"rclone {command[1]} failed: {message}")) from None
        except subprocess.TimeoutExpired:
            raise RcloneError(f"rclone {command[1]} took longer than an hour.") from None
        return result.stdout

    def run(self, *args):
        return self._call(["rclone", *args], env=self.env())

    def upload(self, path):
        self.run("copyto", str(path), f"{CRYPT}:{path.name}")

    def download(self, name, destination):
        self.run("copyto", f"{CRYPT}:{name}", str(destination))

    def list(self):
        """Archive names on the remote, oldest first."""
        output = self.run("lsf", "--files-only", f"{CRYPT}:")
        names = (name.strip() for name in output.splitlines())
        return sorted((name for name in names if is_archive_name(name)), key=archive_time)

    def prune(self, keep):
        names = self.list()
        old = names[:-keep] if keep > 0 else names
        for name in old:
            self.run("deletefile", f"{CRYPT}:{name}")
        return old
