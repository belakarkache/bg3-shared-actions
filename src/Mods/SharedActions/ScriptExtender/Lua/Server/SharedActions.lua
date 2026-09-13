local Catalog = Catalog

local TemplateToSpell = Catalog.TemplateToSpell
local SpellToTemplate = Catalog.SpellToTemplate
local SpellContainer = Catalog.SpellContainer
local Containers = Catalog.Containers
local Labels = Catalog.Labels
local LegacySpells = Catalog.LegacySpells
local RemovesItemOnCast = Catalog.RemovesItemOnCast
local Dig = Catalog.Dig

local POLL_TRIES, POLL_STEP_MS = 12, 250
local USE_RECONCILE_MS = 10000

local channel = Ext.Net.CreateChannel(ModuleUUID, "SharedActions_Labels")

local grantedSpellsByCharacter = {}
local reconciledWithSave = {}
local partyCountBySpell = {}
local appliedContainerSpells = {}
local selfTriggeredUseByTemplate = {}
local digGrantedByCharacter = {}
local shovelInParty = false
local digTargetByCaster = {}

local function log(...)
    print("[SharedActions]", ...)
end

local function partyMembers()
    local members = {}
    for _, row in ipairs(Osi.DB_Players:Get(nil) or {}) do
        members[#members + 1] = row[1]
    end
    return members
end

local function carriesShovel(character)
    local shovel = Osi.GetItemByTagInInventory(Dig.tag, character)
    return shovel ~= nil and shovel ~= ""
end

local function grantDig(character)
    if Osi.HasActiveStatus(character, Dig.status) == 0 then
        Osi.ApplyStatus(character, Dig.status, -1.0, 1, character)
    end
    if digGrantedByCharacter[character] then return end
    Osi.AddSpell(character, Dig.spell, 0, 0)
    digGrantedByCharacter[character] = true
end

local function revokeDig(character, carries)
    if not digGrantedByCharacter[character] then return end
    digGrantedByCharacter[character] = nil
    Osi.RemoveSpell(character, Dig.spell, 0)
    if not carries then Osi.RemoveStatus(character, Dig.status) end
end

local function countInParty(template, queryAnchor)
    return Osi.TemplateIsInPartyInventory(template, queryAnchor, 0) or 0
end

local function grantSpell(character, spell)
    local granted = grantedSpellsByCharacter[character]
    if not granted or granted[spell] then return end
    Osi.AddSpell(character, spell, 0, 0)
    granted[spell] = true
end

local function revokeSpell(character, spell)
    local granted = grantedSpellsByCharacter[character]
    if not granted or not granted[spell] then return end
    Osi.RemoveSpell(character, spell, 0)
    granted[spell] = nil
end

local function ensureContainersGranted(character)
    if grantedSpellsByCharacter[character] then return end
    grantedSpellsByCharacter[character] = {}
    for _, container in ipairs(Containers) do
        Osi.AddSpell(character, container, 0, 0)
    end
end

local function writeContainerSpells(container, spells)
    table.sort(spells)
    local joined = table.concat(spells, ";")
    if appliedContainerSpells[container] == joined then return end
    appliedContainerSpells[container] = joined

    local stat = Ext.Stats.Get(container)
    if not stat then
        log("ALERTA: stat não encontrado:", container)
        return
    end
    stat.ContainerSpells = joined
    stat:Sync()
end

local function rebuildContainer(container)
    local spells = {}
    for spell, count in pairs(partyCountBySpell) do
        if count > 0 and SpellContainer[spell] == container then
            spells[#spells + 1] = spell
        end
    end
    writeContainerSpells(container, spells)
end

local function rebuildAllContainers()
    for _, container in ipairs(Containers) do
        rebuildContainer(container)
    end
end

local function labelPayload(counts)
    local payload = {}
    for spell, count in pairs(counts) do
        local handles = Labels[spell]
        if handles then payload[spell] = { count, handles[1], handles[2] } end
    end
    return payload
end

local function pushLabels(changed)
    if next(changed) == nil then return end
    channel:Broadcast(labelPayload(changed))
end

channel:SetRequestHandler(function()
    local snapshot = {}
    for spell, count in pairs(partyCountBySpell) do
        if count > 0 then snapshot[spell] = count end
    end
    return labelPayload(snapshot)
end)

local function availableSpells()
    local available = {}
    for spell, count in pairs(partyCountBySpell) do
        if count > 0 then available[spell] = true end
    end
    return available
end

local function setupCharacter(character, available)
    ensureContainersGranted(character)
    local granted = grantedSpellsByCharacter[character]
    local alreadyReconciled = reconciledWithSave[character]
    for spell in pairs(SpellContainer) do
        if available[spell] then
            grantSpell(character, spell)
        elseif granted[spell] then
            revokeSpell(character, spell)
        elseif not alreadyReconciled and Osi.HasSpell(character, spell) == 1 then
            Osi.RemoveSpell(character, spell, 0)
        end
    end
    if not alreadyReconciled then
        local retired = 0
        for _, spell in ipairs(LegacySpells) do
            if Osi.HasSpell(character, spell) == 1 then
                Osi.RemoveSpell(character, spell, 0)
                retired = retired + 1
            end
        end
        if retired > 0 then log("magias de build antigo removidas:", retired, character) end
    end

    reconciledWithSave[character] = true
end

local function refreshDig(members)
    members = members or partyMembers()
    if #members == 0 then return end

    local carriers = {}
    local hadShovel = shovelInParty
    shovelInParty = false
    for _, character in ipairs(members) do
        carriers[character] = carriesShovel(character)
        if carriers[character] then shovelInParty = true end
    end

    for _, character in ipairs(members) do
        if shovelInParty then
            grantDig(character)
        else
            revokeDig(character, carriers[character])
        end
    end

    if hadShovel ~= shovelInParty then log("pa na party:", shovelInParty) end
end

local function resync()
    local members = partyMembers()
    if #members == 0 then return end
    local queryAnchor = members[1]

    local changed = {}
    for template, spell in pairs(TemplateToSpell) do
        local count = countInParty(template, queryAnchor)
        if partyCountBySpell[spell] ~= count then
            partyCountBySpell[spell] = count
            if count > 0 then changed[spell] = count end
        end
    end

    local available = availableSpells()
    for _, character in ipairs(members) do
        setupCharacter(character, available)
    end

    rebuildAllContainers()
    pushLabels(changed)
    refreshDig(members)
end

local function refreshTemplate(template)
    local spell = TemplateToSpell[template]
    if not spell then return end
    local members = partyMembers()
    if #members == 0 then return end

    for _, character in ipairs(members) do
        if not grantedSpellsByCharacter[character] then return resync() end
    end

    local count = countInParty(template, members[1])

    if partyCountBySpell[spell] ~= count then
        partyCountBySpell[spell] = count
        rebuildContainer(SpellContainer[spell])
        if count > 0 then pushLabels({ [spell] = count }) end
    end

    for _, character in ipairs(members) do
        if count > 0 then grantSpell(character, spell) else revokeSpell(character, spell) end
    end
end

local function pollUntilCountChanges(template, triesLeft)
    local spell = TemplateToSpell[template]
    local before = partyCountBySpell[spell]
    Ext.Timer.WaitFor(POLL_STEP_MS, function()
        refreshTemplate(template)
        if triesLeft > 1 and partyCountBySpell[spell] == before then
            pollUntilCountChanges(template, triesLeft - 1)
        end
    end)
end

Ext.Osiris.RegisterListener("CastedSpell", 5, "after", function(caster, spell)
    local template = SpellToTemplate[spell]
    if not template then return end

    local own = Osi.GetItemByTemplateInInventory(template, caster)
    local item = own or Osi.GetItemByTemplateInPartyInventory(template, caster)
    if not item then
        log("ALERTA: usou", spell, "mas não achei o item na party")
        return
    end

    local key = string.lower(template)

    if RemovesItemOnCast[SpellContainer[spell]] then
        Osi.TemplateRemoveFrom(template, own and caster or Osi.GetInventoryOwner(item), 1)
        pollUntilCountChanges(key, POLL_TRIES)
        return
    end

    Osi.Use(caster, item, 1, 0, "")

    local remaining = (partyCountBySpell[spell] or 0) - 1
    if remaining <= 0 then return end

    partyCountBySpell[spell] = remaining
    pushLabels({ [spell] = remaining })
    selfTriggeredUseByTemplate[key] = true
    Ext.Timer.WaitFor(USE_RECONCILE_MS, function()
        selfTriggeredUseByTemplate[key] = nil
        refreshTemplate(key)
    end)
end)

Ext.Osiris.RegisterListener("UsingSpellOnTarget", 6, "after", function(caster, target, spell)
    if spell == Dig.spell then digTargetByCaster[caster] = target end
end)

Ext.Osiris.RegisterListener("CastedSpell", 5, "after", function(caster, spell)
    local target = digTargetByCaster[caster]
    if spell ~= Dig.spell or not target then return end
    digTargetByCaster[caster] = nil
    Osi.UseSpell(caster, Dig.vanillaSpell, target)
end)

Ext.Osiris.RegisterListener("TemplateAddedTo", 4, "after", function(template, item)
    refreshTemplate(string.lower(template))
    if not shovelInParty and item and Osi.IsTagged(item, Dig.tag) == 1 then refreshDig() end
end)

Ext.Osiris.RegisterListener("TemplateRemovedFrom", 3, "after", function(template)
    refreshTemplate(string.lower(template))
    if shovelInParty then refreshDig() end
end)

Ext.Osiris.RegisterListener("TemplateUseFinished", 4, "after", function(_, template)
    local key = string.lower(template)
    if not TemplateToSpell[key] or selfTriggeredUseByTemplate[key] then return end
    pollUntilCountChanges(key, POLL_TRIES)
end)

Ext.Osiris.RegisterListener("CharacterJoinedParty", 1, "after", function(character)
    resync()
    if not grantedSpellsByCharacter[character] then
        setupCharacter(character, availableSpells())
    end
end)

Ext.Osiris.RegisterListener("CharacterLeftParty", 1, "after", function(character)
    grantedSpellsByCharacter[character] = nil
    reconciledWithSave[character] = nil
    revokeDig(character, carriesShovel(character))
end)

Ext.Osiris.RegisterListener("LevelGameplayStarted", 2, "after", function()
    grantedSpellsByCharacter, partyCountBySpell = {}, {}
    reconciledWithSave, appliedContainerSpells = {}, {}
    digGrantedByCharacter, shovelInParty = {}, false
    resync()
end)
