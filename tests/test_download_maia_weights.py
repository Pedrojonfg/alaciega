import os
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "download_maia_weights.sh"


def _run(env):
    return subprocess.run(
        ["bash", str(SCRIPT)],
        env={**os.environ, **env},
        capture_output=True,
        text=True,
    )


def test_skip_existing_does_not_fetch(tmp_path):
    dest = tmp_path / "maia-1100.pb.gz"
    dest.write_bytes(b"already")
    r = _run({
        "MAIA_WEIGHTS_DIR": str(tmp_path),
        "MAIA_LEVELS": "1100",
        "MAIA_WEIGHTS_URL": "http://127.0.0.1:1",
    })
    assert r.returncode == 0, r.stderr
    assert dest.read_bytes() == b"already"


def test_download_missing_file(tmp_path):
    (tmp_path / "maia-1100.pb.gz").write_bytes(b"net-bytes")
    handler = SimpleHTTPRequestHandler
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, d=tmp_path, **k: handler(*a, directory=str(d), **k))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    out = tmp_path / "out"
    out.mkdir()
    r = _run({
        "MAIA_WEIGHTS_DIR": str(out),
        "MAIA_LEVELS": "1100",
        "MAIA_WEIGHTS_URL": f"http://127.0.0.1:{port}",
    })
    httpd.shutdown()
    assert r.returncode == 0, r.stderr
    assert (out / "maia-1100.pb.gz").read_bytes() == b"net-bytes"


def test_download_failure_nonzero(tmp_path):
    r = _run({
        "MAIA_WEIGHTS_DIR": str(tmp_path),
        "MAIA_LEVELS": "1100",
        "MAIA_WEIGHTS_URL": "http://127.0.0.1:1",
    })
    assert r.returncode != 0
