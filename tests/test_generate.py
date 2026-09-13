#!/usr/bin/env python3
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATS_DIR = ROOT / "src/Public/SharedActions/Stats/Generated/Data"
CATALOG_LUA = ROOT / "src/Mods/SharedActions/ScriptExtender/Lua/Catalog.lua"
DISCOVERY_LUA = ROOT / "src/Mods/SharedActions/ScriptExtender/Lua/Server/Discovery.lua"
SERVER_LUA = ROOT / "src/Mods/SharedActions/ScriptExtender/Lua/Server/SharedActions.lua"
LOCA_EN = ROOT / "src/Mods/SharedActions/Localization/English/SharedActions.xml"
LOCA_PT = ROOT / "src/Mods/SharedActions/Localization/BrazilianPortuguese/SharedActions.xml"
ATLAS_LSX = ROOT / "src/Public/SharedActions/GUI/SharedActions_Items.lsx"
MERGED_LSX = ROOT / "src/Public/SharedActions/Content/UI/[PAK]_UI/_merged.lsx"
GUI_DIR = ROOT / "src/Public/SharedActions/GUI"

CATEGORIES_UNDER_TEST = [
    ("SA_TakePotion", "SA_Potion_", {"Potion"}, "BonusActionPoint:1",
     {"BASE_ALCH_Solution_Elixir", "BASE_CONS_Drink_Potion", "BASE_ALCH_Solution_Potion"},
     "h366930b4g0001g4000g9000g366930b40001",
     "h366930b4g0003g4000g9000g366930b40003",
     "none"),
    ("SA_UseScroll", "SA_Scroll_", {"Scroll"}, "ActionPoint:1",
     {"BASE_BOOK_Scroll_Magic"},
     "h366930b4g0002g4000g9000g366930b40002",
     "h366930b4g0004g4000g9000g366930b40004",
     "item"),
    ("SA_ThrowItem", "SA_Throw_", {"Potion", "Grenade", "Throwable"}, "ActionPoint:1",
     set(),
     "h366930b4g0007g4000g9000g366930b40007",
     "h366930b4g0008g4000g9000g366930b40008",
     "projectile"),
]

DIG_UNDER_TEST = {
    "spell": "SA_Dig",
    "vanillaSpell": "Target_Dig",
    "status": "HAS_SHOVEL",
    "tag": "SHOVEL_e2db698a-0705-43f4-9674-06fff1fd1e67",
    "label_handle": "h366930b4g0005g4000g9000g366930b40005",
    "desc_handle": "h366930b4g0006g4000g9000g366930b40006",
}

STATS_FILES = ["Spell_Shout.txt", "Spell_Target.txt"]

RUNTIME_TABLES = ["TemplateToSpell", "SpellToTemplate", "SpellContainer", "Labels",
                  "LegacySpells"]

PREFIX_COLLIDING_STATS = [
    "OBJ_Potion_Healing", "OBJ_Potion_Healing_Greater",
    "OBJ_Potion_Healing_Superior", "OBJ_Potion_Healing_Supreme",
    "ALCH_Solution_Elixir_Meditation", "ALCH_Solution_Elixir_Meditation_Greater",
]

MAP_KEY_PATTERN = re.compile(r'MapKey" type="FixedString" value="([^"]+)"')
ATLAS_PATH_PATTERN = re.compile(r'id="Path" type="string" value="([^"]+)"')
ATLAS_UUID_PATTERN = re.compile(r'id="UUID" type="FixedString" value="([^"]+)"')
DATA_FIELD_PATTERN = re.compile(r'^data "([^"]+)" "([^"]*)"', re.M)
USING_PATTERN = re.compile(r'^using "([^"]+)"', re.M)
ICON_KEY_PATTERN = re.compile(r'\["(SA_Icon_[^"]+)"\] = true')
SUB_SPELL_PATTERN = re.compile(r'\["(SA_(?:Potion|Scroll|Throw)_[^"]+)"\]')

lua = CATALOG_LUA.read_text(encoding="utf-8")
discovery = DISCOVERY_LUA.read_text(encoding="utf-8")
server = SERVER_LUA.read_text(encoding="utf-8")
loca_en = LOCA_EN.read_text(encoding="utf-8")
loca_pt = LOCA_PT.read_text(encoding="utf-8")


