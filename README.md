# Shared Actions

*[English](#english) · [Português](#português)*

Use any party member's potions, scrolls, throwables and shovel straight from
your Action Bar — no more passing items around mid-fight. Works with modded items too: the
list is discovered from your own installation every time you load a save.

[![Version](https://img.shields.io/github/v/release/belakarkache/bg3-shared-actions?color=blue&label=version)](https://github.com/belakarkache/bg3-shared-actions/releases/latest) ![BG3](https://img.shields.io/badge/BG3-Patch%208-green)

---

## English

### What it does

Adds four buttons to the Action Bar:

- **Take Potion** — every potion carried by anyone in the party
- **Use Scroll** — every scroll carried by anyone in the party
- **Throw Item** — every potion, grenade and throwable carried by the party that
  does something when it breaks
- **Dig** — available to everyone as long as *someone* in the party carries a
  shovel, and no shovel ever changes hands

Click one and the item is used from the bag of whoever is actually carrying it.
The list only ever shows what the party really has, and the quantity appears in
the tooltip.

It uses the game's own rules: the Bonus Action (or Action) is charged by the
engine, and buttons grey out when you can't afford them. Scrolls keep their
native targeting, animation and effect, and thrown items keep the projectile,
area and effect the game gives them when they break.

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
5. Launch the game. The buttons appear on the Action Bar.

### Good to know

- A few scrolls that open their own sub-menu (Chromatic Orb, Enlarge/Reduce,
  Disguise Self…) don't appear in the list. Use them from the inventory.
- **Potions and scrolls from other mods show up automatically.** The list is
  built from your installed mods when the save loads, so nothing has to be
  rebuilt or configured.
- Works alongside BetterHotbar, ImpUI, MCM and 5eSpells — it doesn't overwrite
  any Larian file.
- Not tested in co-op.

---

## Português

### O que faz

Adiciona quatro botões à Action Bar:

- **Tomar Poção** — todas as poções carregadas por qualquer membro do grupo
- **Usar Pergaminho** — todos os pergaminhos carregados por qualquer membro
- **Arremessar Item** — toda poção, granada e arremessável do grupo que faz algo
  ao se quebrar
- **Cavar** — disponível para todo o grupo enquanto *alguém* estiver com uma pá,
  e nenhuma pá troca de dono

Clicou, o item é usado da mochila de quem realmente o carrega. A lista mostra só
o que o grupo tem de verdade, e a quantidade aparece no tooltip.

O mod usa as regras do próprio jogo: quem cobra a Ação Bônus (ou a Ação) é a
engine, e o botão fica acinzentado quando você não tem o recurso. Pergaminhos
mantêm mira, animação e efeito nativos, e o item arremessado mantém o projétil,
a área e o efeito que o jogo lhe dá ao se quebrar.

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
5. Inicie o jogo. Os botões aparecem na Action Bar.

### Bom saber

- Alguns pergaminhos que abrem submenu próprio (Orbe Cromático, Ampliar/Reduzir,
  Disfarçar-se…) não aparecem na lista. Use pelo inventário.
- **Poções e pergaminhos de outros mods aparecem sozinhos.** A lista é montada a
  partir dos mods instalados quando o save carrega, sem regerar nem configurar
  nada.
- Convive com BetterHotbar, ImpUI, MCM e 5eSpells — não sobrescreve nenhum
  arquivo da Larian.
- Não testado em co-op.

---

Autora: **[icka.dev](https://www.icka.dev/)**
