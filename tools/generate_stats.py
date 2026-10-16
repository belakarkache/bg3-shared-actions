#!/usr/bin/env python3
import functools
import json
import os
import re
from pathlib import Path

from collect import GAMEDATA, SPELL_FILES, parse_stat_entries

CUSTOM_ICON_ENABLED = os.environ.get("SA_ICON") != "0"

ROOT = Path(__file__).resolve().parent.parent
STATS_DIR = ROOT / "src/Public/SharedActions/Stats/Generated/Data"
LOCALIZATION_ROOT = ROOT / "src/Mods/SharedActions/Localization"
LUA_DIR = ROOT / "src/Mods/SharedActions/ScriptExtender/Lua"
ITEM_ATLAS_LSX = ROOT / "src/Public/SharedActions/GUI/SharedActions_Items.lsx"
CATALOG_JSON = ROOT / "data/catalog.json"
SPELLS_JSON = ROOT / "data/spells.json"
STATS_FILE = "Spell_Shout.txt"
EXPORT_COMMAND = "!sa_export"

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
        "key": "arrows",
        "spell": "SA_Quiver",
        "prefix": "SA_Arrow_",
        "use_types": {"Arrow"},
        "label": "Quiver",
        "label_handle": "h366930b4g0009g4000g9000g366930b40009",
        "desc_handle": "h366930b4g000ag4000g9000g366930b4000a",
        "desc": "Shoot a special arrow carried by anyone in the party.",
        "label_ptbr": "Aljava",
        "desc_ptbr": "Dispara uma flecha especial carregada por qualquer membro do grupo.",
        "icon": "SharedActions_Quiver" if CUSTOM_ICON_ENABLED else "Item_ARR_Arrow_Of_Piercing",
        "use_costs": "ActionPoint:1",
        "families": {"BASE_LOOT_Arrow"},
        "inherits_item_spell": True,
    },
]

ENABLED_CATEGORIES = {"potions", "scrolls", "arrows"}

THROW_BASE_SPELL = "SA_ThrowBase"
NATIVE_THROW_ENTRY = "Throw_Throw"
THROW_CONTAINER = {
    "spell": "SA_ThrowItems",
    "use_costs": "ActionPoint:1",
    "icon": "SharedActions_Throw" if CUSTOM_ICON_ENABLED else "Action_Throw",
    "label_handle": "h366930b4g0007g4000g9000g366930b40007",
    "desc_handle": "h366930b4g0008g4000g9000g366930b40008",
    "label": "Throw",
    "desc": "Throw an item carried by anyone in the party.",
    "label_ptbr": "Arremessar",
    "desc_ptbr": "Arremessa um item carregado por qualquer membro do grupo.",
}

BASE_ENTRY = "SA_Base"
BASE_SPELL_ANIMATION = ("03496c4a-49e0-4132-b585-3e5ecd1ad8e5,,;,,;"
                        "bcc3b0d9-f04f-4448-aab0-e0ad641167cc,,;"
                        "bf924cc6-8b39-4c3b-b1c0-eda264cf6150,,;"
                        "a9682ef9-5d9e-4ac0-8144-2c7fe6eb868c,,;,,;"
                        "32fb4d91-7fde-4b05-9144-ea87b9a4284a,,;,,")

RUNTIME_TABLES = ["TemplateToSpell", "SpellToTemplate", "SpellContainer", "Labels",
                  "LegacySpells", "ScrollVariants", "VariantGroupOf"]

MAP_KEY_PATTERN = re.compile(r'MapKey" type="FixedString" value="([^"]+)"')
UNVERSIONED_LOCA_HANDLE = re.compile(r"h[0-9a-g]{36}")


@functools.lru_cache(maxsize=1)
def atlas_icon_keys():
    if not CUSTOM_ICON_ENABLED or not ITEM_ATLAS_LSX.exists():
        return frozenset()
    return frozenset(MAP_KEY_PATTERN.findall(ITEM_ATLAS_LSX.read_text(encoding="utf-8")))


@functools.lru_cache(maxsize=1)
def throwable_templates():
    if not CATALOG_JSON.exists():
        raise SystemExit(f"{CATALOG_JSON} não existe: rode python3 tools/collect.py")
    catalog = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    templates = {}
    for item in catalog.get("throwables", []):
        templates[item["template"]] = templates.get(item["template"]) or item["spell"]
    if not templates:
        raise SystemExit(
            "catalog.json sem throwables: o painel de arremesso precisa saber quais itens têm "
            "efeito ao quebrar (ProjectileSpell no nó Scripts, ilegível em runtime) — "
            "rode python3 tools/collect.py")
    return templates


@functools.lru_cache(maxsize=1)
def vanilla_spells():
    if not SPELL_FILES:
        raise SystemExit(f"sem dados do jogo em {GAMEDATA} — aponte BG3_DATA para os .pak extraídos")
    return frozenset(parse_stat_entries(SPELL_FILES))