def parse_stats():
    files = sorted(STATS_DIR.glob("Spell_*.txt"))
    assert [path.name for path in files] == STATS_FILES, (
        "os sub-spells nascem em runtime: o build só emite o esqueleto "
        f"{STATS_FILES}, mas achei {[path.name for path in files]}")

    entries = {}
    for path in files:
        for block in path.read_text(encoding="utf-8").split("new entry ")[1:]:
            name = block.split("\n", 1)[0].strip().strip('"')
            fields = dict(DATA_FIELD_PATTERN.findall(block))
            parent = USING_PATTERN.search(block)
            fields["_using"] = parent.group(1) if parent else None
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
        text = lsx.read_text(encoding="utf-8")
        uuid = ATLAS_UUID_PATTERN.search(text).group(1)
        assert f'value="{uuid}"' in merged, f"{lsx.name}: UUID {uuid} ausente no _merged.lsx"
        dds = ROOT / "src" / ATLAS_PATH_PATTERN.search(text).group(1)
        assert dds.exists(), (
            f"{lsx.name} aponta para {dds.name}, que não existe: o jogo morre em LoadModule "
            "com atlas sem textura — rode ./tools/make_icon.sh <arte.png> <alvo>")

    atlas_keys = set(MAP_KEY_PATTERN.findall(ATLAS_LSX.read_text(encoding="utf-8")))
    lua_keys = set(ICON_KEY_PATTERN.findall(lua))
    assert lua_keys, "Catalog.IconKeys vazio: o runtime perde o fundo de raridade"
    assert lua_keys <= atlas_keys, (
        f"Catalog.IconKeys cita tile fora do atlas: {sorted(lua_keys - atlas_keys)[:3]}")
    return atlas_keys


def check_container(entries, container_name, use_costs, label_handle, desc_handle):
    container = entries[container_name]
    assert container["_using"] == "SA_Base", f"{container_name}: não herda de SA_Base"
    assert container["ContainerSpells"] == "", (
        f"{container_name}: ContainerSpells tem de nascer vazio — quem preenche é "
        "rebuildContainer com o que a party carrega")
    assert container["UseCosts"] == use_costs, f"{container_name}: UseCosts errado"
    assert container["DisplayName"] == f"{label_handle};1", f"{container_name}: DisplayName errado"
    assert container["Description"] == f"{desc_handle};1", f"{container_name}: Description errada"
    assert "IsLinkedSpellContainer" in container["SpellFlags"], (
        f"{container_name}: precisa da flag IsLinkedSpellContainer")
    assert "ImmediateCast" not in container["SpellFlags"], (
        f"{container_name}: container não deve ter ImmediateCast")


def check_throw_reads_projectile_spell():
    assert "Catalog.ProjectileSpells[" in discovery, (
        "o arremesso herda o spell que o item dispara ao quebrar; esse dado não é legível em "
        "runtime (ScriptConfigGlobalParameters vem vazio, medido in-game) e é assado por "
        "collect.py em Catalog.ProjectileSpells")
    baked = re.findall(r'\["([0-9a-f-]{36})"\] = "([^"]+)"', lua)
    assert len(baked) > 50, (
        f"Catalog.ProjectileSpells tem {len(baked)} templates: sem esse mapa nenhum item entra "
        "na lista de arremesso — rode python3 tools/collect.py")


def check_spell_names_never_collide():
    assert 'statName .. "_" .. #statName' in discovery, (
        "o nome do sub-spell tem de terminar no comprimento do stat: o jogo esconde um "
        "sub-spell cujo nome é prefixo de um irmão do mesmo container")

    named = [f"{stat}_{len(stat)}" for stat in PREFIX_COLLIDING_STATS]
    for name in named:
        for other in named:
            assert name == other or not other.startswith(name), (
                f"{name} continua sendo prefixo de {other}: a Poção de Cura simples some "
                "da lista quando uma irmã maior está junto")


def check_dig(entries):
    dig = entries[DIG_UNDER_TEST["spell"]]
    assert dig["_using"] == DIG_UNDER_TEST["vanillaSpell"], (
        "SA_Dig tem de herdar Target_Dig: mira, cursor, custo e requisitos vêm de lá")
    assert dig["DisplayName"] == f'{DIG_UNDER_TEST["label_handle"]};1', "SA_Dig: DisplayName errado"
    assert dig["Description"] == f'{DIG_UNDER_TEST["desc_handle"]};1', "SA_Dig: Description errada"

    for field, value in DIG_UNDER_TEST.items():
        if field.endswith("_handle"):
            continue
        assert f'{field} = "{value}"' in lua, f"Catalog.Dig.{field} não bate com {value}"
        assert f'"{value}"' not in server, (
            f"Server/SharedActions.lua traz {value} hardcoded: quem define é Catalog.Dig")

    assert "Dig.vanillaSpell" in server, (
        "o goal vanilla só escuta o nome Target_Dig: o cast de SA_Dig tem de ser repassado "
        "com Osi.UseSpell para a magia de verdade")


