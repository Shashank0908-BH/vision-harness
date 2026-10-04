"""Read-only Daytona access and persistence checks; never creates cloud resources."""

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

from daytona.common.errors import DaytonaNotFoundError
from dotenv import dotenv_values

from infra.daytona.manage import ROOT, client, config, info, owned, write

REQUIRED = ("write:sandboxes", "write:snapshots", "read:volumes", "write:volumes")


def permissions():
    values = dotenv_values(ROOT / ".env")
    key = values.get("DAYTONA_API_KEY") or os.environ.get("DAYTONA_API_KEY")
    if not key:
        raise ValueError("DAYTONA_API_KEY is not set")
    base = (values.get("DAYTONA_API_URL") or "https://app.daytona.io/api").rstrip("/")
    request = urllib.request.Request(
        base + "/api-keys/current", headers={"Authorization": "Bearer " + key},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            # The response includes the key value: return only permission names.
            result = json.load(response)
        granted = result.get("permissions", [])
        return {"verified": True, "granted": granted,
                "missing_for_durable_lab": [p for p in REQUIRED if p not in granted]}
    except urllib.error.HTTPError as error:
        return {"verified": False, "http_status": error.code}
    except (urllib.error.URLError, TimeoutError):
        return {"verified": False, "error": "Permission endpoint unavailable"}


def inspect_resource(call):
    try:
        resource = call()
        return {"exists": True, "name": resource.name, "state": str(resource.state)}
    except DaytonaNotFoundError:
        return {"exists": False}
    except Exception as error:
        # Do not serialize API response bodies, which may contain sensitive data.
        return {"exists": None, "error_type": type(error).__name__}


def main():
    cfg = config()
    daytona = client()
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "permissions": permissions(),
        "snapshot": inspect_resource(lambda: daytona.snapshot.get(cfg["snapshot"])),
        "volume": inspect_resource(lambda: daytona.volume.get(cfg["volume"], create=False)),
        "sandbox": inspect_resource(lambda: owned(daytona)),
        "gpu_filesystem_survives_stop": False,
        "mounted_volume_verified": False,
        "write_operations_tested": False,
    }
    if report["sandbox"]["exists"]:
        box = owned(daytona)
        report["sandbox"].update(info(box))
        # Do not start a stopped sandbox just to inspect it.
        if str(box.state).lower().split(".")[-1] == "started":
            check = box.process.exec("mountpoint -q /persist", timeout=15)
            report["mounted_volume_verified"] = check.exit_code == 0
    write("persistence-check.json", report)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
