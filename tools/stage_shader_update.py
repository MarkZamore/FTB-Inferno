"""Stage the pinned shader addition against the current public FTB Inferno manifest."""

import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from urllib.request import urlopen
import zipfile


def pin(content):
    return {"sha256": hashlib.sha256(content).hexdigest(), "sizeBytes": len(content)}


def archive(files):
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, contents in sorted(files.items()):
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(entry, contents)
    return target.getvalue()


def match(data, row):
    if any(row[key] != value for key, value in pin(data).items()):
        raise ValueError(f"File differs from its pin: {row}")
    return data


def main(output):
    source = Path(__file__).resolve().parents[1]
    def git(*args):
        return subprocess.check_output(["git", "-C", str(source), *args]).decode().strip()

    revision = git("rev-parse", "HEAD")
    date = datetime.fromtimestamp(int(git("show", "-s", "--format=%ct", revision)), timezone.utc)
    lock = json.loads(git("show", f"{revision}:tools/shaders-lock.json"))
    base = "https://github.com/MarkZamore/FTB-Inferno/releases/download/pack-latest/"
    with urlopen(base + "pack-manifest.json?stage=" + revision, timeout=25) as response:
        previous = response.read()
    manifest = json.loads(previous)
    if (manifest["packId"], manifest["schemaVersion"], manifest["minecraftVersion"]) != ("minecraft-12", 2, "1.18.2"):
        raise ValueError("Unexpected FTB Inferno manifest")
    names = {row["path"].casefold() for row in manifest["files"]}
    shaders = {}
    for row in lock["files"]:
        path = Path(row["path"])
        if len(path.parts) != 2 or path.parts[0] != "shaderpacks" or path.suffix != ".zip":
            raise ValueError(f"Invalid shader path: {path}")
        if row["path"].casefold() in names:
            raise ValueError(f"Conflicting manifest path: {path}")
        local = source / path
        if local.is_file():
            content = local.read_bytes()
        else:
            with urlopen(row["source"], timeout=30) as response:
                content = response.read(row["sizeBytes"] + 1)
        shaders[row["path"]] = match(content, row)
        names.add(row["path"].casefold())
    with urlopen(base + manifest["library"]["name"], timeout=25) as response:
        old_library = match(response.read(), manifest["library"])
    with zipfile.ZipFile(io.BytesIO(old_library)) as old:
        card = json.loads(old.read("library.json"))
        if card["revision"] != manifest["revision"]:
            raise ValueError("Public library revision mismatch")
        card["revision"] = revision
        library = archive({
            "library.json": (json.dumps(card, ensure_ascii=False, indent=2) + "\n").encode(),
            "preview.jpg": old.read("preview.jpg"),
        })
    content = archive(shaders)
    shader_asset = pin(content)
    shader_asset.update(name=f"r-{shader_asset['sha256'][:12]}-shaderpacks-r5.7.1.zip",
                        kind="zipRoot", covers=sorted(shaders))
    library_asset = pin(library)
    library_asset.update(name=f"library-{library_asset['sha256']}.zip", revision=revision)
    manifest["revision"] = revision
    manifest["generatedAtUtc"] = date.strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["library"] = library_asset
    manifest["files"].extend({"path": name, **pin(data)} for name, data in shaders.items())
    manifest["files"].sort(key=lambda row: row["path"])
    manifest["assets"].append(shader_asset)
    manifest["assets"].sort(key=lambda row: row["name"])
    if sorted(row["path"] for row in manifest["files"]) != sorted(
            name for asset in manifest["assets"] for name in asset["covers"]):
        raise ValueError("Manifest assets must cover each file exactly once")
    output.mkdir()
    (output / "previous-manifest.json").write_bytes(previous)
    (output / shader_asset["name"]).write_bytes(content)
    (output / library_asset["name"]).write_bytes(library)
    (output / "pack-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
