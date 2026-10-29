"""Compile local portfolio missions and editorial briefs; never dispatch work."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from control_tower.campaigns import campaign_briefs
from control_tower.missions import compile_mission, export_role_draft, validate_mission
from control_tower.network_contract import canonical, load_packet
from control_tower.portfolio import portfolio_catalog


def _resolve(path, *, strict=False):
    try:
        return path.resolve(strict=strict)
    except RuntimeError:
        raise ValueError("path cannot be resolved") from None


def _local(root, locator):
    if not locator or Path(locator).is_absolute():
        raise ValueError("paths must be relative to the workspace root")
    path = _resolve(root / locator)
    if not path.is_relative_to(root) or path == root:
        raise ValueError("path leaves the workspace root")
    return path


def _write(path, record):
    content = canonical(record) + b"\n"
    if len(content) > 65536:
        raise ValueError("output exceeds packet limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=".jarvis-portfolio-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        if os.name == "posix":
            # Flush the published name before reporting success. If this fails,
            # retain the complete artifact and require reconciliation, not overwrite.
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    commands = parser.add_subparsers(dest="command", required=True)
    catalog = commands.add_parser("catalog")
    catalog.add_argument("--out", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("--request", required=True)
    plan.add_argument("--mission", required=True)
    plan.add_argument("--source-revision", required=True)
    plan.add_argument("--out", required=True)
    role = commands.add_parser("export-role")
    role.add_argument("--mission-file", required=True)
    role.add_argument("--role", required=True)
    role.add_argument("--out", required=True)
    manifest = commands.add_parser("export-swarm")
    manifest.add_argument("--mission-file", required=True)
    manifest.add_argument("--out", required=True)
    campaign = commands.add_parser("campaign")
    campaign.add_argument("--mission-file", required=True)
    campaign.add_argument("--destination-index", type=int, default=0)
    campaign.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        root = _resolve(Path(args.root), strict=True)
        if not root.is_dir():
            raise ValueError("root must be an existing directory")
        output = _local(root, args.out)
        if output.exists():
            raise ValueError("output already exists; choose a fresh filename")
        if args.command == "catalog":
            result = portfolio_catalog()
        elif args.command == "plan":
            request = load_packet(_local(root, args.request))
            result = compile_mission(request, mission_id=args.mission, source_revision=args.source_revision)
        else:
            mission = load_packet(_local(root, args.mission_file))
            if args.command == "export-role":
                result = export_role_draft(mission, args.role)
            elif args.command == "export-swarm":
                result = validate_mission(mission)["swarm"]
            else:
                result = campaign_briefs(mission, destination_index=args.destination_index)
        _write(output, result)
        print(json.dumps({"saved": str(output.relative_to(root)), "kind": result["kind"],
                          "model_calls": 0, "external_actions": 0}))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc) if type(exc) is ValueError else type(exc).__name__,
                          "external_actions": 0}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