def inherits_from_game_or_self(spell):
    parent = spell["parent"]
    return parent.startswith("SA_") or parent in vanilla_spells()


def exported_sub_spells():
    if not SPELLS_JSON.exists():
        print(f"ALERTA: {SPELLS_JSON} não existe — o pak sai sem sub-spells. No jogo, console do "
              f"servidor: {EXPORT_COMMAND}; depois rode tools/generate.sh de novo")
        return []
    exported = json.loads(SPELLS_JSON.read_text(encoding="utf-8"))
    kept = [spell for spell in exported if inherits_from_game_or_self(spell)]
    print(f"sub-spells: {len(exported) - len(kept)} descartados por herdar magia de outro mod")
    return kept


def stat_value(spell_name, field, value):
    if '"' in value or "\n" in value:
        raise SystemExit(f"{spell_name}.{field}: valor com aspas ou quebra de linha, "
                         f"o formato .txt não comporta: {value!r}")
    if value.startswith("ls::"):
        raise SystemExit(f"{spell_name}.{field}: {value!r} é o marcador de handle vazio da SE, não um "
                         "handle — corrija a leitura no Lua (Tooltip.TranslatedHandle) e exporte de novo")
    if UNVERSIONED_LOCA_HANDLE.fullmatch(value):
        return value + ";1"
    return value


def emit_sub_spell(spell):
    lines = [f'new entry "{spell["name"]}"', 'type "SpellData"', f'using "{spell["parent"]}"']
    lines += [f'data "{field}" "{stat_value(spell["name"], field, value)}"'
              for field, value in sorted(spell["fields"].items())]
    return "\n".join(lines + [""])


def enabled_categories():
    return [c for c in CATEGORIES if c["key"] in ENABLED_CATEGORIES]


def atlas_icon_key(stat):
    return "SA_Icon_" + stat


def category_items(category, catalog):
    items = catalog.get(category["key"], [])
    if category["families"]:
        items = [i for i in items if i["family"] in category["families"]]
    if category.get("inherits_item_spell"):
        items = [i for i in items if i["spell"]]
    return items


def removes_item_on_cast(category):
    return bool(category.get("inherits_item_spell"))


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
        'data "Autocast" "Yes"',
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


def emit_throw_base_entry():
    return "\n".join([
        f'new entry "{THROW_BASE_SPELL}"',
        'type "SpellData"',
        f'using "{NATIVE_THROW_ENTRY}"',
        "",
    ])


def emit_catalog_lua():
    lines = ["Catalog = {}", "", f'Catalog.BaseEntry = "{BASE_ENTRY}"',
             f'Catalog.ThrowBaseSpell = "{THROW_BASE_SPELL}"',
             f'Catalog.ThrowContainer = "{THROW_CONTAINER["spell"]}"', "",
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

    lines += ["}", "", "Catalog.ThrowableTemplates = {"]
    lines += [f'    ["{guid}"] = "{spell}",' for guid, spell in sorted(throwable_templates().items())]

    lines += ["}", ""]
    lines += [f"Catalog.{table} = {{}}" for table in RUNTIME_TABLES]
    lines += [""]
    return "\n".join(lines)


def main():
    for directory in (STATS_DIR, LUA_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    entries = [emit_base_entry()]
    localization = {lang: ['<?xml version="1.0" encoding="utf-8"?>', "<contentList>"]
                    for lang in LANGUAGES}

    for category in enabled_categories() + [THROW_CONTAINER]:
        entries.append(emit_container(category))
        for lang, (label_key, desc_key) in LANGUAGES.items():
            localization[lang].append(
                f'\t<content contentuid="{category["label_handle"]}" version="1">'
                f'{category[label_key]}</content>')
            localization[lang].append(
                f'\t<content contentuid="{category["desc_handle"]}" version="1">'
                f'{category[desc_key]}</content>')
        print(f'{category["spell"]}: container vazio, preenchido em runtime')

    entries.append(emit_throw_base_entry())

    sub_spells = exported_sub_spells()
    entries += [emit_sub_spell(spell) for spell in sub_spells]

    for stale in STATS_DIR.glob("Spell_*.txt"):
        stale.unlink()
    (STATS_DIR / STATS_FILE).write_text("\n".join(entries), encoding="utf-8")

    for lang, lines in localization.items():
        directory = LOCALIZATION_ROOT / lang
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SharedActions.xml").write_text(
            "\n".join(lines + ["</contentList>"]) + "\n", encoding="utf-8")

    (LUA_DIR / "Catalog.lua").write_text(emit_catalog_lua(), encoding="utf-8")
    print(f"atlas: {len(atlas_icon_keys())} chaves de icone "
          f"| arremesso: {len(throwable_templates())} templates elegiveis (container de arremesso) "
          f"| sub-spells: {len(sub_spells)} do export do jogo, depois das bases em {STATS_FILE}")


if __name__ == "__main__":
    main()
