import time

from rtsapi import bluetooth

ADDRESS = "F0:B5:D1:5D:FC:6F"


def heartbeat(client, worker="w1", hostname="pi-1"):
    hb = {"worker_id": worker, "sent_at": time.time(), "system": {"hostname": hostname}}
    return client.post("/worker/heartbeat", json=hb).json()["bluetooth_requests"]


def device_id(client, hostname="pi-1"):
    return next(d["id"] for d in client.get("/devices").json() if d["hostname"] == hostname)


def test_scan_is_handed_to_one_worker_of_the_pi(client):
    heartbeat(client, "w1")
    heartbeat(client, "other", hostname="pi-2")
    pi = device_id(client)
    request = client.post(f"/devices/{pi}/bluetooth/scan").json()
    assert request["status"] == "pending"
    # A second scan of the same Pi follows the running one
    assert client.post(f"/devices/{pi}/bluetooth/scan").json()["id"] == request["id"]

    assert heartbeat(client, "other", hostname="pi-2") == []  # another Pi
    taken = heartbeat(client, "w1")
    assert [r["id"] for r in taken] == [request["id"]] and taken[0]["kind"] == "scan"
    assert heartbeat(client, "w2") == []  # only one worker gets it

    found = [{"address": ADDRESS, "name": "TS885873", "rssi": -60}]
    url = f"/worker/bluetooth/{request['id']}"
    assert client.post(url, params={"worker_id": "w2"}, json={"status": "done"}).status_code == 404
    assert client.post(url, params={"worker_id": "w1"}, json={"status": "running", "found": found}).status_code == 204
    assert client.get(f"/bluetooth/requests/{request['id']}").json()["found"][0]["name"] == "TS885873"
    client.post(url, params={"worker_id": "w1"}, json={"status": "done", "found": found})
    assert client.get(f"/bluetooth/requests/{request['id']}").json()["status"] == "done"
    assert client.get("/bluetooth/instruments").json() == []  # a scan alone does not identify


def test_identify_remembers_the_instrument(client):
    heartbeat(client)
    pi = device_id(client)
    assert client.post(f"/devices/{pi}/bluetooth/identify", json={"address": "nonsense"}).status_code == 422
    request = client.post(f"/devices/{pi}/bluetooth/identify", json={"address": ADDRESS}).json()
    assert request["channel"] is None
    heartbeat(client)
    instrument = {"address": ADDRESS, "name": "TS885873", "instrument_name": 'MS60 1" R2000', "serial_number": 885873, "channel": 11}
    client.post(f"/worker/bluetooth/{request['id']}", params={"worker_id": "w1"}, json={"status": "done", "instrument": instrument})

    [known] = client.get("/bluetooth/instruments").json()
    assert known["channel"] == 11 and known["last_device_id"] == pi and known["serial_number"] == 885873
    # The next identification tries the known channel first
    assert client.post(f"/devices/{pi}/bluetooth/identify", json={"address": ADDRESS}).json()["channel"] == 11
    assert client.delete(f"/bluetooth/instruments/{ADDRESS}").status_code == 204
    assert client.get("/bluetooth/instruments").json() == []


def test_request_fails_without_worker(client, monkeypatch):
    heartbeat(client)
    pi = device_id(client)
    monkeypatch.setattr(bluetooth, "PICKUP_TIMEOUT", 0.0)
    request = client.post(f"/devices/{pi}/bluetooth/scan").json()
    time.sleep(0.01)
    failed = client.get(f"/bluetooth/requests/{request['id']}").json()
    assert failed["status"] == "failed" and "No worker" in failed["error"]


def test_no_scan_while_measuring_over_bluetooth(client, setup):
    rts = setup["rts"]
    client.patch(f"/rts/{rts['id']}", json={"port": f"bt://{ADDRESS}/11"})
    client.post("/jobs", json={"rts_id": rts["id"], "type": "track_prism"})
    assert client.post("/worker/claim", json={"worker_id": "w1", "hostname": "pi-1"}).status_code == 200
    pi = setup["device"]["id"]
    response = client.post(f"/devices/{pi}/bluetooth/scan")
    assert response.status_code == 409 and "would disturb" in response.json()["message"]
    assert client.post(f"/devices/{pi}/bluetooth/identify", json={"address": ADDRESS}).status_code == 409
