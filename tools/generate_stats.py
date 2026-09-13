#!/usr/bin/env python3
import functools
import json
import os
import re
from pathlib import Path

CUSTOM_ICON_ENABLED = os.environ.get("SA_ICON") != "0"

ROOT = Path(__file__).resolve().parent.parent
STATS_DIR = ROOT / "src/Public/SharedActions/Stats/Generated/Data"
LOCALIZATION_ROOT = ROOT / "src/Mods/SharedActions/Localization"
LUA_DIR = ROOT / "src/Mods/SharedActions/ScriptExtender/Lua"
ITEM_ATLAS_LSX = ROOT / "src/Public/SharedActions/GUI/SharedActions_Items.lsx"
CATALOG_JSON = ROOT / "data/catalog.json"

LANGUAGES = {
    "English": ("label", "desc"),
    "BrazilianPortuguese": ("label_ptbr", "desc_ptbr"),
}

CATEGORIES = [
    {
        "key": "potions",
        "spell": "SA_TakePotion",
        "prefix": "SA_Potion_",
        "use_types": {"Potion"},
        "label": "Take Potion",
        "label_handle": "h366930b4g0001g4000g9000g366930b40001",
        "desc_handle": "h366930b4g0003g4000g9000g366930b40003",
        "desc": "Drink a potion carried by anyone in the party.",
        "label_ptbr": "Tomar Poção",
        "desc_ptbr": "Bebe uma poção carregada por qualquer membro do grupo.",
        "icon": "SharedActions_TakePotion" if CUSTOM_ICON_ENABLED else "Item_CONS_Potion_Healing_A",
        "use_costs": "BonusActionPoint:1",
        "families": {"BASE_ALCH_Solution_Elixir", "BASE_CONS_Drink_Potion",
                     "BASE_ALCH_Solution_Potion"},
    },
    {
        "key": "scrolls",
        "spell": "SA_UseScroll",
        "prefix": "SA_Scroll_",
        "use_types": {"Scroll"},
        "label": "Use Scroll",
        "label_handle": "h366930b4g0002g4000g9000g366930b40002",
        "desc_handle": "h366930b4g0004g4000g9000g366930b40004",
        "desc": "Use a scroll carried by anyone in the party.",
        "label_ptbr": "Usar Pergaminho",
        "desc_ptbr": "Usa um pergaminho carregado por qualquer membro do grupo.",
        "icon": "SharedActions_UseScroll" if CUSTOM_ICON_ENABLED else "Item_LOOT_SCROLL_Fireball",
        "use_costs": "ActionPoint:1",
        "families": {"BASE_BOOK_Scroll_Magic"},
        "inherits_item_spell": True,
    },
    {
        "key": "throwables",
        "spell": "SA_ThrowItem",
        "prefix": "SA_Throw_",
        "use_types": {"Potion", "Grenade", "Throwable"},
        "label": "Throw Item",
        "label_handle": "h366930b4g0007g4000g9000g366930b40007",
        "desc_handle": "h366930b4g0008g4000g9000g366930b40008",
        "desc": "Throw an item carried by anyone in the party.",
        "label_ptbr": "Arremessar",
        "desc_ptbr": "Arremessa um item carregado por qualquer membro do grupo.",
        "icon": "SharedActions_Throw" if CUSTOM_ICON_ENABLED else "Action_Throw",
        "use_costs": "ActionPoint:1",
        "families": set(),
        "inherits_projectile_spell": True,
        "force_use_costs": True,
        "overrides": {
            "TargetRadius": "ThrownObjectRange",
            "TargetConditions": "not Self()",
            "SpellFlags": ["IsHarmful", "RangeIgnoreVerticalThreshold",
                           "HasHighGroundRangeExtension", "IgnoreSilence", "IgnoreVisionBlock"],
        },
    },
]

ENABLED_CATEGORIES = {"potions", "scrolls", "throwables"}

DIG = {
    "spell": "SA_Dig",
    "vanilla_spell": "Target_Dig",
    "status": "HAS_SHOVEL",
    "tag": "SHOVEL_e2db698a-0705-43f4-9674-06fff1fd1e67",
    "label": "Dig",
    "label_handle": "h366930b4g0005g4000g9000g366930b40005",
    "desc_handle": "h366930b4g0006g4000g9000g366930b40006",
    "desc": "Dig with a shovel carried by anyone in the party.",
    "label_ptbr": "Cavar",
    "desc_ptbr": "Cava com uma pá carregada por qualquer membro do grupo.",
    "icon": "SharedActions_Dig" if CUSTOM_ICON_ENABLED else "Item_TOOL_GEN_Shovel_A",
}

