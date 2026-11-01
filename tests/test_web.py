import copy
import json
import threading
import time
import urllib.error
import urllib.request

import pytest
import yaml

from ssr.team import TEAMS
from ssr.web import server
from ssr.web.jobs import JobBusy, JobRunner

AFC = yaml.safe_load((TEAMS / "amber_flora_chixia.yaml").read_text())


class Client:
    def __init__(self, base):
        self.base = base

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def json(self, method, path, body=None, expect=200):
        status, _h, raw = self.call(method, path, body)
        assert status == expect, raw
        return json.loads(raw)

    def get(self, path):
        return self.json("GET", path)

    def wait(self, job_id, timeout=120):
        t0 = time.time()
        while time.time() - t0 < timeout:
            s = self.get(f"/api/jobs/{job_id}")
            if s["state"] != "running":
                return s
            time.sleep(0.1)
        raise TimeoutError(job_id)


@pytest.fixture(scope="session")
def client(gd):
    srv = server.make_server(gd, port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield Client(f"http://127.0.0.1:{srv.server_address[1]}")
    srv.shutdown()


@pytest.fixture
def tmp_teams(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "TEAMS_DIR", tmp_path)
    return tmp_path


def state(**top):
    d = copy.deepcopy(AFC)
    d.update(top)
    return d


def test_catalog_lists_spec_trekkers(client):
    cat = client.get("/api/catalog")
    assert {t["name"] for t in cat["trekkers"]} >= {"Amber", "Flora", "Chixia"}
    amber = next(t for t in cat["trekkers"] if t["name"] == "Amber")
    assert {p["row"] for p in amber["roles"]["main"]["potentials"]} == {1, 2, 3}
    assert len(amber["roles"]["support"]["pinks"]) == 4 and amber["element"] == "Ignis"
    assert any(d["modelled"] for d in cat["discs"]) and any(not d["modelled"] for d in cat["discs"])
    lines = cat["emblems"][str(amber["id"])]
    atk = next(e for e in lines if e["name"] == "ATK%")
    assert [t["colour"] for t in atk["tiers"]] == ["green", "blue", "yellow", "purple"] and atk["slots"] == [1, 2, 3]


def test_team_list_and_get(client):
    assert "amber_flora_chixia" in client.get("/api/teams")
    assert client.get("/api/teams/amber_flora_chixia") == AFC
    assert client.call("GET", "/api/teams/nope")[0] == 404


def test_team_load_save_round_trip(client, tmp_teams):
    doc = state(name="x")
    assert client.json("PUT", "/api/teams/my_team", {"state": doc}) == {"saved": "my_team"}
    assert client.get("/api/teams/my_team") == doc
    assert (tmp_teams / "my_team.yaml").exists()


def test_save_rejects_path_tricks(client, tmp_teams):
    assert client.call("PUT", "/api/teams/..%2Fx", {"state": state()})[0] == 400
    assert client.call("PUT", "/api/teams/a.b", {"state": state()})[0] == 400


def test_save_rejects_bad_state(client, tmp_teams):
    doc = state()
    doc["members"][0]["targets"] = {"Nope": 3}
    status, _h, raw = client.call("PUT", "/api/teams/bad", {"state": doc})
    assert status == 400 and "Nope" in json.loads(raw)["error"] and not (tmp_teams / "bad.yaml").exists()


def test_bad_state_is_400_naming_the_value(client):
    doc = state()
    doc["members"][0]["targets"] = {"Nope": 3}
    status, _h, raw = client.call("POST", "/api/jobs", {"kind": "recalc", "state": doc})
    assert status == 400 and "Nope" in json.loads(raw)["error"]


def test_malformed_json_is_400(client):
    req = urllib.request.Request(client.base + "/api/jobs", data=b"{nope", method="POST")
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=10)
    assert e.value.code == 400


def test_two_pinks_required(client):
    doc = state()
    doc["members"][1]["pinks"] = doc["members"][1]["pinks"][:1]
    status, _h, raw = client.call("POST", "/api/jobs", {"kind": "recalc", "state": doc})
    assert status == 400 and json.loads(raw)["error"] == "pick 2 pinks for Flora"


def test_unknown_job_kind_is_400(client):
    assert client.call("POST", "/api/jobs", {"kind": "nope", "state": state()})[0] == 400


def test_second_job_is_409(client):
    first = client.json("POST", "/api/jobs", {"kind": "recalc", "state": state()})
    status, _h, raw = client.call("POST", "/api/jobs", {"kind": "recalc", "state": state()})
    assert status == 409 and "running" in json.loads(raw)["error"]
    client.json("POST", f"/api/jobs/{first['id']}/cancel", {})
    assert client.wait(first["id"])["state"] == "cancelled"


def test_recalc_job_completes(client):
    doc = state(fight_length=20)
    doc["members"][0]["targets"] = {"Ardent Trigger": 3}
    job = client.json("POST", "/api/jobs", {"kind": "recalc", "state": doc})
    s = client.wait(job["id"])
    assert s["state"] == "done", s
    res = s["result"]
    assert {k.split(":")[0] for k in res["grid"]} == {"0", "1", "2"}
    assert all(len(v) == 6 for v in res["grid"].values())
    assert set(res["emblems"]) == {"0", "1", "2"} and res["total"] > 0
    row = res["emblems"]["0"][0]
    assert set(row) == {"name", "kind", "slots", "relevant", "tiers"}


def test_optimize_and_pinks_jobs(client):
    doc = state(fight_length=20)
    s = client.wait(client.json("POST", "/api/jobs", {"kind": "optimize", "state": doc,
                                                      "split": [2, 1, 1], "max_level": 2})["id"])
    assert s["state"] == "done", s
    assert [sum(t.values()) for t in s["result"]["targets"]] == [2, 1, 1]
    assert s["result"]["method"].startswith("greedy")
    doc["members"][2]["pinks"] = []          # the searched member's own pinks don't matter
    s = client.wait(client.json("POST", "/api/jobs", {"kind": "pinks", "state": doc, "member": 2})["id"])
    assert s["state"] == "done", s
    rows = s["result"]
    assert len(rows) == 6 and rows[0]["vs_best"] == 0 and all(r["vs_best"] <= 0 for r in rows)
    assert all(len(r["pinks"]) == 2 for r in rows)


def test_job_runner_busy_and_cancel():
    runner = JobRunner()
    gate = threading.Event()

    def work(progress):
        while True:
            progress("x", 0, 1)
            gate.wait(0.01)
    jid = runner.start("t", work)
    with pytest.raises(JobBusy):
        runner.start("t", work)
    runner.cancel(jid)
    for _ in range(200):
        if runner.status(jid)["state"] != "running":
            break
        time.sleep(0.01)
    assert runner.status(jid)["state"] == "cancelled"
    assert runner.status(runner.start("t", lambda p: 42))["id"]


def test_page_and_static_files(client):
    status, headers, raw = client.call("GET", "/")
    assert status == 200 and "text/html" in headers["Content-Type"] and b"app.js" in raw
    status, headers, raw = client.call("GET", "/static/app.js")
    assert status == 200 and "javascript" in headers["Content-Type"] and b"runJob" in raw
    status, headers, _raw = client.call("GET", "/static/app.css")
    assert status == 200 and "text/css" in headers["Content-Type"]
    assert client.call("GET", "/static/..%2Fserver.py")[0] == 404
