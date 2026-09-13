# Shared Actions

*[English](#english) · [Português](#português)*

Use any party member's potions and scrolls straight from your Action Bar — no
more passing items around mid-fight.

![Version](https://img.shields.io/badge/version-1.0.1-blue) ![BG3](https://img.shields.io/badge/BG3-Patch%208-green)

---

## English

### What it does

Adds two buttons to the Action Bar:

- **Take Potion** — every potion carried by anyone in the party
- **Use Scroll** — every scroll carried by anyone in the party

Click one and the item is used from the bag of whoever is actually carrying it.
The list only ever shows what the party really has, and the quantity appears in
the tooltip.

It uses the game's own rules: the Bonus Action (or Action) is charged by the
engine, and buttons grey out when you can't afford them. Scrolls keep their
native targeting, animation and effect.

### Requirements

- Baldur's Gate 3, Patch 8
- [BG3 Script Extender](https://github.com/Norbyte/bg3se) — **required**

### Installing

1. **Back up your save first.** This mod grants spells that are written into
   your save file.
2. Download `SharedActions.pak` from the [Releases](../../releases) page.
3. Put it in your Mods folder:
   `%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\Mods`
   (paste that into the Windows Explorer address bar) or install using the BG3 Mod Manager
4. Open **BG3 Mod Manager**, enable **Shared Actions**, and click
   *Export Load Order to Game*.
5. Launch the game. The two buttons appear on the Action Bar.

### Good to know

- A few scrolls that open their own sub-menu (Chromatic Orb, Enlarge/Reduce,
  Disguise Self…) don't appear in the list. Use them from the inventory.
- Items added by other mods won't show up unless the mod is rebuilt to include
  them.
- Works alongside BetterHotbar, ImpUI, MCM and 5eSpells — it doesn't overwrite
  any Larian file.
- Not tested in co-op.

### How it works

The mod never casts anything from Lua — casting through Osiris ignores costs and
preconditions, which would mean keeping a parallel action economy in sync with
the engine's. Instead, everything the player clicks is a **real spell with real
`UseCosts`** inside a native spell container: the engine charges the resource,
greys the button out and respects combat, incapacitation and dialogue. Lua only
decides *which* spells exist and *what happens after the cast*.

A build step reads the game's own data and writes one sub-spell per consumable
(183 of them), copying each item's own action cost — the exceptions are real, so
a per-category cost would hand out free actions. At runtime the container's list
is rewritten on every inventory change, so it holds exactly what the party
carries. Potions call `Osi.Use` on the real item, wherever it is; scrolls inherit
the scroll's own spell, which is what keeps native aiming, animation and effect.

### Repository contents

```
src/      the mod tree, exactly as it is packed into the .pak
tools/    the build pipeline: reads the game data, writes stats, localization,
          the Lua catalog and the icon atlas
tests/    assertions over the generated files — run before every install
```

The generated catalog and the icon source art are not published: they are
derived from the game's own files. `tools/collect.py` rebuilds the catalog from
a local extraction.

### Building from source

Needs Python 3 (standard library only), [LSLib/Divine][lslib] and, for the
icons, `texconv`. Point the tools at your own paths:

```bash
export BG3_DATA=/path/to/extracted/game/data   # the .pak trees, unpacked
export BG3_BUILD=/path/to/a/scratch/dir
export DIVINE=/path/to/Divine.exe TEXCONV=/path/to/texconv.exe

./tools/generate.sh                  # catalog + stats + localization + tests
python3 tools/make_item_atlas.py     # only when the catalog changes

cp -r src build
divine -g bg3 -a convert-resource -o lsf \
  -s "build/Public/SharedActions/Content/UI/[PAK]_UI/_merged.lsx" \
  -d "build/Public/SharedActions/Content/UI/[PAK]_UI/_merged.lsf"
rm "build/Public/SharedActions/Content/UI/[PAK]_UI/_merged.lsx"
divine -g bg3 -a create-package -s build -d SharedActions.pak
```

[lslib]: https://github.com/Norbyte/lslib

---

## Português

### O que faz

Adiciona dois botões à Action Bar:

- **Tomar Poção** — todas as poções carregadas por qualquer membro do grupo
- **Usar Pergaminho** — todos os pergaminhos carregados por qualquer membro

Clicou, o item é usado da mochila de quem realmente o carrega. A lista mostra só
o que o grupo tem de verdade, e a quantidade aparece no tooltip.

O mod usa as regras do próprio jogo: quem cobra a Ação Bônus (ou a Ação) é a
engine, e o botão fica acinzentado quando você não tem o recurso. Pergaminhos
mantêm mira, animação e efeito nativos.

### Requisitos

- Baldur's Gate 3, Patch 8
- [BG3 Script Extender](https://github.com/Norbyte/bg3se) — **obrigatório**

### Instalação

1. **Faça backup do seu save.** O mod concede magias que ficam gravadas no save.
2. Baixe o `SharedActions.pak` na página de [Releases](../../releases).
3. Coloque o arquivo na sua pasta de Mods:
   `%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\Mods`
   (cole isso na barra de endereço do Explorador de Arquivos) ou instale normalmente pelo BG3 Mod Manager
4. Abra o **BG3 Mod Manager**, ative o **Shared Actions** e clique em
   *Export Load Order to Game*.
5. Inicie o jogo. Os dois botões aparecem na Action Bar.

### Bom saber

- Alguns pergaminhos que abrem submenu próprio (Orbe Cromático, Ampliar/Reduzir,
  Disfarçar-se…) não aparecem na lista. Use pelo inventário.
- Itens de outros mods não aparecem, a menos que o mod seja regerado incluindo
  eles.
- Convive com BetterHotbar, ImpUI, MCM e 5eSpells — não sobrescreve nenhum
  arquivo da Larian.
- Não testado em co-op.

### Como funciona

O mod não conjura nada pelo Lua — conjurar via Osiris ignora custo e
pré-condição, o que obrigaria a manter uma economia de ações paralela à da
engine. Em vez disso, o que o jogador clica é um **spell de verdade, com
`UseCosts` de verdade**, dentro de um spell container nativo: a engine cobra o
recurso, acinzenta o botão e respeita combate, incapacitação e diálogo. O Lua só
decide *quais* spells existem e *o que acontece depois do cast*.

Um passo de build lê os dados do próprio jogo e escreve um sub-spell por
consumível (183 deles), copiando o custo de ação de cada item — as exceções são
reais, então fixar o custo por categoria daria ações de graça. Em runtime a
lista do container é reescrita a cada mudança de inventário, e por isso mostra
exatamente o que a party carrega. Poções chamam `Osi.Use` no item real, onde ele
estiver; pergaminhos herdam a magia do próprio pergaminho, que é o que preserva
mira, animação e efeito nativos.

### Conteúdo do repositório

```
src/      a árvore do mod, exatamente como vai dentro do .pak
tools/    o pipeline de build: lê os dados do jogo e escreve stats, localização,
          o catálogo Lua e o atlas de ícones
tests/    asserções sobre o que foi gerado — rode antes de instalar
```

O catálogo gerado e a arte de origem dos ícones não são publicados: são
derivados dos arquivos do jogo. O `tools/collect.py` regera o catálogo a partir
de uma extração local.

### Build a partir do código

Precisa de Python 3 (só stdlib), [LSLib/Divine][lslib] e, para os ícones, do
`texconv`. Aponte as ferramentas para os seus caminhos:

```bash
export BG3_DATA=/caminho/para/os/dados/extraidos
export BG3_BUILD=/caminho/para/uma/pasta/temporaria
export DIVINE=/caminho/para/Divine.exe TEXCONV=/caminho/para/texconv.exe

./tools/generate.sh                  # catálogo + stats + localização + testes
python3 tools/make_item_atlas.py     # só quando o catálogo muda

cp -r src build
divine -g bg3 -a convert-resource -o lsf \
  -s "build/Public/SharedActions/Content/UI/[PAK]_UI/_merged.lsx" \
  -d "build/Public/SharedActions/Content/UI/[PAK]_UI/_merged.lsf"
rm "build/Public/SharedActions/Content/UI/[PAK]_UI/_merged.lsx"
divine -g bg3 -a create-package -s build -d SharedActions.pak
```

---

Autora: **[icka.dev](https://www.icka.dev/)**
