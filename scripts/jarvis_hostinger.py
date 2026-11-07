"""Read-only Hostinger inventory command; tokens come only from HOSTINGER_API_TOKEN.

Choose --check-config (offline presence only) or --live (one HTTPS inventory read).
Both modes require a fresh relative JSON output path under an existing --root.
"""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from control_tower.hostinger_live import check_configuration, read_inventory_from_environment


MAX_REPORT_BYTES = 16 * 1024
_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z")


class _SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's normal unknown-argument error can echo a pasted credential.
        raise ValueError("invalid_arguments")


def _reserve_output(root_value, relative):
    """Securely open a fresh file before any credential check or network read.

    Existing parent directories are required. Descriptor-relative traversal rejects
    symlink parents and O_EXCL prevents replacement of an existing final name.
    """
    if (type(relative) is not str or not 1 <= len(relative) <= 256 or "\\" in relative
            or relative.startswith("/") or not relative.endswith(".json")):
        raise ValueError("invalid_output_path")
    parts = relative.split("/")
    if not 1 <= len(parts) <= 6 or any(not _COMPONENT.fullmatch(part) or part in (".", "..") for part in parts):
        raise ValueError("invalid_output_path")
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY") or os.open not in os.supports_dir_fd:
        raise ValueError("secure_output_platform_required")
    root = Path(root_value).resolve(strict=True)
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        descriptor = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
        return descriptor, directory, parts[-1]
    except Exception:
        os.close(directory)
        raise


def _discard_owned_file(descriptor, directory, name):
    try:
        current = os.stat(name, dir_fd=directory, follow_symlinks=False)
        opened = os.fstat(descriptor)
        if stat.S_ISREG(current.st_mode) and (current.st_dev, current.st_ino) == (opened.st_dev, opened.st_ino):
            os.unlink(name, dir_fd=directory)
    except OSError:
        pass


def _write_report(descriptor, record):
    payload = (json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    if len(payload) > MAX_REPORT_BYTES:
        raise ValueError("report_size_limit")
    remaining = memoryview(payload)
    while remaining:
        amount = os.write(descriptor, remaining)
        if amount <= 0:
            raise OSError("report_write_failed")
        remaining = remaining[amount:]
    os.fsync(descriptor)


def main(argv=None):
    descriptor = directory = None
    name = None
    finished = False
    try:
        parser = _SafeParser(description=__doc__, allow_abbrev=False)
        parser.add_argument("--root", default=str(ROOT))
        parser.add_argument("--out", required=True)
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--check-config", action="store_true")
        mode.add_argument("--live", action="store_true")
        args = parser.parse_args(argv)
        descriptor, directory, name = _reserve_output(args.root, args.out)
        result = check_configuration() if args.check_config else read_inventory_from_environment(live=True)
        _write_report(descriptor, {"schema_version": 1, **result})
        finished = True
        summary = {"status": result["status"], "report_written": True,
                   "connection_status": result["connection_status"],
                   "live_access_verified": result["live_access_verified"],
                   "transport_calls": result["transport_calls"], "writes_requested": 0}
        if args.check_config:
            summary["credential_present"] = result["credential_present"]
        print(json.dumps(summary, sort_keys=True))
        if args.check_config:
            return 0 if result["credential_present"] else 2
        return 0 if result["status"] == "response_validated" else 1
    except Exception:
        # No raw argument, file path, provider response or exception is printed.
        print(json.dumps({"status": "command_failed", "report_written": False}), file=sys.stderr)
        return 1
    finally:
        if descriptor is not None:
            if not finished:
                _discard_owned_file(descriptor, directory, name)
            os.close(descriptor)
        if directory is not None:
            os.close(directory)


if __name__ == "__main__":
    raise SystemExit(main())
