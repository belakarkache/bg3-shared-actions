#!/usr/bin/env python3
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATS_DIR = ROOT / "src/Public/SharedActions/Stats/Generated/Data"
CATALOG_LUA = ROOT / "src/Mods/SharedActions/ScriptExtender/Lua/Catalog.lua"
DISCOVERY_LUA = ROOT / "src/Mods/SharedActions/ScriptExtender/Lua/Server/Discovery.lua"
SERVER_LUA = ROOT / "src/Mods/SharedActions/ScriptExtender/Lua/Server/SharedActions.lua"
THROW_LUA = ROOT / "src/Mods/SharedActions/ScriptExtender/Lua/Server/Throw.lua"
CLIENT_THROW_LUA = ROOT / "src/Mods/SharedActions/ScriptExtender/Lua/Client/Throw.lua"
SERVER_LUA_DIR = ROOT / "src/Mods/SharedActions/ScriptExtender/Lua/Server"
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
    ("SA_Quiver", "SA_Arrow_", {"Arrow"}, "ActionPoint:1",
     {"BASE_LOOT_Arrow"},
     "h366930b4g0009g4000g9000g366930b40009",
     "h366930b4g000ag4000g9000g366930b4000a",
     "item"),
]

THROW_BASE_SPELL = "SA_ThrowBase"
THROW_CONTAINER = "SA_ThrowItems"
THROW_USE_COSTS = "ActionPoint:1"
THROW_LABEL_HANDLE = "h366930b4g0007g4000g9000g366930b40007"
THROW_DESC_HANDLE = "h366930b4g0008g4000g9000g366930b40008"
RETIRED_THROW_SPELLS = ["SA_ThrowItem", "SA_OpenThrowPanel", "SA_ThrowProbe"]

STATS_FILES = ["Spell_Shout.txt"]
SUB_SPELL_PREFIXES = ("SA_Potion_", "SA_Scroll_", "SA_Arrow_", "SA_Throwable_")
MIN_SUB_SPELLS = 100
EXPORT_HINT = ("no jogo, console do servidor: !sa_export; depois ./tools/generate.sh e o build")

RUNTIME_TABLES = ["TemplateToSpell", "SpellToTemplate", "SpellContainer", "Labels",
                  "LegacySpells", "ScrollVariants", "VariantGroupOf"]

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
LOCA_HANDLE_FIELD = re.compile(r"h[0-9a-g]{36};\d+")
SUB_SPELL_PATTERN = re.compile(r'\["(SA_(?:Potion|Scroll|Arrow)_[^"]+)"\]')
THROWABLE_TEMPLATE_PATTERN = re.compile(r'\["([0-9a-f-]{36})"\] = "[A-Za-z0-9_]*"')

lua = CATALOG_LUA.read_text(encoding="utf-8")
discovery = DISCOVERY_LUA.read_text(encoding="utf-8")
throw = THROW_LUA.read_text(encoding="utf-8")
client_throw = CLIENT_THROW_LUA.read_text(encoding="utf-8")
loca_en = LOCA_EN.read_text(encoding="utf-8")
loca_pt = LOCA_PT.read_text(encoding="utf-8")


def parse_stats():
    files = sorted(STATS_DIR.glob("Spell_*.txt"))
    assert [path.name for path in files] == STATS_FILES, (
        f"o build emite exatamente {STATS_FILES}: as bases e, depois delas, os sub-spells exportados "
        f"do jogo. Achei {[path.name for path in files]}")

    entries = {}
    for path in files:
        for block in path.read_text(encoding="utf-8").split("new entry ")[1:]:
            name = block.split("\n", 1)[0].strip().strip('"')
            fields = dict(DATA_FIELD_PATTERN.findall(block))
            parent = USING_PATTERN.search(block)
            fields["_using"] = parent.group(1) if parent else None
            fields["_position"] = len(entries)
            entries[name] = fields
    return entries


def check_parents_come_first(entries):
    for name, fields in entries.items():
        parent = entries.get(fields["_using"])
        assert parent is None or parent["_position"] < fields["_position"], (
            f"{name} vem antes do pai {fields['_using']}: o jogo não resolve using para entrada que "
            "ainda não carregou, e o filho perde flags, alvo e animação (poção e arremesso deram "
            "CastSpellFailed na hora, 2026-09-22)")


