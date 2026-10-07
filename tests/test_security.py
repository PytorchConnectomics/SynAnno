"""Regression tests for the security fixes (public demo hardening)."""

import base64
import io
import logging
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


# 1. /load_materialization: arbitrary file read and server-side requests


def test_demo_rejects_local_files(make_app):
    client = make_app(SYNANNO_PUBLIC_DEMO="1").test_client()
    for url in ("/etc/passwd", "file:///etc/passwd", "../../etc/passwd"):
        response = load(client, url)
        assert response.status_code == 400
        assert "root:" not in response.get_data(as_text=True)


def test_demo_rejects_remote_urls(make_app):
    client = make_app(SYNANNO_PUBLIC_DEMO="1").test_client()
    for url in ("http://example.com/table.csv", "https://169.254.169.254/latest"):
        assert load(client, url).status_code == 400


def test_demo_accepts_bundled_materialization(make_app):
    app = make_app(SYNANNO_PUBLIC_DEMO="1")
    url = "file://" + app.config["BUNDLED_MATERIALIZATION"]
    response = load(app.test_client(), url)
    assert response.status_code == 200
    assert len(app.synapse_data) > 0


def test_rejected_even_when_table_is_cached(make_app):
    app = make_app(SYNANNO_PUBLIC_DEMO="1")
    client = app.test_client()
    url = "file://" + app.config["BUNDLED_MATERIALIZATION"]
    assert load(client, url).status_code == 200
    assert load(client, "/etc/passwd").status_code == 400


def test_local_mode_limits_paths_to_data_dirs(make_app, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "table.csv").write_text("x,y,z\n1,2,3\n")
    (tmp_path / "outside.csv").write_text("x,y,z\n1,2,3\n")
    client = make_app(SYNANNO_DATA_DIRS=str(data_dir)).test_client()

    assert load(client, str(tmp_path / "outside.csv")).status_code == 400
    assert load(client, str(data_dir / ".." / "outside.csv")).status_code == 400
    assert load(client, "/etc/passwd").status_code == 400
    assert load(client, "gs://bucket/table.csv").status_code == 400
    assert load(client, "file://" + str(data_dir / "table.csv")).status_code == 200


def test_local_mode_allows_http_urls(make_app):
    from synanno.routes.opendata import resolve_materialization_path

    app = make_app()
    with app.app_context():
        url = "https://example.com/table.csv"
        assert resolve_materialization_path(url) == url
        assert resolve_materialization_path("http:///no-host") is None


def test_load_errors_do_not_leak_details(make_app, tmp_path):
    (tmp_path / "empty.csv").write_text("")
    client = make_app(SYNANNO_DATA_DIRS=str(tmp_path)).test_client()
    response = load(client, str(tmp_path / "empty.csv"))
    assert response.status_code == 500
    assert response.get_json() == {"error": "Failed to load the materialization table."}


def test_missing_or_malformed_payload_is_400(make_app):
    client = make_app().test_client()
    assert client.post("/load_materialization", json={}).status_code == 400
    assert client.post("/load_materialization", data="x").status_code == 400
    response = client.post("/load_materialization", json={"materialization_url": 5})
    assert response.status_code == 400


# 2. Uploaded credentials and custom buckets in the public demo

H01 = {
    "source_url": "gs://h01-release/data/20210601/4nm_raw",
    "target_url": "gs://h01-release/data/20210729/c3/synapses/whole_ei_onlyvol",
    "neuropil_url": "gs://h01-release/data/20210601/proofread_104",
}


def test_demo_rejects_credential_upload(make_app):
    app = make_app(SYNANNO_PUBLIC_DEMO="1")
    form = dict(H01, view_style="neuron", tiles_per_page="12")
    form["secrets_file"] = (io.BytesIO(b'{"token": "x"}'), "secrets.json")
    response = app.test_client().post(
        "/upload", data=form, content_type="multipart/form-data"
    )
    assert response.status_code == 403
    assert not hasattr(app, "view_style")


def test_demo_rejects_custom_buckets(make_app):
    app = make_app(SYNANNO_PUBLIC_DEMO="1")
    client = app.test_client()
    form = dict(H01, source_url="gs://attacker/bucket", view_style="neuron")
    form["tiles_per_page"] = "12"
    assert client.post("/upload", data=form).status_code == 403
    query = dict(H01, source_url="file:///etc")
    assert client.get("/launch_neuroglancer", query_string=query).status_code == 403


# 3. Guessable Neuroglancer URLs


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

    assert len(tokens[0]) >= 43  # 32 random bytes, base64url encoded
    assert tokens[0] != tokens[1]
    assert "/" not in tokens[0]


# 4. CORS


