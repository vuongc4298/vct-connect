"""Start a manual Container Apps migration job and await its exact execution."""

import argparse
import json
import subprocess
import time


class ExecutionNotVisible(RuntimeError):
    """The new execution has not propagated to the read endpoint yet."""


def az(*arguments: str) -> dict:
    result = subprocess.run(
        ["az", "containerapp", "job", *arguments, "--output", "json", "--only-show-errors"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        if arguments[:2] == ("execution", "show") and any(
            marker in result.stderr.lower() for marker in ("not found", "could not be found", "404")
        ):
            raise ExecutionNotVisible("Migration execution is not visible yet")
        raise RuntimeError("Container Apps job operation failed")
    return json.loads(result.stdout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="vct-connect-dev-migrate")
    parser.add_argument("--resource-group", default="VCT_Connect_Service_Bus")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    execution = az("start", "--name", args.name, "--resource-group", args.resource_group)
    execution_name = execution.get("name")
    if not execution_name:
        raise RuntimeError("Migration start returned no execution name")
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        try:
            state = az(
                "execution", "show", "--name", args.name,
                "--resource-group", args.resource_group,
                "--job-execution-name", execution_name,
            ).get("properties", {}).get("status")
        except ExecutionNotVisible:
            state = None
        if state == "Succeeded":
            print("Migration job succeeded.")
            return 0
        if state in {"Failed", "Stopped"}:
            print(f"Migration job ended with status {state}.")
            return 1
        time.sleep(10)
    print("Migration job timed out.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
