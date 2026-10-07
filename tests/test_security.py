"""Regression tests for the security fixes (public demo hardening)."""

import base64
import io
import os
import runpy

import pytest

from synanno import create_app


@pytest.fixture
def make_app(monkeypatch):
    """Create a fresh app with the given environment variables."""

    def _make(**env):
        for key in ("SYNANNO_PUBLIC_DEMO", "SYNANNO_DATA_DIRS", "SECRET_KEY"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        app = create_app()
        app.config["TESTING"] = True
        return app

    return _make


def load(client, url):
    return client.post("/load_materialization", json={"materialization_url": url})


H01 = {
    "source_url": "gs://h01-release/data/20210601/4nm_raw",
    "target_url": "gs://h01-release/data/20210729/c3/synapses/whole_ei_onlyvol",
    "neuropil_url": "gs://h01-release/data/20210601/proofread_104",
}


def test_demo_materialization_allowlist(make_app):
    app = make_app(SYNANNO_PUBLIC_DEMO="1")
    client = app.test_client()
    for url in ("/etc/passwd", "file:///etc/passwd", "http://example.com/t.csv"):
        response = load(client, url)
        assert response.status_code == 400
        assert "root:" not in response.get_data(as_text=True)

    bundled = "file://" + app.config["BUNDLED_MATERIALIZATION"]
    assert load(client, bundled).status_code == 200
    # still rejected once a table is cached
    assert load(client, "/etc/passwd").status_code == 400


def test_local_materialization_limited_to_data_dirs(make_app, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "table.csv").write_text("x,y,z\n1,2,3\n")
    (data_dir / "empty.csv").write_text("")
    (tmp_path / "outside.csv").write_text("x,y,z\n1,2,3\n")
    client = make_app(SYNANNO_DATA_DIRS=str(data_dir)).test_client()

    outside = str(data_dir / ".." / "outside.csv")
    for url in (outside, "gs://bucket/t.csv", "/etc/passwd"):
        assert load(client, url).status_code == 400

    # errors do not echo exception details
    response = load(client, str(data_dir / "empty.csv"))
    assert response.get_json() == {"error": "Failed to load the materialization table."}

    assert load(client, "file://" + str(data_dir / "table.csv")).status_code == 200


def test_demo_refuses_credentials_and_custom_buckets(make_app):
    app = make_app(SYNANNO_PUBLIC_DEMO="1")
    client = app.test_client()

    form = dict(H01, view_style="neuron", tiles_per_page="12")
    form["secrets_file"] = (io.BytesIO(b'{"token": "x"}'), "secrets.json")
    assert client.post("/upload", data=form).status_code == 403
    assert not hasattr(app, "view_style")  # rejected before any state change

    form = dict(H01, source_url="gs://other/bucket", tiles_per_page="12")
    assert client.post("/upload", data=form).status_code == 403
    query = dict(H01, source_url="file:///etc")
    response = client.get("/launch_neuroglancer", query_string=query)
    assert response.status_code == 403


def test_neuroglancer_token_is_unguessable(make_app, monkeypatch):
    import synanno.backend.ng_util as ng_util

    tokens = []

    class Stop(Exception):
        pass

    def fake_viewer(token):
        tokens.append(token)
        raise Stop

    monkeypatch.setattr(ng_util.neuroglancer, "set_server_bind_address", lambda **_: 0)
    monkeypatch.setattr(ng_util.neuroglancer, "Viewer", fake_viewer)
    app = make_app()
    for _ in range(2):
        with pytest.raises(Stop):
            ng_util.setup_ng(
                app, "precomputed://a", "precomputed://b", "precomputed://c"
            )

    assert len(tokens[0]) >= 43 and tokens[0] != tokens[1]


def test_no_cors_headers(make_app):
    client = make_app().test_client()
    response = client.get("/", headers={"Origin": "http://evil.example"})
    assert "Access-Control-Allow-Origin" not in response.headers
    preflight = {
        "Origin": "http://evil.example",
        "Access-Control-Request-Method": "POST",
    }
    response = client.options("/get_instance", headers=preflight)
    assert "Access-Control-Allow-Origin" not in response.headers


def test_no_debug_by_default(make_app, monkeypatch):
    import dotenv
    from flask import Flask

    calls = []
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(Flask, "run", lambda self, **kwargs: calls.append(kwargs))
    for key in ("APP_IP", "FLASK_DEBUG", "DEBUG_APP"):
        monkeypatch.delenv(key, raising=False)

    run_py = os.path.join(os.path.dirname(os.path.dirname(__file__)), "run.py")
    runpy.run_path(run_py, run_name="__main__")
    assert calls[0]["host"] == "127.0.0.1" and calls[0]["debug"] is False

    app = make_app()
    assert app.debug is False and app.config["DEBUG_APP"] is False


def test_secret_key(make_app):
    assert make_app(SECRET_KEY="from-env").config["SECRET_KEY"] == "from-env"
    first, second = make_app().config["SECRET_KEY"], make_app().config["SECRET_KEY"]
    assert len(first) == 64 and first != second


def test_os_module_not_exposed_to_templates(make_app):
    from flask import render_template_string

    with make_app().test_request_context("/"):
        assert render_template_string("{{ os is defined }}") == "False"


def test_pages_use_vendored_jquery(make_app):
    html = make_app().test_client().get("/").get_data(as_text=True)
    assert "/static/vendor/jquery-3.7.1.min.js" in html
    assert "jquery-2.1.3" not in html


@pytest.mark.parametrize(
    "path",
    [
        "/get_source_image/..%2F..%2Fetc%2Fpasswd/0",
        "/get_curve_image/../../etc/passwd/0",
    ],
)
def test_file_routes_serve_only_in_memory_data(make_app, path):
    response = make_app().test_client().get(path)
    assert response.status_code in (204, 404)
    assert b"root:" not in response.data


def test_fn_save_rejects_invalid_bbox(make_app):
    from synanno.backend.processing import calculate_crop_pad

    with pytest.raises(ValueError):  # not an assert, so it survives python -O
        calculate_crop_pad([10, 5, 0, 10, 0, 10], (100, 100, 100))

    client = make_app().test_client()
    assert client.post("/ng_bbox_fn_save", data={}).status_code == 400
    form = {"z1": "10", "z2": "2", "my": "5", "mx": "5", "currentPage": "1"}
    assert client.post("/ng_bbox_fn_save", data=form).status_code == 400


def _encoded(fmt):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGBA", (4, 4)).save(buffer, format=fmt)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def test_canvas_upload_accepts_only_png(make_app):
    from PIL import UnidentifiedImageError

    from synanno.routes.manual_annotate import decode_image

    assert decode_image(_encoded("PNG")).format == "PNG"
    with pytest.raises(UnidentifiedImageError):
        decode_image(_encoded("TIFF"))

    client = make_app().test_client()
    form = {"imageBase64": _encoded("TIFF"), "page": "1", "data_id": "0"}
    assert client.post("/save_canvas", data=form).status_code == 400
