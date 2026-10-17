"""Create a self-contained UI preview and a clean release ZIP from this source."""

from __future__ import annotations

import argparse
import ast
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import wave
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/daybreak_alarm"
EXCLUDE = {"__pycache__", ".git", ".venv", "node_modules", "dist"}


def source_files():
    # Prune build/tool directories so a local npm install cannot enter a release.
    import os
    for directory, dirs, names in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE)
        for name in sorted(names):
            path = Path(directory) / name
            if path.suffix not in (".pyc", ".zip"):
                yield path


def build(destination):
    spec = importlib.util.spec_from_file_location("standalone_models", COMPONENT / "models.py")
    models = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(models)
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    version = manifest["version"]
    assert manifest["domain"] == "daybreak_alarm"
    assert json.loads((COMPONENT / "strings.json").read_text()) == json.loads((COMPONENT / "translations/en.json").read_text())
    for source in (p for p in source_files() if p.suffix == ".py"):
        ast.parse(source.read_text(), filename=str(source))
    for name in ("daybreak", "soft", "pulse"):
        with wave.open(str(COMPONENT / "frontend/sounds" / f"{name}.wav")) as sound:
            assert sound.getnchannels() == 1 and sound.getsampwidth() == 2
            assert sound.getnframes() == sound.getframerate() * 6
    js = (COMPONENT / "frontend/panel.js").read_text()
    demo = (ROOT / "tools/preview_adapter.js").read_text().replace("__DEFAULTS__", json.dumps(models.default_config()))
    script = (js + "\n" + demo).replace("</script", "<\\/script")
    subprocess.run(["node", "--input-type=module", "--check"], input=script, text=True, check=True)
    preview = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Daybreak Alarms — interactive preview</title>
<style>body{margin:0;background:#111215;color:#f6f4ef;font-family:system-ui,sans-serif}.preview-banner{height:42px;box-sizing:border-box;display:flex;align-items:center;justify-content:center;gap:16px;padding:8px 12px;background:#362b20;color:#ffc078;font-size:11px}.preview-banner button{border:1px solid #ffc07866;border-radius:5px;padding:4px 8px;background:none;color:inherit;font:inherit;cursor:pointer}daybreak-alarm-panel{height:calc(100dvh - 42px)}@media(max-width:500px){.preview-banner{font-size:9px;gap:8px}}</style></head>
<body><div class="preview-banner"><span>Interactive preview · no devices are controlled · changes stay in this tab</span><button id="preview-theme">Light / dark</button></div><daybreak-alarm-panel></daybreak-alarm-panel><script type="module">''' + script + "</script></body></html>\n"
    (ROOT / "preview.html").write_text(preview)
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / f"daybreak-alarm-v{version}.zip"
    files = sorted(source_files())
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, Path(f"daybreak-alarm-v{version}") / file.relative_to(ROOT))
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert len(names) == len(files) == len(set(names))
        assert all(not name.startswith("/") and ".." not in Path(name).parts for name in names)
    print(json.dumps({"path":str(output),"files":len(files),"bytes":output.stat().st_size,"sha256":sha256(output.read_bytes()).hexdigest()},indent=2))


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=ROOT.parent/"deliverables")
    build(parser.parse_args().output)
