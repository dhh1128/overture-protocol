"""``overture-standin``: run the stand-in agent over HTTP."""

import argparse
import os
import socketserver
from pathlib import Path
from wsgiref.simple_server import WSGIServer, make_server

from keri.app import habbing
from keri.core.signing import Salter

from . import StandIn, load_script
from .http import app


class ThreadingServer(socketserver.ThreadingMixIn, WSGIServer):
    daemon_threads = True


def serve(api, host: str, port: int) -> None:  # pragma: no cover - runs forever
    with make_server(host, port, api, server_class=ThreadingServer) as httpd:
        httpd.serve_forever()


def salt(directory: Path) -> str:
    """This stand-in's own salt, made once and kept beside its databases."""
    path = directory / "salt"
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(Salter().qb64)
    os.chmod(path, 0o600)
    return path.read_text().strip()


def main(argv=None, *, run=serve) -> None:
    parser = argparse.ArgumentParser(prog="overture-standin", description=(
        "A stand-in Overture agent that decides by a script, for building clients against."))
    parser.add_argument("--data", type=Path, default=Path(".standin"),
                        help="Directory for its keys and memory (default .standin).")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5642)
    parser.add_argument("--url", help="The URL requesters reach it at (default http://HOST:PORT).")
    parser.add_argument("--script", type=Path, help="A JSON script of outcomes per action.")
    args = parser.parse_args(argv)
    args.data.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(args.data, 0o700)
    url = args.url or f"http://{args.host}:{args.port}"
    hby = habbing.Habery(name="standin", headDirPath=str(args.data), temp=False,
                         salt=salt(args.data))
    standin = StandIn(hby, url, load_script(args.script), args.data / "memory.sqlite")
    print(f"Principal {standin.principal.pre}", flush=True)
    print(f"Agent     {standin.agent.pre}", flush=True)
    print(f"OOBI      {standin.oobi()}", flush=True)
    try:
        run(app(standin), args.host, args.port)
    finally:
        standin.close()
        hby.close()
