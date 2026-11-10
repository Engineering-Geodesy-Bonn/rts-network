"""Uploads a measurement CSV log of a worker into an existing job (recovery tool).

The worker keeps every measurement in its outbox until the API confirmed it, so this is
normally not needed. It helps if a worker's disk was moved to another machine, or to restore
a job from the CSV logs (measurements/<job_id>.csv on the worker).

The upload is idempotent: measurements already stored are skipped, so it can be repeated.

    python scripts/import_csv.py --api http://192.168.0.101:8000 measurements/<job_id>.csv
    python scripts/import_csv.py --job <job_id> some_log.csv
"""

import argparse
import csv
import json
import os
import sys
import urllib.request

BATCH = 2000


def post(api: str, job_id: str, rows: list[list]) -> dict:
    body = json.dumps({"job_id": job_id, "rows": rows}).encode()
    request = urllib.request.Request(f"{api}/worker/measurements", data=body, method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv", help="CSV log of a worker (columns ref_time, ts_time, h_angle, v_angle, distance, num_chars, ...)")
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="API address (default %(default)s)")
    parser.add_argument("--job", help="Job id (default: the file name of a worker log)")
    args = parser.parse_args()

    job_id = args.job or os.path.splitext(os.path.basename(args.csv))[0]
    rows = []
    with open(args.csv) as f:
        reader = csv.DictReader(f, skipinitialspace=True)
        for index, r in enumerate(reader):
            seq = int(r["seq"]) if r.get("seq") not in (None, "") else index  # older logs: line order
            request_time = float(r["request_time"]) if r.get("request_time") not in (None, "") else None
            rows.append([
                seq, float(r["ref_time"]), float(r["ts_time"]), request_time, int(float(r["num_chars"])),
                int(float(r["geocom_return_code"])), int(float(r["rpc_return_code"])),
                float(r["distance"]), float(r["h_angle"]), float(r["v_angle"]),
            ])
    inserted = 0
    for start in range(0, len(rows), BATCH):
        result = post(args.api.rstrip("/"), job_id, rows[start:start + BATCH])
        if result.get("rejected"):
            sys.exit(f"The API rejected the measurements: {result['rejected']} (does job {job_id} exist?)")
        inserted += result["inserted"]
    print(f"{len(rows)} measurements in the file, {inserted} new ones stored in job {job_id}")


if __name__ == "__main__":
    main()
