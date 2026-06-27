"""Load test for the EGI sync server (plan-15 §8.2).

Exercises the three hot paths a real deployment sees under stress:

  * sync upload  — devices pushing batches of person records to ``POST /sync``.
  * search       — operators/families querying ``GET /persons?q=`` under load.
  * moderation   — operators draining the queue via ``GET /moderation/pending``.

Run it against a server seeded with ~10k records (``egi generate-synthetic``) to
verify the SLOs in ``docs/PERFORMANCE.md``. This is OPTIONAL tooling — locust is
not a runtime dependency; install it only when you want to load test:

    pip install locust
    egi generate-synthetic --count 10000
    egi backend                       # in another shell, on :3000
    locust -f server/tests/load/locustfile.py --host http://localhost:3000

Then open http://localhost:8089, or run headless for CI-style p95 reporting:

    locust -f server/tests/load/locustfile.py --host http://localhost:3000 \
        --headless -u 50 -r 10 -t 1m --csv egi-load

All generated data is fake (TEST DATA) and lands as untrusted-source records that
stay in the moderation queue — never approve a load-test run into a real DB.
"""

import uuid

from locust import HttpUser, between, task

# A token can be supplied via the LOCUST env if the target enforces auth; the
# default dev server (no users, no OPERATOR_TOKENS) needs none.
import os

_AUTH = os.environ.get("EGI_LOAD_TOKEN", "").strip()
_HEADERS = {"Authorization": f"Bearer {_AUTH}"} if _AUTH else {}

_NAMES = ["TEST Ana", "TEST Luis", "TEST Maria", "TEST Jose", "TEST Carmen"]
_STATUSES = ["missing", "found", "safe", "sighted"]


class EgiUser(HttpUser):
    wait_time = between(0.5, 2.5)

    @task(3)
    def search_persons(self):
        term = _NAMES[hash(self.environment.runner.user_count) % len(_NAMES)]
        self.client.get(f"/persons?q={term}", name="GET /persons?q=", headers=_HEADERS)

    @task(2)
    def sync_upload(self):
        n = self.environment.runner.user_count or 1
        rec_id = f"load-{uuid.uuid4().hex}"
        payload = {
            "records": [
                {
                    "id": rec_id,
                    "name": _NAMES[n % len(_NAMES)],
                    "status": _STATUSES[n % len(_STATUSES)],
                    "source": "synthetic",
                    "notes": "TEST DATA load run",
                }
            ]
        }
        self.client.post("/sync", json=payload, name="POST /sync", headers=_HEADERS)

    @task(1)
    def moderation_queue(self):
        self.client.get(
            "/moderation/pending?limit=50", name="GET /moderation/pending", headers=_HEADERS
        )

    @task(1)
    def health(self):
        self.client.get("/health", name="GET /health")