def check_no_runtime_spell_creation():
    for lua_file in sorted(SERVER_LUA_DIR.glob("*.lua")):
        assert "Ext.Stats.Create" not in lua_file.read_text(encoding="utf-8"), (
            f"{lua_file.name} chama Ext.Stats.Create: spell criado em runtime fica fora do cache de "
            "protótipos da IA de combate, e o jogo crasha no turno de quem o tem (dump de "
            "2026-09-22, NOTES.md). Sub-spell tem de vir do pak, via !sa_export + generate.sh")


def check_sub_spells(entries):
    sub_spells = {name: fields for name, fields in entries.items()
                  if name.startswith(SUB_SPELL_PREFIXES)}
    assert len(sub_spells) >= MIN_SUB_SPELLS, (
        f"só {len(sub_spells)} sub-spells no pak: sem eles os menus ficam vazios — {EXPORT_HINT}")
    for name, fields in sub_spells.items():
        assert fields["_using"], f"{name}: sem using, não herda a mira/efeito do pai"
        assert fields.get("SpellType"), (
            f"{name}: sem SpellType explícito — o export copia do pai para não depender de a "
            "herança resolver um pai de outro mod")
        assert LOCA_HANDLE_FIELD.fullmatch(fields.get("DisplayName", "")), (
            f"{name}: DisplayName {fields.get('DisplayName')!r} não é handle;versão — o rótulo "
            "do cliente escreve texto nesse handle")
    return len(sub_spells)


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


def check_throw(entries):
    assert "Catalog.ThrowableTemplates" in throw, (
        "o arremesso decide quem entra na lista pelo conjunto assado em Catalog.ThrowableTemplates "
        "(o que torna um item arremessável mora no root template, ilegível em runtime) — "
        "Server/Throw.lua tem de ler dessa tabela")
    baked = THROWABLE_TEMPLATE_PATTERN.findall(lua.split("Catalog.ThrowableTemplates = {", 1)[1])
    assert len(baked) > 50, (
        f"Catalog.ThrowableTemplates tem {len(baked)} templates: sem esse conjunto nenhum item "
        "entra no arremesso — rode python3 tools/collect.py da raiz do workspace")

    for spell in RETIRED_THROW_SPELLS:
        assert f'"{spell}"' in discovery, (
            f"{spell} é um desenho antigo do arremesso e precisa continuar em RETIRED_SPELLS: "
            "quem já tinha essa spell gravada no save fica com um identificador órfão sem a limpeza")

    check_container(entries, THROW_CONTAINER, THROW_USE_COSTS, THROW_LABEL_HANDLE, THROW_DESC_HANDLE)
    assert f'"{THROW_CONTAINER}",' not in lua, (
        f"{THROW_CONTAINER} não entra em Catalog.Containers: rebuildAllContainers só conhece "
        "poção e pergaminho e apagaria o ContainerSpells que Server/Throw.lua escreve")

    base = entries[THROW_BASE_SPELL]
    assert base["_using"] == "Throw_Throw", (
        f"{THROW_BASE_SPELL}: tem de herdar de Throw_Throw — é a mira nativa de arremesso que o "
        "servidor preenche com o item, e o custo de Ação vem daí")
    assert "SpellFlags" not in base, (
        f"{THROW_BASE_SPELL}: os SpellFlags vêm do Throw_Throw, com InventorySelection — é o que faz o "
        "servidor aceitar item de inventário como alvo do arremesso. Quem tira a flag é só o cliente, "
        "em Client/Throw.lua (NOTES.md, P16f e sexta rodada)")
    assert 'STRIPPED_FLAG = "InventorySelection"' in client_throw and "stat:Sync()" in client_throw, (
        "Client/Throw.lua tem de remover InventorySelection dos sub-spells e dar Sync() local: "
        "sem isso o clique abre o seletor do próprio inventário em vez da mira vazia")
    assert "Catalog.ThrowBaseSpell" in throw and "Catalog.ThrowContainer" in throw, (
        "Server/Throw.lua cria os sub-spells herdando de Catalog.ThrowBaseSpell dentro de "
        "Catalog.ThrowContainer")
    for handle in (THROW_LABEL_HANDLE, THROW_DESC_HANDLE):
        assert f'contentuid="{handle}"' in loca_en, f"{handle}: sem texto em inglês"
        assert f'contentuid="{handle}"' in loca_pt, f"{handle}: sem texto em PT-BR"


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


