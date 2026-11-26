"""The ``agriscale`` command line.

A notebook is a poor way to check an installation: it gives no exit code,
needs its paths edited by hand, and says nothing useful when a model engine
is missing. This gives one command per question instead.

``agriscale engines`` answers the first question a student on a locked-down
machine will ask -- "is my install found?" -- and tells apart the two ways
it can fail: ModFileGen cannot see the engine, or the engine itself is
incomplete.
"""

import argparse
import json
import sys

from modfilegen import engines
from modfilegen.version import __version__

#: Printed beside an engine, so the line reads on its own.
STATUS_TEXT = {
    "ok": "ok",
    "missing": "not found",
    "incomplete": "incomplete",
    "not executable": "not executable",
}


def engines_report(stream=None, as_json=False):
    """Report where each model engine was found, and whether it can run.

    ``stream`` is resolved at call time: a default of ``sys.stdout`` would be
    bound at import and would keep writing to the original stream whatever
    the caller redirected.
    """
    stream = sys.stdout if stream is None else stream
    findings = [engines.inspect(name) for name in sorted(engines.ENGINES)]

    if as_json:
        json.dump(findings, stream, indent=2)
        stream.write("\n")
        return 0

    width = max(len(finding["label"]) for finding in findings)
    stream.write(f"{'Engine'.ljust(width)}  {'Status'.ljust(14)}  Found via\n")
    stream.write(f"{'-' * width}  {'-' * 14}  {'-' * 40}\n")
    for finding in findings:
        status = STATUS_TEXT.get(finding["status"], finding["status"])
        stream.write(
            f"{finding['label'].ljust(width)}  {status.ljust(14)}  "
            f"{finding['origin']}\n"
        )
        if finding["status"] != "missing":
            stream.write(f"{' ' * width}  {' ' * 14}  {finding['executable']}\n")

    problems = [finding for finding in findings if finding["status"] != "ok"]
    if not problems:
        stream.write("\nAll engines are in place.\n")
        return 0

    stream.write("\n")
    for finding in problems:
        stream.write(f"{finding['label']}: ")
        if finding["status"] == "missing":
            stream.write("not found. " + engines.describe(finding["engine"]) + "\n")
        elif finding["status"] == "incomplete":
            missing = ", ".join(finding["missing_companions"])
            stream.write(
                f"found at {finding['executable']}, but {missing} is not beside "
                "it. Point at the executable inside the engine's own install "
                "directory rather than at a copy of the binary.\n"
            )
        else:
            stream.write(
                f"{finding['executable']} is not executable. "
                "chmod +x it, or point at the right file.\n"
            )
    # Missing engines are a normal state: file generation needs none of them.
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="agriscale",
        description="Generate and run crop model input files.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command")

    engines_command = commands.add_parser(
        "engines",
        help="show where each model engine was found, and what is missing",
    )
    engines_command.add_argument(
        "--json", action="store_true", help="machine-readable output"
    )
    return parser


def main(argv=None):
    parser = build_parser()
    arguments = parser.parse_args(argv)

    if arguments.command == "engines":
        return engines_report(as_json=arguments.json)

    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
