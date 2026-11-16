"""Prepare a full author release with the pack-owned multiplayer setting."""

import argparse
from codecs import BOM_UTF8
import io
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from stage_shader_update import archive, match, pin


PACK = Path(__file__).resolve().parents[1]
OPTIONS = "launcher/options-default.txt"
MANIFEST = "pack-manifest.json"
SETTING = b"!skipMultiplayerWarning:true"
PLATFORM = ("1.18.2", {"type": "forge", "version": "40.2.34"})
WARNING = re.compile(rb"^[ \t]*!?[ \t]*skipMultiplayerWarning[ \t]*:")


def apply_setting(author, required):
    if required != SETTING + b"\n":
        raise ValueError("The pack policy must set only skipMultiplayerWarning:true")
    bom = BOM_UTF8 if author.startswith(BOM_UTF8) else b""
    author = author[len(bom):]
    lines = author.splitlines(keepends=True)
    matching = [index for index, line in enumerate(lines) if WARNING.match(line)]
    if matching:
        for index in matching:
            line = lines[index]
            ending = line[len(line.rstrip(b"\r\n")):]
            lines[index] = SETTING + ending
        return bom + b"".join(lines)
    separator = b"\r\n" if b"\r\n" in author else b"\n"
    return bom + author + (separator if author and not author.endswith(b"\n") else b"") + SETTING + separator


def verify(manifest, read_asset, expected):
    files = [row for row in manifest["files"] if row["path"] == OPTIONS]
    assets = [row for row in manifest["assets"] if OPTIONS in row["covers"]]
    if len(files) != 1 or len(assets) != 1 or assets[0]["covers"] != [OPTIONS]:
        raise ValueError("The prepared release must include exactly one multiplayer settings file")
    with ZipFile(io.BytesIO(match(read_asset(assets[0]["name"]), assets[0]))) as bundle:
        if bundle.namelist() != [OPTIONS]:
            raise ValueError("Unexpected multiplayer settings archive members")
        data = match(bundle.read(OPTIONS), files[0])
    if data != expected or apply_setting(data, SETTING + b"\n") != data:
        raise ValueError("Prepared release lost the required multiplayer setting")


def apply_release(output, required):
    path = output / MANIFEST
    manifest = json.loads(path.read_bytes())
    if (manifest["minecraftVersion"], manifest["loader"]) != PLATFORM:
        raise ValueError("Review the multiplayer warning on the new game platform before release")
    assets_dir = output / "assets"
    files = {row["path"]: row for row in manifest["files"]}
    carriers = [row for row in manifest["assets"] if OPTIONS in row["covers"]]
    if len(carriers) != int(OPTIONS in files):
        raise ValueError("Invalid author controls inventory")
    assets = [row for row in manifest["assets"] if OPTIONS not in row["covers"]]
    output_assets = {}
    author = b""

    def add(label, contents):
        payload = archive(contents)
        payload_pin = pin(payload)
        name = f"r-{payload_pin['sha256'][:12]}-{label}.zip"
        assets.append({"name": name, "kind": "zipRoot", "covers": sorted(contents), **payload_pin})
        output_assets[name] = payload

    if carriers:
        row = carriers[0]
        with ZipFile(io.BytesIO(match((assets_dir / row["name"]).read_bytes(), row))) as bundle:
            if sorted(bundle.namelist()) != sorted(row["covers"]):
                raise ValueError("Unexpected author archive members")
            contents = {name: match(bundle.read(name), files[name]) for name in row["covers"]}
        author = contents.pop(OPTIONS)
        if contents:
            add("author-launcher", contents)

    expected = apply_setting(author, required)
    add("options-default", {OPTIONS: expected})
    files[OPTIONS] = {"path": OPTIONS, **pin(expected)}
    if sorted(files) != sorted(name for row in assets for name in row["covers"]):
        raise ValueError("Asset coverage changed while applying the pack policy")
    manifest["files"] = sorted(files.values(), key=lambda row: row["path"])
    manifest["assets"] = sorted(assets, key=lambda row: row["name"])
    verify(manifest, output_assets.__getitem__, expected)
    for name, payload in output_assets.items():
        (assets_dir / name).write_bytes(payload)
    for row in carriers:
        if row["name"] not in output_assets:
            (assets_dir / row["name"]).unlink()
    verify(manifest, lambda name: (assets_dir / name).read_bytes(), expected)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return files[OPTIONS]["sha256"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher-source", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    required = (PACK / OPTIONS).read_bytes()
    committed = subprocess.check_output(["git", "-C", str(PACK), "cat-file", "blob", f"{args.revision}:{OPTIONS}"])
    if required != committed:
        raise ValueError("Multiplayer policy differs from the release commit")
    apply_setting(b"", required)
    if args.output.exists():
        raise ValueError("Select a new output directory")
    with TemporaryDirectory(prefix=".inferno-author-", dir=args.output.parent) as tmp:
        candidate = Path(tmp) / "release"
        subprocess.run(
            [sys.executable, "-B", str(args.launcher_source / "tools/PackData/CurseForge/stage_release.py"),
             "--pack-source", str(PACK), "--stage", str(args.stage), "--output", str(candidate),
             "--revision", args.revision, "--id", "minecraft-12"],
            check=True,
        )
        sha256 = apply_release(candidate, required)
        candidate.rename(args.output)
    print(OPTIONS, sha256)



if __name__ == "__main__":
    main()
