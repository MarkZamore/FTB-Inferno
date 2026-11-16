from codecs import BOM_UTF8
import json
from pathlib import Path
import tempfile
import unittest

from prepare_author_release import OPTIONS, PLATFORM, SETTING, apply_release, apply_setting, verify
from stage_shader_update import archive, pin


class AuthorReleaseTests(unittest.TestCase):
    def candidate(self, directory, options):
        config = "config/defaultoptions/options.txt"
        other = "launcher/jvm-args.txt"
        groups = [{"author-config.zip": {config: b"difficulty:3\n"}},
                  {"author-launcher.zip": {other: b"-Dexample=true\n"}}]
        if options is not None:
            groups[1]["author-launcher.zip"][OPTIONS] = options
        (directory / "assets").mkdir()
        files, assets = [], []
        for group in groups:
            for name, contents in group.items():
                payload = archive(contents)
                (directory / "assets" / name).write_bytes(payload)
                assets.append({"name": name, "kind": "zipRoot", "covers": sorted(contents), **pin(payload)})
                files.extend({"path": path, **pin(data)} for path, data in contents.items())
        manifest = dict(zip(("minecraftVersion", "loader"), PLATFORM), files=files, assets=assets)
        (directory / "pack-manifest.json").write_text(json.dumps(manifest), encoding="utf8")
        return {row["path"]: row for row in files if row["path"] != OPTIONS}

    def test_author_update_preserves_other_settings(self):
        for author in (None, b"difficulty:3\r\nlang:ru_ru\r\n",
                       b"lang:ru_ru\r\nskipMultiplayerWarning:false\r\nrenderDistance:9"):
            with self.subTest(author=author), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                other = self.candidate(root, author)
                required = SETTING + b"\n"
                apply_release(root, required)
                m = json.loads((root / "pack-manifest.json").read_bytes())
                self.assertEqual(other, {row["path"]: row for row in m["files"] if row["path"] != OPTIONS})
                self.assertEqual([row["name"] for row in m["assets"] if row["covers"] ==
                                  ["config/defaultoptions/options.txt"]], ["author-config.zip"])
                expected = apply_setting(author or b"", required)
                verify(m, lambda name: (root / "assets" / name).read_bytes(), expected)
                if author is not None:
                    self.assertEqual(
                        [line for line in expected.splitlines() if line != SETTING],
                        [line for line in author.splitlines() if line != b"skipMultiplayerWarning:false"],
                    )

    def test_preserves_bom_and_updates_first_setting(self):
        author = BOM_UTF8 + b"skipMultiplayerWarning:false\r\nlang:ru_ru\r\n"
        self.assertEqual(apply_setting(author, SETTING + b"\n"),
                         BOM_UTF8 + SETTING + b"\r\nlang:ru_ru\r\n")

    def test_verify_rejects_missing_or_disabled_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.candidate(root, None)
            manifest = json.loads((root / "pack-manifest.json").read_bytes())
            with self.assertRaisesRegex(ValueError, "exactly one"):
                verify(manifest, lambda _: b"", SETTING + b"\n")
        disabled = b"!skipMultiplayerWarning:false\n"
        payload = archive({OPTIONS: disabled})
        m = {"files": [{"path": OPTIONS, **pin(disabled)}],
             "assets": [{"name": "options.zip", "covers": [OPTIONS], **pin(payload)}]}
        with self.assertRaisesRegex(ValueError, "lost the required"):
            verify(m, lambda _: payload, SETTING + b"\n")


if __name__ == "__main__":
    unittest.main()
