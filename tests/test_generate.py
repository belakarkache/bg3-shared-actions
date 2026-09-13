#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATS_DIR = ROOT / "src/Public/SharedActions/Stats/Generated/Data"
CATALOG_LUA = ROOT / "src/Mods/SharedActions/ScriptExtender/Lua/Catalog.lua"
CATALOG_JSON = ROOT / "data/catalog.json"
LOCA_EN = ROOT / "src/Mods/SharedActions/Localization/English/SharedActions.xml"
LOCA_PT = ROOT / "src/Mods/SharedActions/Localization/BrazilianPortuguese/SharedActions.xml"
ATLAS_LSX = ROOT / "src/Public/SharedActions/GUI/SharedActions_Items.lsx"
MERGED_LSX = ROOT / "src/Public/SharedActions/Content/UI/[PAK]_UI/_merged.lsx"
GUI_DIR = ROOT / "src/Public/SharedActions/GUI"

MAX_VANILLA_CONTAINER_CHILDREN = 32
MAX_VANILLA_CONTAINER_CHARS = 1385

CATEGORIES_UNDER_TEST = [
    ("potions", "SA_TakePotion", "SA_Potion_",
     {"BASE_ALCH_Solution_Elixir", "BASE_CONS_Drink_Potion", "BASE_ALCH_Solution_Potion"},
     ("SA_Potion_OBJ_Potion_Healing", "SA_Potion_OBJ_Potion_Healing_Supreme"),
     False),
    ("scrolls", "SA_UseScroll", "SA_Scroll_",
     {"BASE_BOOK_Scroll_Magic"},
     ("SA_Scroll_OBJ_Scroll_Blindness",),
     True),
]

MAP_KEY_PATTERN = re.compile(r'MapKey" type="FixedString" value="([^"]+)"')
ATLAS_UUID_PATTERN = re.compile(r'id="UUID" type="FixedString" value="([^"]+)"')
DATA_FIELD_PATTERN = re.compile(r'^data "([^"]+)" "([^"]*)"', re.M)
USING_PATTERN = re.compile(r'^using "([^"]+)"', re.M)

lua = CATALOG_LUA.read_text(encoding="utf-8")
loca_en = LOCA_EN.read_text(encoding="utf-8")
loca_pt = LOCA_PT.read_text(encoding="utf-8")


def parse_stats():
    entries = {}
    for path in sorted(STATS_DIR.glob("Spell_*.txt")):
        spell_type = path.stem[len("Spell_"):]
        for block in path.read_text(encoding="utf-8").split("new entry ")[1:]:
            name = block.split("\n", 1)[0].strip().strip('"')
            fields = dict(DATA_FIELD_PATTERN.findall(block))
            parent = USING_PATTERN.search(block)
            fields["_using"] = parent.group(1) if parent else None
            fields["_type"] = spell_type
            entries[name] = fields
    return entries


def check_base_entry(entries):
    base = entries["SA_Base"]
    assert base.get("SpellAnimation"), "SA_Base sem SpellAnimation"
    assert base.get("CastTextEvent"), "SA_Base sem CastTextEvent"
    assert "ImmediateCast" in base["SpellFlags"], "SA_Base sem ImmediateCast"


def check_icon_atlases():
    merged = MERGED_LSX.read_text(encoding="utf-8")
    for lsx in sorted(GUI_DIR.glob("*.lsx")):
        uuid = ATLAS_UUID_PATTERN.search(lsx.read_text(encoding="utf-8")).group(1)
        assert f'value="{uuid}"' in merged, f"{lsx.name}: UUID {uuid} ausente no _merged.lsx"
    return set(MAP_KEY_PATTERN.findall(ATLAS_LSX.read_text(encoding="utf-8")))


def check_container(entries, container_name):
    container = entries[container_name]
    assert container["_using"] == "SA_Base", f"{container_name}: não herda de SA_Base"

    static_children = container["ContainerSpells"].split(";")
    assert static_children, f"{container_name}: sem lista estática"
    assert len(static_children) <= MAX_VANILLA_CONTAINER_CHILDREN, (
        f"{container_name}: lista estática com {len(static_children)} filhos "
        f"(max vanilla: {MAX_VANILLA_CONTAINER_CHILDREN})")
    assert len(container["ContainerSpells"]) <= MAX_VANILLA_CONTAINER_CHARS, (
        f"{container_name}: ContainerSpells com {len(container['ContainerSpells'])} chars "
        f"(max vanilla: {MAX_VANILLA_CONTAINER_CHARS})")
    assert "IsLinkedSpellContainer" in container["SpellFlags"], (
        f"{container_name}: precisa da flag IsLinkedSpellContainer")
    assert "ImmediateCast" not in container["SpellFlags"], (
        f"{container_name}: container não deve ter ImmediateCast")
    return static_children


