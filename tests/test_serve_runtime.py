import socket

from ltts.client import server_alive
from ltts.serve_runtime import start_server_background, stop_server


def test_server_background_start_stop():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    assert not server_alive(url, timeout=0.2)
    handle = start_server_background("127.0.0.1", port, log_level="error")
    assert handle is not None
    assert server_alive(url, timeout=2)
    stop_server(handle)
    assert not server_alive(url, timeout=0.5)