def check_runtime_tables():
    for table in RUNTIME_TABLES:
        assert f"Catalog.{table} = {{}}" in lua, (
            f"Catalog.{table} tem de ser declarada vazia: Server/Discovery.lua a preenche "
            "no lugar, e Server/SharedActions.lua guarda a referência no load")
        assert f"Catalog.{table}[" in discovery, (
            f"Catalog.{table} é declarada mas ninguém a preenche em Discovery.lua")

    leaked = SUB_SPELL_PATTERN.findall(lua)
    assert not leaked, (
        f"Catalog.lua traz sub-spell de build time: {leaked[:3]} — quem cria é Discovery.lua")


def check_category_rules(container_name, prefix, use_types, families, inherits):
    block = lua.split(f'container = "{container_name}"', 1)
    assert len(block) == 2, f"{container_name}: ausente em Catalog.Categories"
    block = block[1].split("    },\n    {", 1)[0]

    assert f'prefix = "{prefix}"' in block, f"{container_name}: prefixo errado"
    for use_type in use_types:
        assert f'["{use_type}"] = true' in block, f"{container_name}: ItemUseType {use_type} ausente"
    assert f'inheritsItemSpell = {str(inherits == "item").lower()}' in block, (
        f"{container_name}: inheritsItemSpell não bate")
    assert f'inheritsProjectileSpell = {str(inherits == "projectile").lower()}' in block, (
        f"{container_name}: inheritsProjectileSpell não bate")
    for family in families:
        assert f'["{family}"] = true' in block, f"{container_name}: família {family} ausente"
    assert bool(families) == ("families = {\n            [" in block), (
        f"{container_name}: categoria sem famílias só é aceitável quando a herança do spell do "
        "item já filtra o que é usável — é o caso do arremesso, que exige ProjectileSpell")

    assert (f'["{container_name}"] = true' in lua) == (inherits != "none"), (
        f"{container_name}: Catalog.RemovesItemOnCast não bate com a herança "
        "(o servidor decide por essa tabela se remove o item na mão)")
    assert f'"{container_name}",' in lua, f"{container_name}: fora de Catalog.Containers"


def main():
    entries = parse_stats()
    check_base_entry(entries)
    check_icon_atlases()
    check_runtime_tables()
    check_dig(entries)
    check_spell_names_never_collide()
    check_throw_reads_projectile_spell()

    for translation in ("Tomar Poção", "Usar Pergaminho", "Cavar", "Arremessar"):
        assert translation in loca_pt, f"faltou a tradução PT-BR de {translation}"

    for (container_name, prefix, use_types, use_costs,
         families, label_handle, desc_handle, inherits) in CATEGORIES_UNDER_TEST:
        check_container(entries, container_name, use_costs, label_handle, desc_handle)
        check_category_rules(container_name, prefix, use_types, families, inherits)
        for handle in (label_handle, desc_handle):
            assert f'contentuid="{handle}"' in loca_en, f"{handle}: sem texto em inglês"
            assert f'contentuid="{handle}"' in loca_pt, f"{handle}: sem texto em PT-BR"

    for handle in (DIG_UNDER_TEST["label_handle"], DIG_UNDER_TEST["desc_handle"]):
        assert f'contentuid="{handle}"' in loca_en, f"{handle}: sem texto em inglês"
        assert f'contentuid="{handle}"' in loca_pt, f"{handle}: sem texto em PT-BR"

    handles = re.findall(r'contentuid="([^"]+)"', loca_en)
    assert len(handles) == 2 * len(CATEGORIES_UNDER_TEST) + 2, (
        f"loca tem {len(handles)} handles: o rótulo de item vem do jogo em runtime, "
        "só os das categorias ficam no .xml")

    print(f"OK — {len(CATEGORIES_UNDER_TEST)} containers vazios, "
          f"{len(handles)} handles de categoria, sub-spells em runtime")


if __name__ == "__main__":
    sys.exit(main())
