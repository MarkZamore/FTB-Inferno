"""Publish the pack-owned controls preset over the current public payload."""
import io
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.request import urlopen
from uuid import uuid4
from zipfile import ZipFile

from build_preset import ROOT, OUTPUT

sys.path.insert(0, str(ROOT / "tools"))
from stage_shader_update import archive, match, pin

REPO = "MarkZamore/FTB-Inferno"
BASE = f"https://github.com/{REPO}/releases/download/pack-latest/"
PRESET = "launcher/controls-preset.txt"


def command(*args):
    return subprocess.check_output(args, cwd=ROOT).decode().strip()


def download(name):
    with urlopen(f"{BASE}{name}?qa={uuid4()}", timeout=45) as response:
        return response.read()


def json_bytes(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode()


def stage(previous, revision, when, preset, old_library):
    manifest = json.loads(previous)
    if (manifest["packId"], manifest["minecraftVersion"], manifest["loader"]) != (
            "minecraft-12", "1.18.2", {"type": "forge", "version": "40.2.34"}):
        raise ValueError("Unexpected source platform")
    with ZipFile(io.BytesIO(match(old_library, manifest["library"]))) as bundle:
        card = json.loads(bundle.read("library.json"))
        if card["revision"] != manifest["revision"] or card["id"] != manifest["packId"]:
            raise ValueError("Library revision mismatch")
        card["revision"] = revision
        library = archive({"library.json": json_bytes(card), "preview.jpg": bundle.read("preview.jpg")})
    payload = archive({PRESET: preset})
    payload_pin = pin(payload)
    asset_name = f"r-{payload_pin['sha256'][:12]}-controls-preset.zip"
    library_pin = pin(library)
    library_name = f"library-{library_pin['sha256']}.zip"
    assets = []
    for row in manifest["assets"]:
        if PRESET in row["covers"]:
            if row["covers"] != [PRESET]:
                raise ValueError("Preset shares its archive with other files")
        else:
            assets.append(row)
    assets.append({"name": asset_name, "kind": "zipRoot", "covers": [PRESET], **payload_pin})
    files = [row for row in manifest["files"] if row["path"] != PRESET]
    files.append({"path": PRESET, **pin(preset)})
    if sorted(row["path"] for row in files) != sorted(path for row in assets for path in row["covers"]):
        raise ValueError("Incomplete asset coverage")
    manifest.update(revision=revision, generatedAtUtc=when,
                    library={"name": library_name, "revision": revision, **library_pin},
                    files=sorted(files, key=lambda row: row["path"]),
                    assets=sorted(assets, key=lambda row: row["name"]))
    return json_bytes(manifest), {asset_name: payload, library_name: library}


def publish():
    revision = command("git", "rev-parse", "HEAD")
    when = command("git", "show", "-s", "--format=%cI", revision)
    previous = download("pack-manifest.json")
    manifest = json.loads(previous)
    base = manifest["revision"]
    preset = OUTPUT.read_bytes()
    if base == revision and {"path": PRESET, **pin(preset)} in manifest["files"]:
        print("Preset already published", pin(preset))
        return
    result, assets = stage(previous, revision, when, preset, download(manifest["library"]["name"]))
    with TemporaryDirectory() as tmp:
        for name, data in assets.items():
            path = Path(tmp) / name
            path.write_bytes(data)
            listed = json.loads(command("gh", "release", "view", "pack-latest", "-R", REPO, "--json", "assets"))
            if not any(row["name"] == name for row in listed["assets"]):
                command("gh", "release", "upload", "pack-latest", str(path), "-R", REPO)
            match(download(name), pin(data))
        current = command("git", "ls-remote", "origin", "refs/heads/main").split()[0]
        if current != revision:
            raise ValueError("A newer source revision is available")
        if download("pack-manifest.json") != previous:
            raise ValueError("Public manifest changed while staging")
        tag = command("git", "ls-remote", "origin", "refs/tags/pack-latest").split()[0]
        if tag not in (base, revision):
            raise ValueError("Release tag changed while staging")
        if tag != revision:
            command("git", "push", f"--force-with-lease=refs/tags/pack-latest:{base}",
                    "origin", f"{revision}:refs/tags/pack-latest")
        command("gh", "release", "edit", "pack-latest", "--target", revision, "-R", REPO)
        path = Path(tmp) / "pack-manifest.json"
        path.write_bytes(result)
        command("gh", "release", "upload", "pack-latest", str(path), "--clobber", "-R", REPO)
    for attempt in range(6):
        if download("pack-manifest.json") == result:
            print("Published", revision, pin(preset))
            return
        time.sleep(5)
    raise ValueError("Public manifest did not match the candidate")


if __name__ == "__main__":
    publish()
