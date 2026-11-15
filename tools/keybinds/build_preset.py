"""Generate the 1.18.2 Forge options-format preset from the reviewed inventory."""
from collections import Counter
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "launcher/controls-preset.txt"
UNKNOWN = "key.keyboard.unknown"
VANILLA_COUNT = 34
SPECIAL = {"NONE", "CONTROL", "SHIFT", "ALT"}
UNSUPPORTED = {
    "minetogether:keybind.friend_chat",
    "minetogether:keybind.global_chat",
    "minetogether:keybind.settings",
}
DUPLICATES = {"key.evilcraft.fart", "key.evilcraft.exaltedCrafting"}

# Values are the physical keys. No modifier chords or shared keys are needed.
LAYOUT = {
    "key.ftbquests.quests": "g",
    "key.ftbchunks.map": "m",
    "key.ftbchunks.minimap.zoomIn": "equal",
    "key.ftbchunks.minimap.zoomOut": "minus",
    "key.ftbultimine": "grave.accent",
    "key.findme.search": "y",
    "key.lightoverlay.enable_overlay": "f7",
    "key.ftbteams.open_gui": "f8",
    "key.jei.toggleOverlay": "o",
    "key.jei.focusSearch": "f6",
    "key.jei.bookmark": "j",
    "key.jei.showRecipe": "r",
    "key.jei.showUses": "u",
    "key.jei.recipeBack": "backspace",
    "key.jei.previousRecipePage": "page.up",
    "key.jei.nextRecipePage": "page.down",
    "key.jei.closeRecipeGui": "escape",
    "key.curios.open.desc": "i",
    "keybind.sophisticatedbackpacks.open_backpack": "b",
    "keybind.sophisticatedbackpacks.inventory_interaction": "apostrophe",
    "key.occultism.backpack": "comma",
    "key.occultism.storage_remote": "n",
    "key.ars_nouveau.open_book": "h",
    "key.ars_nouveau.selection_hud": "v",
    "key.ars_nouveau.previous_slot": "left.bracket",
    "key.ars_nouveau.next_slot": "right.bracket",
    "key.ars_nouveau.switch_armarium_slot": "semicolon",
    "key.buildinggadgets.settings_menu": "k",
    "key.buildinggadgets.undo": "delete",
    "key.buildinggadgets.material_list": "insert",
    "key.hexerei.glasses_zoom": "z",
    "key.enchanted.broom_forward": "up",
    "key.enchanted.broom_backward": "down",
    "key.enchanted.broom_turn_left": "left",
    "key.enchanted.broom_turn_right": "right",
    "key.enchanted.broom_up": "home",
    "key.enchanted.broom_down": "end",
    "key.enchanted.broom_aim_up": "keypad.add",
    "key.enchanted.broom_aim_down": "keypad.subtract",
    "key.hexerei.broomDescend": "period",
    "key.boththrow.desc": "key.mouse.4",
    "key.jumpanddetach.desc": "key.mouse.5",
    "key.motoronoff.desc": "key.mouse.6",
    "key.slow.desc": "key.mouse.7",
    "key.climb.desc": "key.mouse.8",
    "key.enderlaunch.desc": "keypad.1",
    "key.rocket.desc": "keypad.2",
    "key.slide.desc": "keypad.3",
    "key.carry.desc": "left.alt",
    "create.keyinfo.ponder": "right.alt",
    "create.keyinfo.toolmenu": "right.control",
    "create.keyinfo.toolbelt": "right.shift",
    "key.nextDestination": "keypad.6",
    "key.prevDestination": "keypad.4",
    "key.unmountVehicle": "backslash",
    "key.openManual": "f1",
    "quark.keybind.lock_rotation": "keypad.5",
    "key.tconstruct.leggings_interact": "keypad.7",
    "key.tconstruct.helmet_interact": "keypad.8",
    "key.cofh.mode_change_increment": "keypad.9",
    "key.cofh.mode_change_decrement": "keypad.0",
    "iris.keybind.shaderPackSelection": "f10",
    "quark.keybind.camera_mode": "f12",
}


def inventory():
    rows = []
    for line in (HERE / "registered-keys.txt").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"key_(.+):(key\.(?:keyboard|mouse)\.[a-z0-9.]+)(?::([A-Z]+))?", line)
        if not match:
            raise ValueError(f"Malformed native row: {line}")
        name, key, modifier = match.groups()
        if modifier and modifier not in SPECIAL:
            raise ValueError(f"Unknown modifier: {line}")
        rows.append((name, key, modifier))
    return rows


def build():
    rows = inventory()
    counts = Counter(name for name, _, _ in rows)
    if {name for name, count in counts.items() if count > 1} != DUPLICATES:
        raise ValueError("Native duplicate mappings changed")
    if {name for name in counts if ":" in name} != UNSUPPORTED:
        raise ValueError("Options names with embedded separators changed")
    vanilla = dict((name, key) for name, key, _ in rows[:VANILLA_COUNT])
    if len(vanilla) != VANILLA_COUNT or not LAYOUT.keys() <= counts.keys() - DUPLICATES - UNSUPPORTED - vanilla.keys():
        raise ValueError("Layout references an unknown, reserved or ambiguous name")
    result = {name: UNKNOWN for name in counts if name not in UNSUPPORTED}
    result.update(vanilla)
    result.update({name: key if key.startswith("key.") else "key.keyboard." + key
                   for name, key in LAYOUT.items()})
    return result


def render(mappings):
    return "".join(f"key_{name}:{key}\n" for name, key in mappings.items()).encode("utf-8")


if __name__ == "__main__":
    OUTPUT.write_bytes(render(build()))
