local Catalog = Catalog

local TemplateToSpell = Catalog.TemplateToSpell
local SpellToTemplate = Catalog.SpellToTemplate
local SpellContainer = Catalog.SpellContainer
local Containers = Catalog.Containers
local Labels = Catalog.Labels
local LegacySpells = Catalog.LegacySpells
local RemovesItemOnCast = Catalog.RemovesItemOnCast
local ScrollVariants = Catalog.ScrollVariants
local VariantGroupOf = Catalog.VariantGroupOf

local POLL_TRIES, POLL_STEP_MS = 12, 250
local USE_RECONCILE_MS = 10000

local channel = Ext.Net.CreateChannel(ModuleUUID, "SharedActions_Labels")
local variantMenuChannel = Ext.Net.CreateChannel(ModuleUUID, "SharedActions_VariantMenu")

local grantedSpellsByCharacter = {}
local reconciledWithSave = {}
local partyCountBySpell = {}
local appliedContainerSpells = {}
local selfTriggeredUseByTemplate = {}
local swappedMenu = nil
local strippedCharacters = {}

local partyMembers = Party.Members

local function countInParty(template, queryAnchor)
    return Osi.TemplateIsInPartyInventory(template, queryAnchor, 0) or 0
end

local function isHiddenFromMenu(spell)
    local group = VariantGroupOf[spell]
    if not swappedMenu then return group ~= nil end
    return SpellContainer[spell] == swappedMenu.container and group ~= swappedMenu.picker
end

local function grantSpell(character, spell)
    local granted = grantedSpellsByCharacter[character]
    if not granted or granted[spell] then return end
    if isHiddenFromMenu(spell) then return end
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
    if not stat then return end
    stat.ContainerSpells = joined
    stat:Sync()
end

local function rebuildContainer(container)
    if swappedMenu and swappedMenu.container == container then return end
    local spells = {}
    for spell, count in pairs(partyCountBySpell) do
        if count > 0 and SpellContainer[spell] == container and not isHiddenFromMenu(spell) then
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
        if handles then payload[spell] = { count, handles[1], handles[2], handles[3] } end
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
        if count > 0 and not isHiddenFromMenu(spell) then
            available[spell] = true
        end
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
        for _, spell in ipairs(LegacySpells) do
            if Osi.HasSpell(character, spell) == 1 then
                Osi.RemoveSpell(character, spell, 0)
            end
        end
    end

    reconciledWithSave[character] = true
end

