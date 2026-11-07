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

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"   # frozen team files: the build page saves over teams/

AFC = yaml.safe_load((FIXTURES / "amber_flora_chixia.yaml").read_text())


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
    assert all(d["modelled"] for d in cat["discs"])   # every disc has a spec since 2026-11-04
    lines = cat["emblems"][str(amber["id"])]
    atk = next(e for e in lines if e["name"] == "ATK%")
    assert [t["colour"] for t in atk["tiers"]] == ["green", "blue", "yellow", "purple"] and atk["slots"] == [1, 2, 3]


def test_catalog_says_which_role_kits_are_real(client):
    by_name = {t["name"]: t for t in client.get("/api/catalog")["trekkers"]}
    assert by_name["Firstlight Noya"]["roles"]["main"]["kit"] == "ok"
    assert by_name["Tilia"]["roles"]["main"]["kit"] == "untimed"


def test_team_list_and_get(client, monkeypatch):
    monkeypatch.setattr(server, "TEAMS_DIR", FIXTURES)
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
    req = urllib.request.Request(client.base + "/api/jobs", data=b"{nope", method="POST",
                                 headers={"Content-Type": "application/json"})
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
    assert set(row) == {"name", "kind", "slots", "relevant", "tiers", "by_slot"}


def test_optimize_and_pinks_jobs(client):
    doc = state(fight_length=20)
    s = client.wait(client.json("POST", "/api/jobs", {"kind": "optimize", "state": doc,
                                                      "split": [2, 1, 1], "max_level": 2})["id"])
    assert s["state"] == "done", s
    assert [sum(t.values()) for t in s["result"]["targets"]] == [2, 1, 1]
    assert s["result"]["method"].startswith("greedy")
    s = client.wait(client.json("POST", "/api/jobs", {"kind": "optimize", "state": doc,
                                                      "split": [2, 2, 2], "max_level": 2, "total": 3})["id"])
    assert s["state"] == "done", s
    sums = [sum(t.values()) for t in s["result"]["targets"]]
    assert sum(sums) == 3 and max(sums) <= 2
    client.json("POST", "/api/jobs", {"kind": "optimize", "state": doc, "split": [2, 2, 2], "total": -1}, expect=400)
    client.json("POST", "/api/jobs", {"kind": "optimize", "state": doc, "split": [2, 2, 2], "breaks": "no"}, expect=400)
    s = client.wait(client.json("POST", "/api/jobs", {"kind": "optimize", "state": doc, "split": [1, 0, 0],
                                                      "max_level": 1, "breaks": True})["id"])
    assert s["state"] == "done", s
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


def test_sharecode_routes(client):
    code = "AAAAZwAAAH4AAACNobDDAY6gNhhhiKGGw2wA"
    d = client.json("POST", "/api/sharecode/decode", {"code": code})
    assert [m["trekker"] for m in d["members"]] == ["Amber", "Flora", "Chixia"]
    assert d["members"][0]["targets"]["Overloaded Spark"] == 1
    assert set(d["members"][0]["pinks"]) == {"Dominant Firepower", "Precise Temperature Control"}
    doc = state()
    for m, dm in zip(doc["members"], d["members"]):
        m["pinks"], m["targets"] = dm["pinks"], dm["targets"]
    assert client.json("POST", "/api/sharecode/encode", {"state": doc}) == {"code": code}
    assert client.call("POST", "/api/sharecode/decode", {"code": "hello"})[0] == 400


def test_catalog_potentials_in_game_row_order(client):
    amber = next(t for t in client.get("/api/catalog")["trekkers"] if t["name"] == "Amber")
    row1 = [p["name"] for p in amber["roles"]["main"]["potentials"] if p["row"] == 1]
    assert row1 == ["Confident Mode", "Greed Gunfire", "Ardent Trigger"]


def test_rejects_foreign_host_and_non_json_posts(client):
    port = client.base.rsplit(":", 1)[1]
    req = urllib.request.Request(client.base + "/api/teams", headers={"Host": f"evil.example:{port}"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=10)
    assert e.value.code == 403
    req = urllib.request.Request(client.base + "/api/jobs", method="POST", data=json.dumps(
        {"kind": "recalc", "state": state()}).encode(), headers={"Content-Type": "text/plain"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=10)
    assert e.value.code == 415
    req = urllib.request.Request(client.base + "/api/teams", headers={"Host": f"localhost:{port}"})
    assert urllib.request.urlopen(req, timeout=10).status == 200


def test_catalog_lists_enemies(gd):
    from ssr.web.catalog import catalog
    ids = [e["id"] for e in catalog(gd)["enemies"]]
    assert ids == ["generic", "count_of_the_duloos", "lithe_beauty"]


def test_team_doc_with_preset(gd):
    from ssr.web.server import _team
    doc = yaml.safe_load(open(TEAMS / "fl_noya_skill.yaml")); doc["enemy"] = {"preset": "lithe_beauty"}
    assert _team(gd, doc).enemy.name == "lithe_beauty"
