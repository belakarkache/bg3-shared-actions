# Shared Actions

*[English](#english) · [Português](#português)*

Use any party member's potions and scrolls straight from your Action Bar — no
more passing items around mid-fight. Works with modded items too: the list is
discovered from your own installation every time you load a save.

![Version](https://img.shields.io/badge/version-1.1.0-blue) ![BG3](https://img.shields.io/badge/BG3-Patch%208-green)

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
- **Potions and scrolls from other mods show up automatically.** The list is
  built from your installed mods when the save loads, so nothing has to be
  rebuilt or configured.
- An item is only listed if the game classes it as a potion or a scroll *and* it
  descends from one of the vanilla base templates. A modded item built from
  scratch, without that ancestry, is left out on purpose — that same check is
  what keeps weapon coatings and poisons off the potion list.
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

The sub-spells are not shipped in the `.pak`: they are **created at runtime**.
When the session loads, the mod walks every `Object` stat and root template in
your installation — around 21 ms for the whole game — and calls
`Ext.Stats.Create` once per eligible item, copying that item's own action cost;
the exceptions are real, so a per-category cost would hand out free actions.
That is why items from other mods need no rebuild. At runtime the container's
list is rewritten on every inventory change, so it holds exactly what the party
carries. Potions call `Osi.Use` on the real item, wherever it is; scrolls inherit
the scroll's own spell, which is what keeps native aiming, animation and effect.
Names and counts come from the game's own localisation, pushed to the client
over an `Ext.Net` channel.

### Repository contents

```
src/      the mod tree, exactly as it is packed into the .pak, plus the Lua that
          discovers the items at runtime
tools/    the build pipeline: writes the two spell containers, the category
          localization and the icon atlas
tests/    assertions over the generated files — run before every install
```

The build is deliberately small: the `.pak` carries three stat entries and four
localization handles. Everything per item happens in `Server/Discovery.lua`.

The generated catalog and the icon source art are not published: they are
derived from the game's own files. `tools/collect.py` rebuilds the catalog from
a local extraction, and it is only needed for the rarity-framed icon atlas.

### Building from source

Needs Python 3 (standard library only), [LSLib/Divine][lslib] and, for the
icons, `texconv`. Point the tools at your own paths:

```bash
export BG3_DATA=/path/to/extracted/game/data   # only for the icon atlas
export BG3_BUILD=/path/to/a/scratch/dir
export DIVINE=/path/to/Divine.exe TEXCONV=/path/to/texconv.exe

./tools/generate.sh                  # containers + localization + tests

python3 tools/collect.py             # only for the icon atlas; needs BG3_DATA
python3 tools/make_item_atlas.py     # then rerun generate.sh

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
- **Poções e pergaminhos de outros mods aparecem sozinhos.** A lista é montada a
  partir dos mods instalados quando o save carrega, sem regerar nem configurar
  nada.
- Um item só entra se o jogo o classificar como poção ou pergaminho *e* ele
  descender de um dos templates base do jogo. Item de mod feito do zero, sem essa
  ascendência, fica de fora de propósito — é a mesma checagem que mantém óleo de
  arma e veneno fora da lista de poções.
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

Os sub-spells não vão dentro do `.pak`: são **criados em runtime**. Ao carregar a
sessão, o mod varre todos os stats `Object` e root templates da sua instalação —
cerca de 21 ms para o jogo inteiro — e chama `Ext.Stats.Create` uma vez por item
elegível, copiando o custo de ação de cada um; as exceções são reais, então fixar
o custo por categoria daria ações de graça. É por isso que item de outro mod não
exige regerar nada. Em runtime a lista do container é reescrita a cada mudança de
inventário, e por isso mostra exatamente o que a party carrega. Poções chamam
`Osi.Use` no item real, onde ele estiver; pergaminhos herdam a magia do próprio
pergaminho, que é o que preserva mira, animação e efeito nativos. Nome e
quantidade saem da localização do próprio jogo, enviados ao cliente por um canal
`Ext.Net`.

### Conteúdo do repositório

```
src/      a árvore do mod, exatamente como vai dentro do .pak, mais o Lua que
          descobre os itens em runtime
tools/    o pipeline de build: escreve os dois spell containers, a localização
          das categorias e o atlas de ícones
tests/    asserções sobre o que foi gerado — rode antes de instalar
```

O build é pequeno de propósito: o `.pak` leva três entradas de stats e quatro
handles de localização. Tudo que é por item acontece no `Server/Discovery.lua`.

O catálogo gerado e a arte de origem dos ícones não são publicados: são
derivados dos arquivos do jogo. O `tools/collect.py` regera o catálogo a partir
de uma extração local, e só é necessário para o atlas de ícones com fundo de
raridade.

### Build a partir do código

Precisa de Python 3 (só stdlib), [LSLib/Divine][lslib] e, para os ícones, do
`texconv`. Aponte as ferramentas para os seus caminhos:

```bash
export BG3_DATA=/caminho/para/os/dados/extraidos   # só para o atlas de ícones
export BG3_BUILD=/caminho/para/uma/pasta/temporaria
export DIVINE=/caminho/para/Divine.exe TEXCONV=/caminho/para/texconv.exe

./tools/generate.sh                  # containers + localização + testes

python3 tools/collect.py             # só para o atlas de ícones; precisa de BG3_DATA
python3 tools/make_item_atlas.py     # depois rode generate.sh de novo

cp -r src build
divine -g bg3 -a convert-resource -o lsf \
  -s "build/Public/SharedActions/Content/UI/[PAK]_UI/_merged.lsx" \
  -d "build/Public/SharedActions/Content/UI/[PAK]_UI/_merged.lsf"
rm "build/Public/SharedActions/Content/UI/[PAK]_UI/_merged.lsx"
divine -g bg3 -a create-package -s build -d SharedActions.pak
```

---

Autora: **[icka.dev](https://www.icka.dev/)**
