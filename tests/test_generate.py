#!/usr/bin/env python3
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATS_DIR = ROOT / "src/Public/SharedActions/Stats/Generated/Data"
CATALOG_LUA = ROOT / "src/Mods/SharedActions/ScriptExtender/Lua/Catalog.lua"
DISCOVERY_LUA = ROOT / "src/Mods/SharedActions/ScriptExtender/Lua/Server/Discovery.lua"
THROW_PANEL_LUA = ROOT / "src/Mods/SharedActions/ScriptExtender/Lua/Server/ThrowPanel.lua"
CLIENT_THROW_PANEL_LUA = ROOT / "src/Mods/SharedActions/ScriptExtender/Lua/Client/ThrowPanel.lua"
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
]

THROW_PANEL_SPELL = "SA_OpenThrowPanel"
THROW_PANEL_LABEL_HANDLE = "h366930b4g0007g4000g9000g366930b40007"
THROW_PANEL_DESC_HANDLE = "h366930b4g0008g4000g9000g366930b40008"

STATS_FILES = ["Spell_Shout.txt"]

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
SUB_SPELL_PATTERN = re.compile(r'\["(SA_(?:Potion|Scroll)_[^"]+)"\]')
THROWABLE_TEMPLATE_PATTERN = re.compile(r'\["([0-9a-f-]{36})"\] = true')

lua = CATALOG_LUA.read_text(encoding="utf-8")
discovery = DISCOVERY_LUA.read_text(encoding="utf-8")
throw_panel = THROW_PANEL_LUA.read_text(encoding="utf-8")
client_throw_panel = CLIENT_THROW_PANEL_LUA.read_text(encoding="utf-8")
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


def check_throw_panel():
    assert "Catalog.ThrowableTemplates" in throw_panel, (
        "o painel de arremesso decide quem entra na lista pelo conjunto assado em "
        "Catalog.ThrowableTemplates (o ProjectileSpell do item mora no nó Scripts do root "
        "template, ilegível em runtime) — Server/ThrowPanel.lua tem de ler dessa tabela")
    baked = THROWABLE_TEMPLATE_PATTERN.findall(lua.split("Catalog.ThrowableTemplates = {", 1)[1])
    assert len(baked) > 50, (
        f"Catalog.ThrowableTemplates tem {len(baked)} templates: sem esse conjunto nenhum item "
        "entra no painel de arremesso — rode python3 tools/collect.py")

    assert '"SA_ThrowItem"' in discovery, (
        "SA_ThrowItem (o container antigo) precisa continuar em RETIRED_SPELLS: quem já tinha "
        "essa spell gravada no save fica com um identificador órfão sem a limpeza")

    block = lua.split(f'new entry "{THROW_PANEL_SPELL}"', 1)
    assert len(block) == 1, f"{THROW_PANEL_SPELL} não pode estar em Catalog.lua (é gerado no .txt de stats, não no runtime)"

    assert f'"{THROW_PANEL_SPELL}",' not in lua, (
        f"{THROW_PANEL_SPELL} abre o painel; não é um container e não entra em Catalog.Containers")


def check_open_panel_entry(entries):
    entry = entries[THROW_PANEL_SPELL]
    assert entry["_using"] == "Throw_Throw", (
        f"{THROW_PANEL_SPELL}: tem de herdar de Throw_Throw — é a mira nativa de arremesso que o "
        "painel preenche com o item, e o custo de Ação vem daí")
    assert "SpellFlags" not in entry, (
        f"{THROW_PANEL_SPELL}: os SpellFlags vêm do Throw_Throw, com InventorySelection — é o que faz o "
        "servidor aceitar item de inventário como alvo do arremesso. Quem tira a flag é só o cliente, "
        "em Client/ThrowPanel.lua (NOTES.md, P16f e sexta rodada)")
    assert '~= "InventorySelection"' in client_throw_panel and "stat:Sync()" in client_throw_panel, (
        "Client/ThrowPanel.lua tem de remover InventorySelection do stat do painel e dar Sync() local: "
        "sem isso o botão abre o seletor do próprio inventário em vez da mira vazia")
    assert entry["DisplayName"] == f"{THROW_PANEL_LABEL_HANDLE};1", (
        f"{THROW_PANEL_SPELL}: DisplayName errado")
    assert entry["Description"] == f"{THROW_PANEL_DESC_HANDLE};1", (
        f"{THROW_PANEL_SPELL}: Description errada")
    assert "ContainerSpells" not in entry, (
        f"{THROW_PANEL_SPELL}: não é um spell-container, não precisa de ContainerSpells")
    for handle in (THROW_PANEL_LABEL_HANDLE, THROW_PANEL_DESC_HANDLE):
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
    check_base_entry(entries)
    check_icon_atlases()
    check_runtime_tables()
    check_spell_names_never_collide()
    check_throw_panel()
    check_open_panel_entry(entries)

    assert '"SA_Dig"' in discovery, (
        "SA_Dig foi descontinuado: precisa continuar em RETIRED_SPELLS para limpar o save "
        "de quem já carregou a pá")
    assert "Dig" not in lua and "SHOVEL" not in lua, (
        "Cavar foi descontinuado: Catalog.lua não deve mais gerar nada ligado a ele")

    for translation in ("Tomar Poção", "Usar Pergaminho", "Arremessar"):
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
        "só os das categorias e o botão de abrir o painel de arremesso ficam no .xml")

    print(f"OK — {len(CATEGORIES_UNDER_TEST)} containers vazios, {THROW_PANEL_SPELL} sem sublista, "
          f"{len(handles)} handles fixos, sub-spells em runtime")


if __name__ == "__main__":
    sys.exit(main())
