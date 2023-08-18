def test_landingpage(client):
    response = client.get("/")
    assert response.status_code == 200


def test_open_annotate(client):
    # defaults to task=annotate
    response = client.get("/open_data")
    assert response.status_code == 200


def test_open_draw(client):
    response = client.get("/open_data/draw")
    assert response.status_code == 200
