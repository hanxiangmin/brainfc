"""Standard-library HTTP client: queue a demo or a JSON extraction request.

Run the local server first. Then python examples/http_client.py [--request request.json]
"""

import argparse
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8766")
    parser.add_argument("--request", type=Path)
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()

    def request(path, body=None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = Request(
            args.base_url.rstrip("/") + path, data=data, headers={"Content-Type": "application/json"}
        )
        with urlopen(req, timeout=30) as response:
            return json.load(response)

    payload = json.loads(args.request.read_text(encoding="utf-8-sig")) if args.request else {}
    if args.request:
        request("/api/preflight", payload)
    job = request("/api/jobs" if args.request else "/api/demo", payload)
    deadline = time.monotonic() + args.timeout
    while job["status"] in {"queued", "running"}:
        if time.monotonic() > deadline:
            raise TimeoutError(f"Client wait expired; job {job['id']} may still be running.")
        time.sleep(1)
        job = request("/api/jobs/" + job["id"])
    if job["status"] != "complete":
        raise RuntimeError(job["message"])
    result = request(f"/api/jobs/{job['id']}/files/result.json")
    print(
        json.dumps(
            {"id": job["id"], "qc": result["qc"], "result_dir": job["result_dir"]},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
