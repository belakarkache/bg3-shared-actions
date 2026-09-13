#!/usr/bin/env python3
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

GAMEDATA = Path(os.environ.get("BG3_DATA", "gamedata"))

STATS_FILES = sorted(GAMEDATA.glob("Public/*/Stats/Generated/Data/Object.txt"))
SPELL_FILES = sorted(GAMEDATA.glob("Public/*/Stats/Generated/Data/Spell_*.txt"))
STATUS_FILES = sorted(GAMEDATA.glob("Public/*/Stats/Generated/Data/Status_*.txt"))
TEMPLATE_FILES = sorted(GAMEDATA.glob("Public/*/RootTemplates/_merged.lsx"))

USABLE_ITEM_TYPES = {"Potion": "potions", "Scroll": "scrolls"}
MAX_INHERITANCE_DEPTH = 12

EFFECT_FIELDS = ["Description", "DescriptionParams", "ExtraDescription",
                 "ExtraDescriptionParams", "TooltipDamageList", "TooltipAttackSave",
                 "TooltipStatusApply", "TooltipOnSave"]

DATA_FIELD_PATTERN = re.compile(r'^data "([^"]+)" "([^"]*)"', re.M)
USING_PATTERN = re.compile(r'^using "([^"]+)"', re.M)


def parse_stat_entries(paths):
    entries = {}
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for block in text.split("new entry ")[1:]:
            name = block.split("\n", 1)[0].strip().strip('"')
            fields = dict(DATA_FIELD_PATTERN.findall(block))
            parent = USING_PATTERN.search(block)
            if name in entries:
                entries[name]["fields"].update(fields)
                if parent:
                    entries[name]["using"] = parent.group(1)
            else:
                entries[name] = {"fields": fields, "using": parent.group(1) if parent else None}
    return entries


def resolve_stat_field(entries, name, field, depth=0):
    if name not in entries or depth > MAX_INHERITANCE_DEPTH:
        return None
    entry = entries[name]
    value = entry["fields"].get(field)
    if value not in (None, ""):
        return value
    return resolve_stat_field(entries, entry["using"], field, depth + 1)


def parse_use_actions(node):
    actions = []
    for group in node.findall("children/node"):
        if group.get("id") != "OnUsePeaceActions":
            continue
        for action in group.findall("children/node"):
            attributes = {a.get("id"): a.get("value")
                          for a in action.findall("children/node/attribute")}
            spell = attributes.get("SpellId") or attributes.get("SkillID")
            if spell or attributes.get("StatsId"):
                actions.append((spell, attributes.get("StatsId")))
    return actions


def item_spell(spells, use_actions):
    found = [spell for spell, _ in use_actions if spell]
    name = found[-1] if found else None
    if not name or name not in spells or resolve_stat_field(spells, name, "ContainerSpells"):
        return ""
    return name


def resolve_effect(spells, statuses, use_actions):
    for spell, status in use_actions:
        entries, name = (spells, spell) if spell else (statuses, status)
        if not resolve_stat_field(entries, name, "Description"):
            continue
        return {field: value for field in EFFECT_FIELDS
                if (value := resolve_stat_field(entries, name, field))}
    return {}


def parse_root_templates(paths):
    templates = {}
    for path in paths:
        if not path.exists():
            continue
        root = ET.parse(path).getroot()
        for node in root.iter("node"):
            if node.get("id") != "GameObjects":
                continue
            attributes = {child.get("id"): child.get("value") or child.get("handle")
                          for child in node.findall("attribute")}
            guid = attributes.get("MapKey")
            if not guid:
                continue
            record = {
                "name": attributes.get("Name"),
                "icon": attributes.get("Icon"),
                "displayname": attributes.get("DisplayName"),
                "description": attributes.get("Description"),
                "stats": attributes.get("Stats"),
                "parent": attributes.get("ParentTemplateId"),
                "use_actions": parse_use_actions(node),
            }
            if guid in templates:
                for key, value in record.items():
                    if value and not templates[guid].get(key):
                        templates[guid][key] = value
            else:
                templates[guid] = record
    return templates


def resolve_template_field(templates, guid, field, depth=0):
    if guid not in templates or depth > MAX_INHERITANCE_DEPTH:
        return None
    value = templates[guid].get(field)
    if value:
        return value
    return resolve_template_field(templates, templates[guid].get("parent"), field, depth + 1)


def base_family(templates, guid):
    depth = 0
    while guid in templates and depth < MAX_INHERITANCE_DEPTH:
        name = templates[guid].get("name") or ""
        if name.startswith("BASE_"):
            return name
        guid = templates[guid].get("parent")
        depth += 1
    return None


def main():
    if not STATS_FILES:
        raise SystemExit(f"sem dados do jogo em {GAMEDATA} — aponte BG3_DATA para os .pak extraídos")

    entries = parse_stat_entries(STATS_FILES)
    spells = parse_stat_entries(SPELL_FILES)
    statuses = parse_stat_entries(STATUS_FILES)
    templates = parse_root_templates(TEMPLATE_FILES)
    print(f"stats: {len(entries)} entradas | templates: {len(templates)}", file=sys.stderr)

    catalog = {category: [] for category in USABLE_ITEM_TYPES.values()}
    skipped = {"sem_template": 0, "sem_custo": 0}

    for name in entries:
        item_use_type = resolve_stat_field(entries, name, "ItemUseType")
        category = USABLE_ITEM_TYPES.get(item_use_type)
        if not category or name.startswith("_"):
            continue

        guid = resolve_stat_field(entries, name, "RootTemplate")
        if not guid or guid not in templates:
            skipped["sem_template"] += 1
            continue

        use_costs = resolve_stat_field(entries, name, "UseCosts")
        if not use_costs:
            skipped["sem_custo"] += 1
            continue

        use_actions = resolve_template_field(templates, guid, "use_actions") or []
        spell = item_spell(spells, use_actions)

        catalog[category].append({
            "stat": name,
            "template": guid,
            "template_name": templates[guid]["name"],
            "family": base_family(templates, guid),
            "icon": resolve_template_field(templates, guid, "icon"),
            "displayname": resolve_template_field(templates, guid, "displayname"),
            "description": resolve_template_field(templates, guid, "description") or "",
            "effect": resolve_effect(spells, statuses, use_actions),
            "spell": spell,
            "spell_type": (resolve_stat_field(spells, spell, "SpellType") or "") if spell else "",
            "rarity": resolve_stat_field(entries, name, "Rarity") or "",
            "use_costs": use_costs,
        })

    for category in catalog:
        catalog[category].sort(key=lambda item: item["stat"])

    output = Path(__file__).resolve().parent.parent / "data" / "catalog.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(catalog, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"poções: {len(catalog['potions'])} | pergaminhos: {len(catalog['scrolls'])}",
          file=sys.stderr)
    print(f"descartados: {skipped}", file=sys.stderr)
    print(f"-> {output}", file=sys.stderr)


if __name__ == "__main__":
    main()
