"""Stage a questbook-only update against a pinned public FTB Inferno release."""

import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import subprocess
import sys
from urllib.request import urlopen
from uuid import uuid4
import zipfile

from build import PACK, QUESTS, fingerprint, json_bytes, read_json
sys.path.insert(0, str(PACK / "tools"))
from stage_shader_update import archive, match


BASE = "https://github.com/MarkZamore/FTB-Inferno/releases/download/pack-latest/"


def download(name):
    with urlopen(f"{BASE}{name}?qa={uuid4()}", timeout=45) as response:
        return response.read()


def read_asset(row):
    data = match(download(row["name"]), row)
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        if sorted(bundle.namelist()) != sorted(row["covers"]):
            raise ValueError(f"Unexpected archive members: {row['name']}")
        return {name: bundle.read(name) for name in row["covers"]}


def git(*args):
    return subprocess.check_output(["git", "-C", str(PACK), *args])


def committed(path, revision):
    data = (PACK / path).read_bytes()
    if git("cat-file", "blob", f"{revision}:{path}") != data:
        raise ValueError(f"Working file differs from release commit: {path}")
    return data


def release_update(output, base_revision):
    import json

    revision = git("rev-parse", "HEAD").decode().strip()
    if revision == base_revision:
        raise ValueError("Commit the localization before staging the release")
    timestamp = datetime.fromtimestamp(int(git("show", "-s", "--format=%ct", revision)), timezone.utc)
    overlay = json.loads(committed("tools/overlay.json", revision))
    old_manifest = download("pack-manifest.json")
    manifest = json.loads(old_manifest)
    identity = (manifest["packId"], manifest["minecraftVersion"], manifest["loader"], manifest["revision"])
    if identity != ("minecraft-12", "1.18.2", {"type": "forge", "version": "40.2.34"}, base_revision):
        raise ValueError("Public base revision or platform changed")
    inventory = {row["path"]: row for row in manifest["files"]}
    replacements = {}
    additions = {}
    for row in overlay["bookLocalization"]:
        path = row["path"]
        data = match(committed(path, revision), row["output"])
        if "before" in row:
            if any(inventory[path][key] != value for key, value in row["before"].items()):
                raise ValueError(f"Unexpected base quest bytes: {path}")
            replacements[path] = data
        else:
            if path in inventory:
                raise ValueError(f"Language asset already present: {path}")
            additions[path] = data
    ownership = "launcher/pack-owned.txt"
    replacements[ownership] = committed(ownership, revision)
    patches = {row["path"]: row for row in overlay["patches"] if row["path"].startswith(QUESTS + "/")}
    output.mkdir()
    (output / "previous-manifest.json").write_bytes(old_manifest)
    asset_dir = output / "assets"
    asset_dir.mkdir()

    def write_asset(label, contents):
        data = archive(contents)
        info = fingerprint(data)
        name = f"r-{info['sha256'][:12]}-{label}.zip"
        (asset_dir / name).write_bytes(data)
        return {"name": name, "kind": "zipRoot", "covers": sorted(contents), **info}

    assets = []
    for asset in manifest["assets"]:
        touched = set(asset["covers"]) & (replacements.keys() | patches.keys())
        if not touched:
            assets.append(asset)
            continue
        contents = read_asset(asset)
        for path in touched:
            old = match(contents[path], inventory[path])
            if path in patches:
                row = patches[path]
                data = match(old, row["before"])
                for operation in row["replacements"]:
                    before = operation["from"].encode()
                    if data.count(before) != 1:
                        raise ValueError(f"Overlay replacement is ambiguous: {path}")
                    data = data.replace(before, operation["to"].encode(), 1)
                replacements[path] = match(data, row["after"])
            contents[path] = replacements[path]
        label = "inferno-quest-config" if any(path.startswith(QUESTS + "/") for path in touched) else "inferno-quest-owner"
        assets.append(write_asset(label, contents))
    assets.append(write_asset("inferno-quest-langs", additions))
    for path, data in {**replacements, **additions}.items():
        inventory[path] = {"path": path, **fingerprint(data)}
    if sorted(inventory) != sorted(path for asset in assets for path in asset["covers"]):
        raise ValueError("Manifest asset coverage does not match the payload")

    old = manifest["library"]
    with zipfile.ZipFile(io.BytesIO(match(download(old["name"]), old))) as library:
        card = json.loads(library.read("library.json"))
        if card["revision"] != base_revision or card["id"] != manifest["packId"]:
            raise ValueError("Public library revision or pack ID changed")
        card["revision"] = revision
        library_data = archive({"library.json": json_bytes(card), "preview.jpg": library.read("preview.jpg")})
    library_pin = fingerprint(library_data)
    library_name = f"library-{library_pin['sha256']}.zip"
    (asset_dir / library_name).write_bytes(library_data)
    manifest.update(revision=revision, generatedAtUtc=timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    library={"name": library_name, "revision": revision, **library_pin},
                    files=sorted(inventory.values(), key=lambda row: row["path"]),
                    assets=sorted(assets, key=lambda row: row["name"]))
    (output / "pack-manifest.json").write_bytes(json_bytes(manifest))
    print(revision, len(manifest["files"]), len(assets), fingerprint(json_bytes(manifest))["sha256"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--base", required=True, help="Expected current revision of pack-latest")
    args = parser.parse_args()
    release_update(args.output, args.base)