local function stripCharacter(character)
    if strippedCharacters[character] then return end
    strippedCharacters[character] = true
    grantedSpellsByCharacter[character] = nil
    reconciledWithSave[character] = nil
    Party.StripSpells(character, Containers)
    local spells = {}
    for spell in pairs(SpellContainer) do
        spells[#spells + 1] = spell
    end
    Party.StripSpells(character, spells)
    Party.StripSpells(character, LegacySpells)
end

local function resync()
    local members, others = Party.Split()
    for _, character in ipairs(others) do
        stripCharacter(character)
    end
    if #members == 0 then return end
    local queryAnchor = members[1]

    local changed = {}
    for template, spells in pairs(TemplateToSpell) do
        local count = countInParty(template, queryAnchor)
        for _, spell in ipairs(spells) do
            if partyCountBySpell[spell] ~= count then
                partyCountBySpell[spell] = count
                if count > 0 then changed[spell] = count end
            end
        end
    end

    local available = availableSpells()
    for _, character in ipairs(members) do
        setupCharacter(character, available)
    end

    rebuildAllContainers()
    pushLabels(changed)
end

local function refreshTemplate(template)
    local spells = TemplateToSpell[template]
    if not spells then return end
    local members = partyMembers()
    if #members == 0 then return end

    for _, character in ipairs(members) do
        if not grantedSpellsByCharacter[character] then return resync() end
    end

    local count = countInParty(template, members[1])

    for _, spell in ipairs(spells) do
        if partyCountBySpell[spell] ~= count then
            partyCountBySpell[spell] = count
            rebuildContainer(SpellContainer[spell])
            if count > 0 then pushLabels({ [spell] = count }) end
        end

        for _, character in ipairs(members) do
            if count > 0 then grantSpell(character, spell) else revokeSpell(character, spell) end
        end
    end
end

local function templateCount(template)
    local spells = TemplateToSpell[template]
    return spells and partyCountBySpell[spells[1]]
end

local function pollUntilCountChanges(template, triesLeft)
    local before = templateCount(template)
    Ext.Timer.WaitFor(POLL_STEP_MS, function()
        refreshTemplate(template)
        if triesLeft > 1 and templateCount(template) == before then
            pollUntilCountChanges(template, triesLeft - 1)
        end
    end)
end

local function showVariantsInMenu(picker)
    local container = SpellContainer[picker]
    local leaves = ScrollVariants[picker]
    swappedMenu = { picker = picker, container = container }

    writeContainerSpells(container, { table.unpack(leaves) })
    for _, character in ipairs(partyMembers()) do
        for spell in pairs(grantedSpellsByCharacter[character] or {}) do
            if isHiddenFromMenu(spell) then revokeSpell(character, spell) end
        end
        for _, leaf in ipairs(leaves) do
            grantSpell(character, leaf)
        end
    end
end

local function restoreMenu()
    if not swappedMenu then return end
    local container = swappedMenu.container
    swappedMenu = nil
    rebuildContainer(container)
    resync()
end

local function isLeafOfSwappedMenu(spell)
    return swappedMenu ~= nil and VariantGroupOf[spell] == swappedMenu.picker
end

variantMenuChannel:SetHandler(function(payload)
    if type(payload) == "table" and payload.restore then restoreMenu() end
end)

Ext.Entity.OnCreateDeferred("SpellCastState", function(entity)
    local state = entity.SpellCastState
    local prototype = state and state.SpellId and state.SpellId.Prototype
    if prototype and ScrollVariants[prototype] then showVariantsInMenu(prototype) end
end)

Ext.Osiris.RegisterListener("CastSpellFailed", 5, "after", function(_, spell)
    if isLeafOfSwappedMenu(spell) or (swappedMenu and swappedMenu.picker == spell) then
        restoreMenu()
    end
end)

Ext.Osiris.RegisterListener("CastedSpell", 5, "after", function(caster, spell)
    if isLeafOfSwappedMenu(spell) then restoreMenu() end
    if ScrollVariants[spell] then return end
    local template = SpellToTemplate[spell]
    if not template then return end

    local own = Osi.GetItemByTemplateInInventory(template, caster)
    local item = own or Osi.GetItemByTemplateInPartyInventory(template, caster)
    if not item then return end

    local key = string.lower(template)

    if RemovesItemOnCast[SpellContainer[spell]] then
        Osi.TemplateRemoveFrom(template, own and caster or Osi.GetInventoryOwner(item), 1)
        pollUntilCountChanges(key, POLL_TRIES)
        return
    end

    Osi.Use(caster, item, 1, 0, "")

    local remaining = (partyCountBySpell[spell] or 0) - 1
    if remaining <= 0 then return end

    local changed = {}
    for _, sibling in ipairs(TemplateToSpell[key] or {}) do
        partyCountBySpell[sibling] = remaining
        changed[sibling] = remaining
    end
    pushLabels(changed)
    selfTriggeredUseByTemplate[key] = true
    Ext.Timer.WaitFor(USE_RECONCILE_MS, function()
        selfTriggeredUseByTemplate[key] = nil
        refreshTemplate(key)
    end)
end)

Ext.Osiris.RegisterListener("TemplateAddedTo", 4, "after", function(template)
    refreshTemplate(string.lower(template))
end)

Ext.Osiris.RegisterListener("TemplateRemovedFrom", 3, "after", function(template)
    refreshTemplate(string.lower(template))
end)

Ext.Osiris.RegisterListener("TemplateUseFinished", 4, "after", function(_, template)
    local key = string.lower(template)
    if not TemplateToSpell[key] or selfTriggeredUseByTemplate[key] then return end
    pollUntilCountChanges(key, POLL_TRIES)
end)

Ext.Osiris.RegisterListener("CharacterJoinedParty", 1, "after", function(character)
    resync()
    if not Party.IsPlayable(character) then return end
    if not grantedSpellsByCharacter[character] then
        setupCharacter(character, availableSpells())
    end
end)

Ext.Osiris.RegisterListener("CharacterLeftParty", 1, "after", function(character)
    grantedSpellsByCharacter[character] = nil
    reconciledWithSave[character] = nil
    strippedCharacters[character] = nil
end)

Ext.Osiris.RegisterListener("LevelGameplayStarted", 2, "after", function()
    grantedSpellsByCharacter, partyCountBySpell = {}, {}
    reconciledWithSave, appliedContainerSpells = {}, {}
    strippedCharacters = {}
    swappedMenu = nil
    resync()
end)
