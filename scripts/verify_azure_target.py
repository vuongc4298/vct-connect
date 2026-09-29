"""Read-only guard for the approved development subscription and existing queue."""

import json
import os
import subprocess

SUBSCRIPTION = "93bd5d96-c7a2-4072-9aa3-458ab6132d92"
RESOURCE_GROUP = "VCT_Connect_Service_Bus"
NAMESPACE = "vct-connect-standard"
QUEUE = "vct-analyse"


def az_json(*arguments: str) -> dict:
    result = subprocess.run(
        [os.getenv("AZ_CLI", "az"), *arguments, "--output", "json", "--only-show-errors"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Azure preflight command failed: {' '.join(arguments[:3])}")
    return json.loads(result.stdout)


def verify(account: dict, group: dict, namespace: dict, queue: dict) -> None:
    checks = (
        (account.get("id") == SUBSCRIPTION, "subscription"),
        (group.get("name", "").lower() == RESOURCE_GROUP.lower(), "resource group"),
        (group.get("location", "").lower() == "southeastasia", "resource group region"),
        (namespace.get("name") == NAMESPACE, "Service Bus namespace"),
        (namespace.get("location", "").lower() == "southeastasia", "Service Bus region"),
        (namespace.get("sku", {}).get("name") == "Standard", "Service Bus Standard SKU"),
        (queue.get("name") == QUEUE, "Service Bus queue"),
        (queue.get("status") == "Active", "active queue"),
        (queue.get("lockDuration") == "PT1M", "one-minute queue lock"),
        (queue.get("maxDeliveryCount") == 10, "queue delivery limit"),
        (queue.get("requiresDuplicateDetection") is False, "queue duplicate detection"),
    )
    failures = [label for passed, label in checks if not passed]
    if failures:
        raise ValueError("Azure target mismatch: " + ", ".join(failures))


def main() -> int:
    try:
        verify(
            az_json("account", "show"),
            az_json("group", "show", "--name", RESOURCE_GROUP),
            az_json("servicebus", "namespace", "show", "--resource-group", RESOURCE_GROUP, "--name", NAMESPACE),
            az_json("servicebus", "queue", "show", "--resource-group", RESOURCE_GROUP, "--namespace-name", NAMESPACE, "--name", QUEUE),
        )
    except (RuntimeError, ValueError, KeyError) as exc:
        print(exc)
        return 1
    print("Approved Azure target and existing Standard queue verified; no queue settings changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
