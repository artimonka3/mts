#!/usr/bin/env python3
"""PostgreSQL custom-format backup and guarded restore through the project Compose DB."""

import argparse
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def database_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,62}", value):
        raise argparse.ArgumentTypeError("Use a simple PostgreSQL database name.")
    return value


def compose(arguments):
    files = [ROOT / "compose.yaml"]
    if not arguments.named_volume:
        files.append(ROOT / "compose.host-storage.yaml")
    return [
        "docker",
        "compose",
        *(item for path in files for item in ["-f", str(path)]),
    ]


def run(arguments, script, *values, stdin=None, stdout=subprocess.PIPE):
    # Script is a fixed internal string; user inputs are separate positional shell arguments.
    result = subprocess.run(
        [*compose(arguments), "exec", "-T", "db", "sh", "-ec", script, "--", *values],
        cwd=ROOT,
        stdin=stdin,
        stdout=stdout,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            "Database operation failed; verify container/database availability."
        )
    return result.stdout


def backup(arguments):
    target = arguments.output.resolve()
    if target.exists():
        raise ValueError("Backup output already exists; choose a new file.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            os.chmod(temporary, 0o600)
            run(
                arguments,
                'exec pg_dump -U "$POSTGRES_USER" -d "${1:-$POSTGRES_DB}" '
                "--format=custom --no-owner --no-privileges",
                arguments.database or "",
                stdout=output,
            )
            output.flush()
            os.fsync(output.fileno())
            # Exclusive linking prevents overwriting a concurrent backup writer.
            os.link(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    print("Backup created with mode 0600. Keep encryption keys separately.")


def restore(arguments):
    source = arguments.input.resolve()
    if not source.is_file():
        raise ValueError("Backup file does not exist.")
    configured = run(arguments, 'printf %s "$POSTGRES_DB"').decode()
    database = arguments.database
    if database in {configured, "postgres", "template0", "template1"}:
        raise ValueError(
            "Restore refuses the configured application DB and system databases."
        )
    exists = (
        run(
            arguments,
            'exec psql -X -w -U "$POSTGRES_USER" -d postgres -Atqc "$1"',
            f"SELECT count(*) FROM pg_database WHERE datname='{database}'",
        ).strip()
        == b"1"
    )
    if not exists:
        run(arguments, 'exec createdb -U "$POSTGRES_USER" "$1"', database)
    count = run(
        arguments,
        'exec psql -X -w -U "$POSTGRES_USER" -d "$1" -Atqc "$2"',
        database,
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'",
    ).strip()
    if count != b"0":
        raise ValueError("Restore refuses a nonempty destination database.")
    with source.open("rb") as stream:
        run(
            arguments,
            'exec pg_restore -U "$POSTGRES_USER" -d "$1" '
            "--single-transaction --exit-on-error --no-owner --no-privileges",
            database,
            stdin=stream,
        )
    print(
        "Restore completed into an empty separate database. Application DB untouched."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--named-volume", action="store_true", help="Use default Compose storage."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    dump = commands.add_parser("backup")
    dump.add_argument("--output", required=True, type=Path)
    dump.add_argument("--database", type=database_name)
    recover = commands.add_parser("restore")
    recover.add_argument("--input", required=True, type=Path)
    recover.add_argument("--database", required=True, type=database_name)
    arguments = parser.parse_args()
    try:
        backup(arguments) if arguments.command == "backup" else restore(arguments)
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
