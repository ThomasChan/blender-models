#!/usr/bin/env python3
"""Viewer server for this folder: static files plus /api/models.

python3 serve.py [port]        # default 8777, 127.0.0.1
"""
import json
import os
import struct
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
GLB_MAGIC = 0x46546C67


def tris(path):
    """Triangle count out of the GLB's own JSON chunk. Reads index counts only, so
    a primitive drawn as a strip or fan would be counted wrong -- nothing here
    exports those (glTF's default mode 4 is triangles)."""
    try:
        with open(path, "rb") as f:
            magic, _version, _length = struct.unpack("<III", f.read(12))
            if magic != GLB_MAGIC:
                return None
            chunk_len, _chunk_type = struct.unpack("<II", f.read(8))
            doc = json.loads(f.read(chunk_len))
        acc = doc.get("accessors", [])
        return sum(acc[p["indices"]]["count"] // 3
                   for m in doc.get("meshes", []) for p in m.get("primitives", [])
                   if p.get("indices") is not None)
    except Exception:
        return None


def thumb(d, stem, meta):
    """The gallery card image. `thumb` in the sidecar wins (a folder can hold two
    models); otherwise the shared thumb.webp, the hero render, or any hero render
    left in the folder. 800px WebP keeps the whole grid under ~100KB, which the
    1200px transparent PNGs cannot."""
    if meta.get("thumb"):
        return meta["thumb"]
    for name in ("thumb.webp", "preview-hero.png", f"preview-{stem}-hero.png"):
        if os.path.exists(os.path.join(d, name)):
            return name
    heroes = sorted(f for f in os.listdir(d)
                    if f.startswith("preview-") and f.endswith("-hero.png"))
    return heroes[0] if heroes else None


def index():
    """One entry per .glb, one level down. An optional sidecar with the same stem
    carries the display title and any per-asset conversion fix the viewer applies."""
    out = []
    for folder in sorted(os.listdir(ROOT)):
        d = os.path.join(ROOT, folder)
        if folder.startswith(".") or not os.path.isdir(d):
            continue
        files = [f for f in os.listdir(d) if f.endswith(".glb")]
        # The namesake file leads, so the page opens on `macmini.glb` rather than on
        # whichever `macmini-*.glb` variant happens to sort first.
        files.sort(key=lambda f: (f[:-4] != folder, f))
        for fn in files:
            meta = {}
            sidecar = os.path.join(d, fn[:-4] + ".json")
            if os.path.exists(sidecar):
                with open(sidecar, encoding="utf-8") as f:
                    meta = json.load(f)
            t = thumb(d, fn[:-4], meta)
            out.append({
                "title": meta.get("title") or f"{folder}/{fn[:-4]}",
                "url": f"{folder}/{fn}",
                "thumb": f"{folder}/{t}" if t else None,
                "tris": tris(os.path.join(d, fn)),
                "bytes": os.path.getsize(os.path.join(d, fn)),
                "fix": meta.get("fix") or {},
            })
    return out


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def end_headers(self):
        # Without this Chrome keeps serving whatever it cached from an earlier shape of
        # the page under the same filename, and the browser and the developer end up
        # looking at two different pages. Cost of no-store here: a local re-read.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path.split("?")[0] == "/api/models":
            body = json.dumps(index(), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8777
    print(f"blender-models → http://127.0.0.1:{port}/  ({ROOT})")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
