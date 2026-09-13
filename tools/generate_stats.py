#!/usr/bin/env python3
import functools
import hashlib
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

LANGUAGES = {
    "English": ("label", "desc"),
    "BrazilianPortuguese": ("label_ptbr", "desc_ptbr"),
}

CATEGORIES = [
    {
        "key": "potions",
        "spell": "SA_TakePotion",
        "prefix": "SA_Potion_",
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
]

ENABLED_CATEGORIES = {"potions", "scrolls"}

MAX_STATIC_CONTAINER_SPELLS = 30

COMBAT_PRIORITY = [
    "OBJ_Potion_Healing", "OBJ_Potion_Healing_Greater",
    "OBJ_Potion_Healing_Superior", "OBJ_Potion_Healing_Supreme",
    "OBJ_Potion_Of_Speed", "OBJ_Potion_Of_Vitality", "OBJ_Potion_Of_Heroism",
    "OBJ_Potion_Of_Invisibility", "OBJ_Potion_Of_Invulnerability",
    "OBJ_Potion_Elixir_Of_Health", "OBJ_Antitoxin",
    "OBJ_Potion_Of_Hill_Giant_Strength", "OBJ_Potion_Of_Cloud_Giant_Strength",
    "OBJ_Potion_Of_Fire_Resistance", "OBJ_Potion_Of_Cold_Resistance",
    "OBJ_Potion_Of_Acid_Resistance", "OBJ_Potion_Of_Poison_Resistance",
    "OBJ_Potion_Of_Lightning_Resistance", "OBJ_Potion_Of_Necrotic_Resistance",
    "OBJ_Potion_Of_Psychic_Resistance", "OBJ_Potion_Of_Radiant_Resistance",
    "OBJ_Potion_Of_Force_Resistance", "OBJ_Potion_Of_Thunder_Resistance",
]

BASE_ENTRY = "SA_Base"
BASE_SPELL_ANIMATION = ("03496c4a-49e0-4132-b585-3e5ecd1ad8e5,,;,,;"
                        "bcc3b0d9-f04f-4448-aab0-e0ad641167cc,,;"
                        "bf924cc6-8b39-4c3b-b1c0-eda264cf6150,,;"
                        "a9682ef9-5d9e-4ac0-8144-2c7fe6eb868c,,;,,;"
                        "32fb4d91-7fde-4b05-9144-ea87b9a4284a,,;,,;,,")

MAP_KEY_PATTERN = re.compile(r'MapKey" type="FixedString" value="([^"]+)"')
STAT_PREFIX_PATTERN = re.compile(r"^(OBJ|CONS|ALCH|LOOT|BASE)_")
WHITESPACE_PATTERN = re.compile(r"\s+")


@functools.lru_cache(maxsize=1)
def atlas_icon_keys():
    if not CUSTOM_ICON_ENABLED or not ITEM_ATLAS_LSX.exists():
        return frozenset()
    return frozenset(MAP_KEY_PATTERN.findall(ITEM_ATLAS_LSX.read_text(encoding="utf-8")))


def atlas_icon_key(stat):
    return "SA_Icon_" + stat


def icon_for(item):
    key = atlas_icon_key(item["stat"])
    return key if key in atlas_icon_keys() else item["icon"]


def spell_name(category, item):
    return category["prefix"] + item["stat"]


def own_handle(spell):
    digest = hashlib.md5(spell.encode()).hexdigest()
    return (f"h{digest[:8]}g{digest[8:12]}g{digest[12:16]}"
            f"g{digest[16:20]}g{digest[20:32]}")


def fallback_text(item):
    name = STAT_PREFIX_PATTERN.sub("", item["stat"])
    name = name.replace("Solution_", "").replace("_", " ")
    return WHITESPACE_PATTERN.sub(" ", name).strip()


def root_template_id(item):
    return f'{item["template_name"]}_{item["template"]}'


def select_static_children(items):
    rank = {stat: index for index, stat in enumerate(COMBAT_PRIORITY)}
    ordered = sorted(items, key=lambda i: (rank.get(i["stat"], len(COMBAT_PRIORITY)), i["stat"]))
    return ordered[:MAX_STATIC_CONTAINER_SPELLS]


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


def emit_container(category, children):
    return "\n".join([
        f'new entry "{category["spell"]}"',
        'type "SpellData"',
        f'using "{BASE_ENTRY}"',
        f'data "ContainerSpells" "{";".join(children)}"',
        f'data "UseCosts" "{category["use_costs"]}"',
        f'data "Icon" "{category["icon"]}"',
        f'data "DisplayName" "{category["label_handle"]};1"',
        f'data "Description" "{category["desc_handle"]};1"',
        'data "SpellFlags" "IsLinkedSpellContainer;UnavailableInDialogs"',
        "",
    ])


def spell_type_of(category, item):
    if category.get("inherits_item_spell") and item["spell_type"]:
        return item["spell_type"]
    return "Shout"


def parent_entry(category, item):
    if category.get("inherits_item_spell"):
        return item["spell"]
    return BASE_ENTRY


def category_items(category, catalog):
    items = [i for i in catalog[category["key"]] if i["family"] in category["families"]]
    if category.get("inherits_item_spell"):
        items = [i for i in items if i["spell"]]
    return items


def emit_child(category, item):
    parent = parent_entry(category, item)
    lines = [
        f'new entry "{spell_name(category, item)}"',
        'type "SpellData"',
        f'using "{parent}"',
        f'data "SpellContainerID" "{category["spell"]}"',
        'data "ContainerSpells" ""',
        f'data "Icon" "{icon_for(item)}"',
        f'data "DisplayName" "{own_handle(spell_name(category, item))};1"',
    ]
    if parent == BASE_ENTRY:
        effect = item.get("effect") or {}
        if effect:
            lines += [f'data "{field}" "{value}"' for field, value in effect.items()]
        elif item["description"]:
            lines.append(f'data "Description" "{item["description"]};1"')

    lines += [f'data "UseCosts" "{item["use_costs"]}"', ""]
    return "\n".join(lines)


def emit_catalog_lua(template_spell_pairs, containers, labels, spell_containers,
                     containers_removing_item):
    lines = ["Catalog = {}", "", "Catalog.Containers = {"]
    lines += [f'    "{container}",' for container in containers]

    lines += ["}", "", "Catalog.RemovesItemOnCast = {"]
    lines += [f'    ["{container}"] = true,' for container in containers_removing_item]

    lines += ["}", "", "Catalog.TemplateToSpell = {"]
    lines += [f'    ["{template.lower()}"] = "{spell}",' for template, spell in template_spell_pairs]

    lines += ["}", "", "Catalog.SpellToTemplate = {"]
    lines += [f'    ["{spell}"] = "{template}",' for template, spell in template_spell_pairs]

    lines += ["}", "", "Catalog.SpellContainer = {"]
    lines += [f'    ["{spell}"] = "{container}",' for spell, container in spell_containers]

    lines += ["}", "", "Catalog.Labels = {"]
    lines += [f'    ["{spell}"] = {{"{own}", "{vanilla}"}},' for spell, own, vanilla in labels]

    lines += ["}", "", f"Catalog.Count = {len(template_spell_pairs)}", ""]
    return "\n".join(lines)


def main():
    catalog = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
    for directory in (STATS_DIR, LUA_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    stats_by_type = {"Shout": [emit_base_entry()]}
    localization = {lang: ['<?xml version="1.0" encoding="utf-8"?>', "<contentList>"]
                    for lang in LANGUAGES}
    template_spell_pairs, containers = [], []
    labels, spell_containers, containers_removing_item = [], [], []

    for category in CATEGORIES:
        if category["key"] not in ENABLED_CATEGORIES:
            continue

        items = category_items(category, catalog)
        children = [spell_name(category, i) for i in select_static_children(items)]
        stats_by_type["Shout"].append(emit_container(category, children))
        for item in items:
            stats_by_type.setdefault(
                spell_type_of(category, item), []).append(emit_child(category, item))

        for lang, (label_key, desc_key) in LANGUAGES.items():
            localization[lang].append(
                f'\t<content contentuid="{category["label_handle"]}" version="1">{category[label_key]}</content>')
            localization[lang].append(
                f'\t<content contentuid="{category["desc_handle"]}" version="1">{category[desc_key]}</content>')

        for item in items:
            spell = spell_name(category, item)
            handle = own_handle(spell)
            labels.append((spell, handle, item["displayname"]))
            spell_containers.append((spell, category["spell"]))
            template_spell_pairs.append((root_template_id(item), spell))
            for lang in LANGUAGES:
                localization[lang].append(
                    f'\t<content contentuid="{handle}" version="1">{fallback_text(item)}</content>')

        containers.append(category["spell"])
        if category.get("inherits_item_spell"):
            containers_removing_item.append(category["spell"])
        print(f'{category["spell"]}: {len(items)} sub-spells ({len(children)} na lista estática)')

    for stale in STATS_DIR.glob("Spell_*.txt"):
        stale.unlink()
    for spell_type, lines in stats_by_type.items():
        (STATS_DIR / f"Spell_{spell_type}.txt").write_text("\n".join(lines), encoding="utf-8")
    print("arquivos de stats:", ", ".join(sorted(stats_by_type)))

    for lang, lines in localization.items():
        directory = LOCALIZATION_ROOT / lang
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SharedActions.xml").write_text(
            "\n".join(lines + ["</contentList>"]) + "\n", encoding="utf-8")

    (LUA_DIR / "Catalog.lua").write_text(
        emit_catalog_lua(template_spell_pairs, containers, labels, spell_containers,
                         containers_removing_item),
        encoding="utf-8")
    print(f"total: {len(template_spell_pairs)} sub-spells")


if __name__ == "__main__":
    main()
