"""Build the bilingual FTB Inferno quest book from verified author SNBT."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import re


PACK = Path(__file__).resolve().parents[2]
QUESTS = "config/ftbquests/quests"
LANG = "kubejs/assets/inferno_quests/lang"
RUNTIME = ("mods/ftb-quests-forge-", "mods/ftb-library-forge-", "mods/kubejs-forge-")
TOKEN = re.compile(r"""\s+|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|[{}\[\]:,;]|[\w.+-]+""")
FORMAT = re.compile(r"(?<!\\)[&§](?:#[0-9a-fA-F]{6}|[0-9a-fk-or])")
URL = re.compile(r"https?://[^\s{}]+")
SUBSTITUTION = re.compile(r"(?<!\\)\{([^{}]+)\}")
DIGEST_FIELDS = ("sizeBytes", "sha256")


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate JSON key")
    return result


def read_json(path):
    return json.loads(path.read_bytes(), object_pairs_hook=unique_object)


def fingerprint(data):
    return {"sizeBytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def pinned_bytes(path, pin):
    data = path.read_bytes()
    if fingerprint(data) != pin:
        raise ValueError(f"Author bytes differ from the lock: {path}")
    return data


def decode_string(token):
    # SNBT escapes only its own quote and backslash, with literal Unicode.
    quote = token[0]
    return re.sub(r"\\([" + re.escape(quote) + r"\\])", r"\1", token[1:-1])


def encode_string(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def quest_text(data):
    """Yield (start, end, field, text) from string fields, skipping item NBT."""
    tokens = []
    cursor = 0
    for match in TOKEN.finditer(data):
        if match.start() != cursor:
            raise ValueError(f"Unexpected SNBT at offset {cursor}")
        cursor = match.end()
        if not match[0].isspace():
            tokens.append(match)
    if cursor != len(data):
        raise ValueError(f"Incomplete SNBT at offset {cursor}")

    def walk(index, field=None, skip=False):
        token = tokens[index][0]
        index += 1
        if token == "{":
            while tokens[index][0] != "}":
                key = tokens[index][0]
                if key == ",":
                    index += 1
                    continue
                if key[0] in "\"'":
                    key = decode_string(key)
                if tokens[index + 1][0] != ":":
                    raise ValueError(f"Expected SNBT key at {tokens[index].start()}")
                index = walk(index + 2, key, skip or key in {"tag", "item", "icon"})
        elif token == "[":
            while tokens[index][0] != "]":
                index = index + 1 if tokens[index][0] in {",", ";"} else walk(index, field, skip)
        else:
            match = tokens[index - 1]
            if not skip and token[0] in "\"'" and field in {"title", "subtitle", "description", "hover"}:
                text = decode_string(token)
                if text.strip() and not re.fullmatch(r"\{image:[^{}]+\}", text):
                    yield_to.append((match.start(), match.end(), field, text))
            return index
        return index + 1

    yield_to = []
    if walk(0) != len(tokens):
        raise ValueError("Unexpected trailing SNBT")
    return yield_to


def localized_field(source, target, field, key):
    if not isinstance(target, str) or not target.strip():
        raise ValueError(f"Empty Russian value for {key}")
    if Counter(FORMAT.findall(source)) != Counter(FORMAT.findall(target)):
        raise ValueError(f"Formatting differs for {key}: {source!r}")
    if URL.findall(source) != URL.findall(target) or SUBSTITUTION.findall(source) != SUBSTITUTION.findall(target):
        raise ValueError(f"Link or substitution differs for {key}: {source!r}")
    if field == "hover":
        # ChapterImageButton recognizes a leading/trailing brace as a translation key.
        return "{" + key + "}", source, target
    if FORMAT.search(source) or SUBSTITUTION.search(source) or r"\n" in source or re.search(r"\\[&§{}]", source):
        # The 1.18.2 FTB Library parser resolves {key} with I18n and parses the
        # expansion again, retaining the original legacy styles and components.
        return "{" + key + "}", source.replace("%", "%%"), target.replace("%", "%%")
    # Vanilla translatable components carry keys through the server/client sync.
    # FTB Quests' raw text parser handles JSON before its legacy parser.
    return json.dumps({"translate": key}, separators=(",", ":")), source, target


def inputs(lock):
    root = QUESTS + "/"
    authors = {
        row["path"]: {key: row[key] for key in DIGEST_FIELDS}
        for row in lock["overrides"]
        if row["path"].startswith(root) and row["path"].endswith(".snbt")
    }
    runtime = {
        row["path"]: {key: row[key] for key in (*DIGEST_FIELDS, "projectId", "fileId")}
        for row in lock["files"] if row["path"].startswith(RUNTIME)
    }
    if len(runtime) != len(RUNTIME) or not authors:
        raise ValueError("Review the author FTB Quests, Library and KubeJS versions")
    return authors, runtime


def compile_book(path, source, translations):
    translated = []
    english = {}
    russian = {}
    cursor = 0
    field_key = PurePosixPath(path).relative_to(QUESTS).with_suffix("").as_posix().replace("/", ".")
    replacements = []
    fields = quest_text(source)
    expected = {text for _, _, _, text in fields}
    if translations.keys() != expected:
        raise ValueError(f"{path}: missing {sorted(expected - translations.keys())!r}; "
                         f"extra {sorted(translations.keys() - expected)!r}")
    for number, (start, end, field, text) in enumerate(fields, 1):
        key = f"inferno_quests.{field_key}.{number}"
        replacement, english[key], russian[key] = localized_field(text, translations[text], field, key)
        token = encode_string(replacement)
        translated.extend((source[cursor:start], token))
        replacements.append({"from": source[start:end], "to": token})
        cursor = end
    translated.append(source[cursor:])
    return "".join(translated).encode(), english, russian, replacements


def build(game, action, output):
    lock = read_json(PACK / "tools/upstream-lock.json")
    author, runtime = inputs(lock)
    if action == "extract":
        output.mkdir(parents=True, exist_ok=False)
    overlay = read_json(PACK / "tools/overlay.json") if action != "extract" else {}
    russian = {}
    english = {}
    files = {}
    recipe = []
    book_patches = []
    for path, pin in sorted(author.items()):
        original = pinned_bytes(game / path, pin)
        source = original.decode()
        relative = PurePosixPath(path).relative_to(QUESTS).with_suffix(".json")
        fields = quest_text(source)
        if action == "extract":
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(json_bytes(list(dict.fromkeys(text for _, _, _, text in fields))))
            continue
        if not fields:
            continue
        translations = read_json(Path(__file__).parent / "ru" / relative)
        generated, en, ru, replacements = compile_book(path, source, translations)
        english.update(en)
        russian.update(ru)
        files[path] = generated
        if re.fullmatch(r"config/ftbquests/quests/(?:chapter_groups|chapters/[a-z0-9_.-]+)\.snbt", path):
            recipe.append({"path": path, "before": pin, "inputs": {path: pin}, "output": fingerprint(generated)})
        else:
            # data.snbt and reward tables use the exact byte replacement support
            # already provided by the generic CurseForge overlay.
            current = source
            for change in replacements:
                before, after = change["from"], change["to"]
                if current.count(before) != 1:
                    raise ValueError(f"{path}: ambiguous exact text {before!r}")
                current = current.replace(before, after, 1)
            if current.encode() != generated:
                raise ValueError(f"{path}: patch would alter a non-display field")
            book_patches.append({"path": path, "before": pin, "after": fingerprint(generated),
                                 "replacements": replacements})

    if action == "extract":
        return
    for locale, values in (("en_us", english), ("ru_ru", russian)):
        path = f"{LANG}/{locale}.json"
        files[path] = json_bytes(values)
        recipe.append({"path": path, "inputs": {**author, **runtime}, "output": fingerprint(files[path])})
    prior_book_paths = {row["path"] for row in overlay.get("bookLocalization", [])}
    prior_ownership = (PACK / "launcher/pack-owned.txt").read_text(encoding="utf-8").splitlines()
    previous_patches = [row for row in overlay["patches"] if not row["path"].startswith(QUESTS + "/")]
    owned = {name for name in prior_ownership if name not in prior_book_paths and not name.startswith(QUESTS + "/")}
    owned.update(files)
    overlay["authorArchiveSha256"] = lock["client"]["sha256"]
    overlay["patches"] = previous_patches + book_patches
    overlay["bookLocalization"] = recipe
    files["launcher/pack-owned.txt"] = ("\n".join(sorted(owned)) + "\n").encode()
    files["tools/overlay.json"] = json_bytes(overlay)
    patch_paths = {row["path"] for row in book_patches}
    for path, data in files.items():
        if path in patch_paths:
            # Packaged via overlay patches, no duplicate generated copy in Git.
            continue
        target = PACK / path
        if action == "write":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        elif target.read_bytes() != data:
            raise ValueError(f"Generated localization is stale: {path}")
    print(f"{len(english)} localized fields across {len(files) - 4} author SNBT files")


def review_update(candidate_path, release_overlay):
    current = read_json(PACK / "tools/upstream-lock.json")
    candidate = read_json(candidate_path)
    def quest_inventory(lock):
        return {row["path"]: {key: row[key] for key in DIGEST_FIELDS}
                for row in lock["overrides"] if row["path"].startswith(QUESTS + "/")
                and row["path"].endswith(".snbt")}

    original_book = quest_inventory(current)
    new_book = quest_inventory(candidate)
    changed = sorted(path for path in original_book.keys() | new_book.keys()
                     if original_book.get(path) != new_book.get(path))
    if changed:
        raise ValueError("Quest book changed. Reconcile the translations before author update:\n"
                         + "\n".join(changed))
    subprocess.run([sys.executable, "-B", str(release_overlay), "review-update", "--pack-source",
                    str(PACK), "--candidate-lock", str(candidate_path)], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("extract", "write", "verify"):
        command = commands.add_parser(action)
        command.add_argument("game", type=Path, help="Verified unmodified author game directory")
        if action == "extract":
            command.add_argument("--output", type=Path, required=True)
    review = commands.add_parser("review-update")
    review.add_argument("candidate_lock", type=Path)
    review.add_argument("--release-overlay", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "review-update":
        review_update(args.candidate_lock, args.release_overlay)
    else:
        build(args.game, args.action, getattr(args, "output", None))