BASE_ENTRY = "SA_Base"
BASE_SPELL_ANIMATION = ("03496c4a-49e0-4132-b585-3e5ecd1ad8e5,,;,,;"
                        "bcc3b0d9-f04f-4448-aab0-e0ad641167cc,,;"
                        "bf924cc6-8b39-4c3b-b1c0-eda264cf6150,,;"
                        "a9682ef9-5d9e-4ac0-8144-2c7fe6eb868c,,;,,;"
                        "32fb4d91-7fde-4b05-9144-ea87b9a4284a,,;,,")

RUNTIME_TABLES = ["TemplateToSpell", "SpellToTemplate", "SpellContainer", "Labels",
                  "LegacySpells"]

MAP_KEY_PATTERN = re.compile(r'MapKey" type="FixedString" value="([^"]+)"')


@functools.lru_cache(maxsize=1)
def atlas_icon_keys():
    if not CUSTOM_ICON_ENABLED or not ITEM_ATLAS_LSX.exists():
        return frozenset()
    return frozenset(MAP_KEY_PATTERN.findall(ITEM_ATLAS_LSX.read_text(encoding="utf-8")))


@functools.lru_cache(maxsize=1)
def projectile_spells():
    if not any(c.get("inherits_projectile_spell") for c in enabled_categories()):
        return {}
    if not CATALOG_JSON.exists():
        raise SystemExit(f"{CATALOG_JSON} não existe: rode python3 tools/collect.py")
    catalog = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    spells = {item["template"]: item["spell"] for item in catalog.get("throwables", [])}
    if not spells:
        raise SystemExit(
            "catalog.json sem throwables: o arremesso herda o spell que o item dispara "
            "ao quebrar, e esse dado não é legível em runtime — rode python3 tools/collect.py")
    return spells


def enabled_categories():
    return [c for c in CATEGORIES if c["key"] in ENABLED_CATEGORIES]


def atlas_icon_key(stat):
    return "SA_Icon_" + stat


def category_items(category, catalog):
    items = catalog.get(category["key"], [])
    if category["families"]:
        items = [i for i in items if i["family"] in category["families"]]
    if category.get("inherits_item_spell") or category.get("inherits_projectile_spell"):
        items = [i for i in items if i["spell"]]
    return items


def removes_item_on_cast(category):
    return bool(category.get("inherits_item_spell") or category.get("inherits_projectile_spell"))


def lua_flag(category, field):
    return str(bool(category.get(field))).lower()


def lua_value(value):
    if isinstance(value, str):
        return f'"{value}"'
    return "{ " + ", ".join(f'"{item}"' for item in value) + " }"


def emit_base_entry():
    return "\n".join([
        f'new entry "{BASE_ENTRY}"',
        'type "SpellData"',
        'data "SpellType" "Shout"',
        'data "Level" "0"',
        'data "SpellSchool" "None"',
        'data "TargetConditions" "Self()"',
        f'data "SpellAnimation" "{BASE_SPELL_ANIMATION}"',
        'data "CastTextEvent" "Cast"',
        'data "HitAnimationType" "None"',
        'data "VerbalIntent" "Utility"',
        'data "SpellFlags" "ImmediateCast;UnavailableInDialogs"',
        'data "Icon" "Action_Hide"',
        "",
    ])


def emit_container(category):
    return "\n".join([
        f'new entry "{category["spell"]}"',
        'type "SpellData"',
        f'using "{BASE_ENTRY}"',
        'data "ContainerSpells" ""',
        f'data "UseCosts" "{category["use_costs"]}"',
        f'data "Icon" "{category["icon"]}"',
        f'data "DisplayName" "{category["label_handle"]};1"',
        f'data "Description" "{category["desc_handle"]};1"',
        'data "SpellFlags" "IsLinkedSpellContainer;UnavailableInDialogs"',
        "",
    ])


def emit_dig_entry():
    return "\n".join([
        f'new entry "{DIG["spell"]}"',
        'type "SpellData"',
        f'using "{DIG["vanilla_spell"]}"',
        f'data "Icon" "{DIG["icon"]}"',
        f'data "DisplayName" "{DIG["label_handle"]};1"',
        f'data "Description" "{DIG["desc_handle"]};1"',
        "",
    ])