def check_child(child, entry, item, container_name, families, inherits_item_spell, atlas_keys):
    assert entry["UseCosts"] == item["use_costs"], (
        f"{child}: UseCosts {entry['UseCosts']} != {item['use_costs']} do item")

    if inherits_item_spell:
        assert entry["_using"] == item["spell"], (
            f"{child}: herda {entry['_using']}, não a magia {item['spell']} do item")
        assert entry["_type"] == item["spell_type"], (
            f"{child}: em Spell_{entry['_type']}.txt, mas a base é {item['spell_type']}")
        assert "Description" not in entry, (
            f"{child}: descrição deve vir da magia herdada, não do item")
    else:
        assert entry["_using"] == "SA_Base", f"{child}: não herda de SA_Base"
        assert "SpellProperties" not in entry, (
            f"{child}: não deve ter SpellProperties (o item aplica o efeito)")
    assert entry["SpellContainerID"] == container_name, f"{child}: fora do container"
    assert entry["ContainerSpells"] == "", f"{child}: filho não pode ser container"
    assert "IsLinkedSpellContainer" not in entry.get("SpellFlags", ""), (
        f"{child}: filho não pode ter IsLinkedSpellContainer")
    assert item["family"] in families, (
        f"{child}: família {item['family']} fora da categoria")

    if entry["Icon"].startswith("SA_Icon_"):
        assert entry["Icon"] in atlas_keys, f"{child}: ícone {entry['Icon']} fora do atlas"
        assert entry["Icon"] == f'SA_Icon_{item["stat"]}', f"{child}: ícone de outro item"
    else:
        assert entry["Icon"] == item["icon"], f"{child}: ícone {entry['Icon']} != o do item"
        assert not item["rarity"], f"{child}: tem raridade mas ficou sem fundo"

    if not inherits_item_spell:
        effect = item.get("effect") or {}
        if effect:
            assert entry["Description"] == effect["Description"], (
                f"{child}: Description deve ser a do efeito, não a lore do item")
            assert entry.get("DescriptionParams") == effect.get("DescriptionParams"), (
                f"{child}: DescriptionParams não acompanha a Description")
        elif item["description"]:
            assert entry["Description"] == f'{item["description"]};1', (
                f"{child}: sem efeito, deveria cair na descrição do item")

    own_handle = entry["DisplayName"].split(";")[0]
    assert own_handle != item["displayname"], f"{child}: DisplayName usa o handle do item"
    assert f'["{child}"] = {{"{own_handle}", "{item["displayname"]}"}}' in lua, (
        f"{child}: Catalog.Labels não bate com o DisplayName")
    assert f'contentuid="{own_handle}"' in loca_en, f"{child}: handle sem fallback no .xml (English)"
    assert f'contentuid="{own_handle}"' in loca_pt, f"{child}: handle sem fallback no .xml (PT-BR)"

    assert f'["{child}"] = "' in lua, f"{child}: ausente em SpellToTemplate"
    template_key = f'{item["template_name"]}_{item["template"]}'.lower()
    assert f'["{template_key}"] = "{child}"' in lua, f"{child}: chave de template errada"
    assert f'["{child}"] = "{container_name}"' in lua, f"{child}: sem SpellContainer"


def main():
    catalog = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    entries = parse_stats()

    for translation in ("Tomar Poção", "Usar Pergaminho"):
        assert translation in loca_pt, f"faltou a tradução PT-BR de {translation}"

    check_base_entry(entries)
    atlas_keys = check_icon_atlases()

    total, with_atlas_icon = 0, 0

    for key, container_name, prefix, families, sentinels, inherits in CATEGORIES_UNDER_TEST:
        items_by_stat = {item["stat"]: item for item in catalog[key]}
        static_children = check_container(entries, container_name)
        children = [name for name in entries if name.startswith(prefix)]
        assert set(static_children) <= set(children), (
            f"{container_name}: lista estática cita spell inexistente")

        assert (f'["{container_name}"] = true' in lua) == inherits, (
            f"{container_name}: Catalog.RemovesItemOnCast não bate com inherits_item_spell "
            f"(o servidor decide por essa tabela se remove o item na mão)")

        if inherits:
            expected = {prefix + item["stat"] for item in catalog[key]
                        if item["family"] in families and item["spell"]}
            assert set(children) == expected, (
                f"{container_name}: filhos gerados não batem com os itens com magia")

        for child in children:
            entry = entries[child]
            item = items_by_stat[child[len(prefix):]]
            check_child(child, entry, item, container_name, families, inherits, atlas_keys)
            if entry["Icon"].startswith("SA_Icon_"):
                with_atlas_icon += 1

        for sentinel in sentinels:
            assert sentinel in static_children, f"{sentinel} sumiu da lista estática"
        total += len(children)

    print(f"OK — {total} sub-spells consistentes, "
          f"{with_atlas_icon} com fundo de raridade")


if __name__ == "__main__":
    sys.exit(main())
