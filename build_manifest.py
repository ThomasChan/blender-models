#!/usr/bin/env python3
"""Write the static model index GitHub Pages reads.

`serve.py` answers /api/models from the same scan; this is the committed snapshot.
Run it after adding or removing a .glb:

    python3 build_manifest.py
"""
import json
import os
from serve import index

ROOT = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    entries = index()
    with open(os.path.join(ROOT, "models.json"), "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"models.json: {len(entries)} models")