def test_no_cors_headers(make_app):
    client = make_app().test_client()
    for path in ("/", "/get_source_image/0/0", "/get_neuron_id"):
        response = client.get(path, headers={"Origin": "http://evil.example"})
        assert "Access-Control-Allow-Origin" not in response.headers
    response = client.options(
        "/get_instance",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "Access-Control-Allow-Origin" not in response.headers


# 5. Debug mode


def test_dev_server_defaults_to_localhost_without_debug(monkeypatch):
    import dotenv
    from flask import Flask

    calls = []
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(Flask, "run", lambda self, **kwargs: calls.append(kwargs))
    for key in ("APP_IP", "FLASK_DEBUG"):
        monkeypatch.delenv(key, raising=False)

    run_py = os.path.join(os.path.dirname(os.path.dirname(__file__)), "run.py")
    runpy.run_path(run_py, run_name="__main__")

    assert calls[0]["host"] == "127.0.0.1"
    assert calls[0]["debug"] is False


def test_production_app_never_debugs(make_app, monkeypatch):
    monkeypatch.delenv("DEBUG_APP", raising=False)
    app = make_app()
    assert app.debug is False
    assert app.config["DEBUG_APP"] is False


# 6. Secret key


def test_secret_key_from_environment(make_app):
    assert make_app(SECRET_KEY="from-env").config["SECRET_KEY"] == "from-env"


def test_secret_key_generated_with_warning(make_app, caplog):
    with caplog.at_level(logging.WARNING, logger="synanno"):
        first = make_app().config["SECRET_KEY"]
    second = make_app().config["SECRET_KEY"]
    assert len(first) == 64 and first != second
    assert "SECRET_KEY is not set" in caplog.text
    assert first not in caplog.text


# 7. Templates


def test_os_module_not_exposed_to_templates(make_app):
    from flask import render_template_string

    app = make_app()
    with app.test_request_context("/"):
        assert render_template_string("{{ os }}") == ""
        assert render_template_string("{{ os is defined }}") == "False"


# 8. XSS: jQuery


def test_pages_use_vendored_jquery(make_app):
    app = make_app()
    html = app.test_client().get("/").get_data(as_text=True)
    assert "/static/vendor/jquery-3.7.1.min.js" in html
    assert "jquery-2.1.3" not in html and "code.jquery.com" not in html
    vendored = os.path.join(app.static_folder, "vendor", "jquery-3.7.1.min.js")
    with open(vendored) as f:
        assert "jQuery v3.7.1" in f.readline()


# 9. File routes


@pytest.mark.parametrize(
    "path",
    [
        "/get_source_image/..%2F..%2Fetc%2Fpasswd/0",
        "/get_target_image/0/..%2F..%2Fetc%2Fpasswd",
        "/get_curve_image/../../etc/passwd/0",
        "/get_source_image/%2Fetc%2Fpasswd/0",
    ],
)
def test_file_routes_serve_only_in_memory_data(make_app, path):
    response = make_app().test_client().get(path)
    assert response.status_code in (204, 404)
    assert b"root:" not in response.data


# 10. Input validation without asserts


def test_invalid_bbox_raises_value_error():
    from synanno.backend.processing import calculate_crop_pad

    with pytest.raises(ValueError):
        calculate_crop_pad([10, 5, 0, 10, 0, 10], (100, 100, 100))


def test_fn_save_rejects_bad_input(make_app):
    client = make_app().test_client()
    # missing fields
    assert client.post("/ng_bbox_fn_save", data={}).status_code == 400
    # z2 below z1 and no loaded volume
    form = {"z1": "10", "z2": "2", "my": "5", "mx": "5", "currentPage": "1"}
    assert client.post("/ng_bbox_fn_save", data=form).status_code == 400


# 11. Reachable dependency vulnerabilities


def _encoded(fmt):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGBA", (4, 4)).save(buffer, format=fmt)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def test_canvas_decoding_accepts_only_png(make_app):
    from PIL import UnidentifiedImageError

    from synanno.routes.manual_annotate import decode_image

    assert decode_image(_encoded("PNG")).format == "PNG"
    for fmt in ("GIF", "TIFF", "BMP"):
        with pytest.raises(UnidentifiedImageError):
            decode_image(_encoded(fmt))

    client = make_app().test_client()
    form = {"imageBase64": _encoded("TIFF"), "page": "1", "data_id": "0"}
    assert client.post("/save_canvas", data=form).status_code == 400


def test_locked_tornado_has_dos_fixes():
    lock = os.path.join(os.path.dirname(os.path.dirname(__file__)), "requirements.lock")
    with open(lock) as f:
        pins = dict(line.strip().split("==") for line in f if "==" in line)
    major, minor, patch = (int(x) for x in pins["tornado"].split("."))
    assert (major, minor, patch) >= (6, 5, 9)