def check_runtime_tables():
    for table in RUNTIME_TABLES:
        assert f"Catalog.{table} = {{}}" in lua, (
            f"Catalog.{table} tem de ser declarada vazia: Server/Discovery.lua a preenche "
            "no lugar, e Server/SharedActions.lua guarda a referência no load")
        assert f"Catalog.{table}[" in discovery, (
            f"Catalog.{table} é declarada mas ninguém a preenche em Server/Discovery.lua")

    leaked = SUB_SPELL_PATTERN.findall(lua)
    assert not leaked, (
        f"Catalog.lua traz sub-spell: {leaked[:3]} — os sub-spells vão para "
        f"{STATS_FILES[0]}, e o catálogo é preenchido pela descoberta em runtime")


def check_category_rules(container_name, prefix, use_types, families, inherits):
    block = lua.split(f'container = "{container_name}"', 1)
    assert len(block) == 2, f"{container_name}: ausente em Catalog.Categories"
    block = block[1].split("    },\n    {", 1)[0]

    assert f'prefix = "{prefix}"' in block, f"{container_name}: prefixo errado"
    for use_type in use_types:
        assert f'["{use_type}"] = true' in block, f"{container_name}: ItemUseType {use_type} ausente"
    assert f'inheritsItemSpell = {str(inherits == "item").lower()}' in block, (
        f"{container_name}: inheritsItemSpell não bate")
    for family in families:
        assert f'["{family}"] = true' in block, f"{container_name}: família {family} ausente"
    assert bool(families) == ("families = {\n            [" in block), (
        f"{container_name}: categoria sem famílias só é aceitável quando a herança do spell do "
        "item já filtra o que é usável")

    assert (f'["{container_name}"] = true' in lua) == (inherits != "none"), (
        f"{container_name}: Catalog.RemovesItemOnCast não bate com a herança "
        "(o servidor decide por essa tabela se remove o item na mão)")
    assert f'"{container_name}",' in lua, f"{container_name}: fora de Catalog.Containers"


def main():
    entries = parse_stats()
    check_no_runtime_spell_creation()
    check_parents_come_first(entries)
    sub_spell_count = check_sub_spells(entries)
    check_base_entry(entries)
    check_icon_atlases()
    check_runtime_tables()
    check_spell_names_never_collide()
    check_throw(entries)

    assert '"SA_Dig"' in discovery, (
        "SA_Dig foi descontinuado: precisa continuar em RETIRED_SPELLS para limpar o save "
        "de quem já carregou a pá")
    assert "Dig" not in lua and "SHOVEL" not in lua, (
        "Cavar foi descontinuado: Catalog.lua não deve mais gerar nada ligado a ele")
    assert "HAS_SHOVEL" not in SERVER_LUA.read_text(encoding="utf-8"), (
        "HAS_SHOVEL é status vanilla (StatusInInventory da pá): removê-lo desabilita Target_Dig")

    for translation in ("Tomar Poção", "Usar Pergaminho", "Aljava", "Arremessar"):
        assert translation in loca_pt, f"faltou a tradução PT-BR de {translation}"

    for (container_name, prefix, use_types, use_costs,
         families, label_handle, desc_handle, inherits) in CATEGORIES_UNDER_TEST:
        check_container(entries, container_name, use_costs, label_handle, desc_handle)
        check_category_rules(container_name, prefix, use_types, families, inherits)
        for handle in (label_handle, desc_handle):
            assert f'contentuid="{handle}"' in loca_en, f"{handle}: sem texto em inglês"
            assert f'contentuid="{handle}"' in loca_pt, f"{handle}: sem texto em PT-BR"

    handles = re.findall(r'contentuid="([^"]+)"', loca_en)
    assert len(handles) == 2 * len(CATEGORIES_UNDER_TEST) + 2, (
        f"loca tem {len(handles)} handles: o rótulo de item vem do jogo em runtime, "
        "só os das categorias e o do container de arremesso ficam no .xml")

    print(f"OK — {len(CATEGORIES_UNDER_TEST) + 1} containers vazios, {THROW_BASE_SPELL} herda Throw_Throw, "
          f"{len(handles)} handles fixos, {sub_spell_count} sub-spells no pak")


if __name__ == "__main__":
    sys.exit(main())