def emit_dig_lua():
    return "\n".join([
        "Catalog.Dig = {",
        f'    spell = "{DIG["spell"]}",',
        f'    vanillaSpell = "{DIG["vanilla_spell"]}",',
        f'    status = "{DIG["status"]}",',
        f'    tag = "{DIG["tag"]}",',
        "}",
        "",
    ])


def emit_catalog_lua():
    lines = ["Catalog = {}", "", f'Catalog.BaseEntry = "{BASE_ENTRY}"', "",
             "Catalog.Containers = {"]
    lines += [f'    "{c["spell"]}",' for c in enabled_categories()]

    lines += ["}", "", "Catalog.RemovesItemOnCast = {"]
    lines += [f'    ["{c["spell"]}"] = true,'
              for c in enabled_categories() if removes_item_on_cast(c)]

    lines += ["}", "", "Catalog.Categories = {"]
    for category in enabled_categories():
        lines += [
            "    {",
            f'        container = "{category["spell"]}",',
            f'        prefix = "{category["prefix"]}",',
            f'        inheritsItemSpell = {lua_flag(category, "inherits_item_spell")},',
            f'        inheritsProjectileSpell = '
            f'{lua_flag(category, "inherits_projectile_spell")},',
            "        useTypes = {",
        ]
        lines += [f'            ["{use_type}"] = true,'
                  for use_type in sorted(category["use_types"])]
        lines += ["        },", "        families = {"]
        lines += [f'            ["{family}"] = true,' for family in sorted(category["families"])]
        lines += ["        },"]
        if category.get("force_use_costs"):
            lines += [f'        forcedUseCosts = "{category["use_costs"]}",']
        lines += ["        overrides = {"]
        lines += [f"            {field} = {lua_value(value)},"
                  for field, value in sorted(category.get("overrides", {}).items())]
        lines += ["        },", "    },"]

    lines += ["}", "", "Catalog.IconKeys = {"]
    lines += [f'    ["{key}"] = true,' for key in sorted(atlas_icon_keys())]

    lines += ["}", "", "Catalog.ProjectileSpells = {"]
    lines += [f'    ["{guid}"] = "{spell}",' for guid, spell in sorted(projectile_spells().items())]

    lines += ["}", ""]
    lines += [f"Catalog.{table} = {{}}" for table in RUNTIME_TABLES]
    lines += ["", emit_dig_lua()]
    return "\n".join(lines)


def main():
    for directory in (STATS_DIR, LUA_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    entries = [emit_base_entry()]
    localization = {lang: ['<?xml version="1.0" encoding="utf-8"?>', "<contentList>"]
                    for lang in LANGUAGES}

    for category in enabled_categories():
        entries.append(emit_container(category))
        for lang, (label_key, desc_key) in LANGUAGES.items():
            localization[lang].append(
                f'\t<content contentuid="{category["label_handle"]}" version="1">'
                f'{category[label_key]}</content>')
            localization[lang].append(
                f'\t<content contentuid="{category["desc_handle"]}" version="1">'
                f'{category[desc_key]}</content>')
        print(f'{category["spell"]}: container vazio, preenchido em runtime')

    for lang, (label_key, desc_key) in LANGUAGES.items():
        localization[lang].append(
            f'\t<content contentuid="{DIG["label_handle"]}" version="1">'
            f'{DIG[label_key]}</content>')
        localization[lang].append(
            f'\t<content contentuid="{DIG["desc_handle"]}" version="1">'
            f'{DIG[desc_key]}</content>')

    for stale in STATS_DIR.glob("Spell_*.txt"):
        stale.unlink()
    (STATS_DIR / "Spell_Shout.txt").write_text("\n".join(entries), encoding="utf-8")
    (STATS_DIR / "Spell_Target.txt").write_text(emit_dig_entry(), encoding="utf-8")
    print(f'{DIG["spell"]}: herda {DIG["vanilla_spell"]}, concedida por {DIG["status"]}')

    for lang, lines in localization.items():
        directory = LOCALIZATION_ROOT / lang
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SharedActions.xml").write_text(
            "\n".join(lines + ["</contentList>"]) + "\n", encoding="utf-8")

    (LUA_DIR / "Catalog.lua").write_text(emit_catalog_lua(), encoding="utf-8")
    print(f"atlas: {len(atlas_icon_keys())} chaves de icone "
          f"| arremesso: {len(projectile_spells())} templates com ProjectileSpell "
          f"| sub-spells: criados em runtime")


if __name__ == "__main__":
    main()
