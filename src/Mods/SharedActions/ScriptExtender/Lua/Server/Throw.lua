local Catalog = Catalog

local SPELL_PREFIX = "SA_Throwable_"
local PROBE_SPELL_PREFIX = "SA_ThrowProbe_"
local TRANSFER_POLL_MS = 100
local TRANSFER_POLL_ATTEMPTS = 20
local PREVIEW_TARGET_KIND = 5
local PREVIEW_TARGETING_STATE_KIND = 0
local AIMING_TARGETING_STATE = 2
local PREVIEW_INJECT_ATTEMPTS = 30
local PREVIEW_QUEUE = "NetworkPreviewUpdateRequests"
local POLL_TRIES, POLL_STEP_MS = 12, 250

local channel = Ext.Net.CreateChannel(ModuleUUID, "SharedActions_Throw")

local itemInfo = {}
local keyBySpell = {}
local countByTemplate = {}
local pendingThrow = {}
local grantedByCharacter = {}
local appliedContainerSpells = nil
local castRequestHookRegistered = false
local strippedCharacters = {}
local pollingTemplates = {}

local function isThrowSpell(prototype)
    return prototype ~= nil and keyBySpell[prototype] ~= nil
end

local function safeRead(object, key)
    if object == nil then return nil end
    local ok, value = pcall(function() return object[key] end)
    if ok then return value end
    return nil
end

local function uuidOf(value)
    if value == nil then return nil end
    if type(value) == "string" then return string.sub(value, -36) end
    local ok, uuid = pcall(function() return value.Uuid.EntityUuid end)
    if ok then return uuid end
    return nil
end

local function jsonText(value)
    local ok, text = pcall(Ext.Json.Stringify, value)
    if ok then return text end
    return ""
end

local partyMembers = Party.Members

local translatedHandle = Tooltip.TranslatedHandle

local function spellNameFor(prefix, template)
    return prefix .. template.Name .. "_" .. #template.Name
end

local function iconFor(template)
    local key = "SA_Icon_" .. (template.Stats or "")
    if Catalog.IconKeys[key] then return key end
    return template.Icon
end

local function defineItemSpell(template)
    local spell = spellNameFor(SPELL_PREFIX, template)
    if keyBySpell[spell] then return end

    local fields = {
        SpellContainerID = Catalog.ThrowContainer,
        Icon = iconFor(template),
        DisplayName = Spells.HandleFor(spell) .. ";1",
    }
    local projectileSpell = Catalog.ThrowableTemplates[template.Id]
    if Tooltip.HasDescription(projectileSpell) then
        Tooltip.CopySpellText(fields, projectileSpell)
    else
        Tooltip.ApplyItemText(fields, template)
    end
    return Spells.Define(spell, Catalog.ThrowBaseSpell, fields)
end

local function discoverItems()
    local templates = Ext.Template.GetAllRootTemplates()
    if not templates then return end

    for guid in pairs(Catalog.ThrowableTemplates) do
        local template = templates[guid]
        if template then
            local spell = defineItemSpell(template)
            if spell then
                local key = string.lower(template.Name .. "_" .. template.Id)
                keyBySpell[spell] = key
                itemInfo[key] = {
                    originalKey = template.Name .. "_" .. template.Id,
                    spell = spell,
                    handle = Spells.HandleFor(spell),
                    nameHandle = translatedHandle(template.DisplayName),
                }
            end
            Catalog.LegacySpells[#Catalog.LegacySpells + 1] = spellNameFor(PROBE_SPELL_PREFIX, template)
        end
    end
end

local function countInParty(key, queryAnchor)
    return Osi.TemplateIsInPartyInventory(key, queryAnchor, 0) or 0
end

local function carries(key)
    return (countByTemplate[key] or 0) > 0
end

local function labelPayload(keys)
    local payload = {}
    for key in pairs(keys) do
        local info = itemInfo[key]
        if info and carries(key) then
            payload[info.spell] = { countByTemplate[key], info.handle, info.nameHandle or "" }
        end
    end
    return payload
end

local function pushLabels(keys)
    local payload = labelPayload(keys)
    if next(payload) then channel:Broadcast(payload) end
end

local function setGranted(character, spell, wanted)
    local granted = grantedByCharacter[character]
    if wanted and not granted[spell] then
        Osi.AddSpell(character, spell, 0, 0)
        granted[spell] = true
    elseif not wanted and granted[spell] then
        Osi.RemoveSpell(character, spell, 0)
        granted[spell] = nil
    end
end

local function setupCharacter(character)
    if grantedByCharacter[character] then return end
    grantedByCharacter[character] = {}
    Osi.AddSpell(character, Catalog.ThrowContainer, 0, 0)
    for spell, key in pairs(keyBySpell) do
        if carries(key) then
            setGranted(character, spell, true)
        elseif Osi.HasSpell(character, spell) == 1 then
            Osi.RemoveSpell(character, spell, 0)
        end
    end
end

local function rebuildContainer()
    local spells = {}
    for key, info in pairs(itemInfo) do
        if carries(key) then spells[#spells + 1] = info.spell end
    end
    table.sort(spells)
    local joined = table.concat(spells, ";")
    if joined == appliedContainerSpells then return end

    local stat = Ext.Stats.Get(Catalog.ThrowContainer)
    if not stat then return end
    appliedContainerSpells = joined
    stat.ContainerSpells = joined
    stat:Sync()
end

local function stripCharacter(character)
    if strippedCharacters[character] then return end
    strippedCharacters[character] = true
    grantedByCharacter[character] = nil
    local spells = { Catalog.ThrowContainer }
    for spell in pairs(keyBySpell) do
        spells[#spells + 1] = spell
    end
    Party.StripSpells(character, spells)
end

local function resync()
    local members, others = Party.Split()
    for _, character in ipairs(others) do
        stripCharacter(character)
    end
    if #members == 0 then return end

    local changed = {}
    for key in pairs(itemInfo) do
        local count = countInParty(key, members[1])
        if countByTemplate[key] ~= count then
            countByTemplate[key] = count
            changed[key] = true
        end
    end

    for _, character in ipairs(members) do
        setupCharacter(character)
        for key in pairs(changed) do
            setGranted(character, itemInfo[key].spell, carries(key))
        end
    end
    rebuildContainer()
    pushLabels(changed)
end

local function refreshTemplate(key)
    local info = itemInfo[key]
    if not info then return end
    local members = partyMembers()
    if #members == 0 then return end

    local count = countInParty(key, members[1])
    if countByTemplate[key] == count then return end
    countByTemplate[key] = count

    for _, character in ipairs(members) do
        setupCharacter(character)
        setGranted(character, info.spell, count > 0)
    end
    rebuildContainer()
    pushLabels({ [key] = true })
end

local function pollUntilCountChanges(key, triesLeft)
    local before = countByTemplate[key]
    Ext.Timer.WaitFor(POLL_STEP_MS, function()
        refreshTemplate(key)
        if triesLeft > 1 and countByTemplate[key] == before then
            pollUntilCountChanges(key, triesLeft - 1)
        else
            pollingTemplates[key] = nil
        end
    end)
end

local function scheduleRefresh(key)
    if not itemInfo[key] then return end
    refreshTemplate(key)
    if pollingTemplates[key] then return end
    pollingTemplates[key] = true
    pollUntilCountChanges(key, POLL_TRIES)
end

local function forceRefresh(key)
    countByTemplate[key] = nil
    refreshTemplate(key)
end

local function returnItem(casterUuid)
    local pending = pendingThrow[casterUuid]
    if not pending then return end
    pendingThrow[casterUuid] = nil
    if not pending.originalOwner then return end
    local item = Osi.GetItemByTemplateInInventory(pending.templateKey, casterUuid)
    if item then
        Osi.ToInventory(item, pending.originalOwner, 1, 0)
    end
end

local function pendingItemEntity(casterUuid, pending)
    local item = Osi.GetItemByTemplateInInventory(pending.templateKey, casterUuid)
    if not item then return nil, nil end
    return Ext.Entity.Get(item), uuidOf(item)
end

local function throwCastOf(casterUuid, spell, ignoredGuid)
    for _, entity in ipairs(Ext.Entity.GetAllEntitiesWithComponent("SpellCastState")) do
        local state = entity.SpellCastState
        local prototype = state.SpellId.Prototype
        if isThrowSpell(prototype) and uuidOf(state.Caster) == casterUuid
            and (spell == nil or prototype == spell)
            and (ignoredGuid == nil or tostring(state.SpellCastGuid) ~= ignoredGuid) then
            return entity
        end
    end
    return nil
end

local function isBaseTargetParam(request)
    local text = jsonText(safeRead(request, "Param"))
    return string.find(text, '"TargetProxy"', 1, true) ~= nil
        and string.find(text, "AddSourceBoundsToMargin", 1, true) == nil
end

local function clearTargetProxy(request)
    pcall(function()
        local param = request.Param
        param.TargetProxy = nil
        request.Param = param
    end)
end

local function appendItemPreview(previews, castGuid, itemEntity)
    local ok = pcall(function()
        previews[#previews + 1] = {
            SpellCastGuid = castGuid,
            field_18 = PREVIEW_TARGET_KIND,
            Param = { Target = itemEntity, TargetProxy = itemEntity },
        }
    end)
    if not ok then return nil end
    local appended = previews[#previews]
    if isBaseTargetParam(appended) then clearTargetProxy(appended) end
    return appended
end

local function appendTargetingStatePreview(previews, castGuid)
    pcall(function()
        previews[#previews + 1] = {
            SpellCastGuid = castGuid,
            field_18 = PREVIEW_TARGETING_STATE_KIND,
            Param = AIMING_TARGETING_STATE,
        }
    end)
end

local function retargetQueuedPreview(previews, castGuidText, itemEntity)
    for _, preview in ipairs(previews) do
        if tostring(preview.SpellCastGuid) == castGuidText then
            local ok = pcall(function()
                local param = preview.Param
                param.Target = itemEntity
                preview.Param = param
                preview.field_18 = PREVIEW_TARGET_KIND
            end)
            if ok then return preview end
        end
    end
    return nil
end

local function injectItemPreview(system, casterUuid, pending)
    local castEntity = throwCastOf(casterUuid, pending.spell)
    if not castEntity then return end
    local itemEntity, itemUuid = pendingItemEntity(casterUuid, pending)
    if not itemEntity then return end

    local state = castEntity.SpellCastState
    local castGuidText = tostring(state.SpellCastGuid)
    local previews = system[PREVIEW_QUEUE]
    pending.previewAttempts = (pending.previewAttempts or 0) + 1

    local injected = appendItemPreview(previews, state.SpellCastGuid, itemEntity)
    if uuidOf(safeRead(safeRead(injected, "Param"), "Target")) ~= itemUuid then
        injected = retargetQueuedPreview(previews, castGuidText, itemEntity)
    end

    local landed = injected and uuidOf(safeRead(safeRead(injected, "Param"), "Target"))
    if landed == itemUuid then
        pending.previewInjected = true
        appendTargetingStatePreview(previews, state.SpellCastGuid)
    end
end

local function onCastRequests()
    if not next(pendingThrow) then return end
    local system = Ext.System.ServerCastRequest
    if not system then return end
    for casterUuid, pending in pairs(pendingThrow) do
        if not pending.previewInjected and (pending.previewAttempts or 0) < PREVIEW_INJECT_ATTEMPTS then
            injectItemPreview(system, casterUuid, pending)
        end
    end
end

local function ensureCastRequestHook()
    if castRequestHookRegistered then return end
    castRequestHookRegistered = pcall(function()
        Ext.Entity.OnSystemUpdate("ServerCastRequest", onCastRequests)
    end)
end

local function sendAimItem(casterUuid, itemUuid)
    local userId = Osi.GetReservedUserID(casterUuid)
    if not userId then return end
    channel:SendToClient({ aimItem = itemUuid }, userId)
end

local function waitForItemInInventory(casterUuid, templateKey, attemptsLeft)
    local item = Osi.GetItemByTemplateInInventory(templateKey, casterUuid)
    if item then return sendAimItem(casterUuid, uuidOf(item)) end
    if attemptsLeft <= 0 then return end
    Ext.Timer.WaitFor(TRANSFER_POLL_MS, function()
        waitForItemInInventory(casterUuid, templateKey, attemptsLeft - 1)
    end)
end

local function prepareThrow(caster, spell)
    local info = itemInfo[keyBySpell[spell]]
    if not info then return end
    local casterUuid = uuidOf(caster)
    returnItem(casterUuid)
    ensureCastRequestHook()

    local originalOwner = nil
    local ownItem = Osi.GetItemByTemplateInInventory(info.originalKey, casterUuid)
    if not ownItem then
        local ownerItem = Osi.GetItemByTemplateInPartyInventory(info.originalKey, casterUuid)
        if not ownerItem then return forceRefresh(keyBySpell[spell]) end
        originalOwner = Osi.GetInventoryOwner(ownerItem)
        Osi.ToInventory(ownerItem, casterUuid, 1, 0)
    end

    pendingThrow[casterUuid] = { spell = spell, templateKey = info.originalKey, originalOwner = originalOwner }
    waitForItemInInventory(casterUuid, info.originalKey, TRANSFER_POLL_ATTEMPTS)
end

channel:SetRequestHandler(function()
    return labelPayload(itemInfo)
end)

channel:SetHandler(function(payload)
    if type(payload) ~= "table" or not payload.caster or not payload.spell then return end
    prepareThrow(payload.caster, payload.spell)
end)

Ext.Osiris.RegisterListener("CastedSpell", 5, "after", function(caster, spell)
    if isThrowSpell(spell) then pendingThrow[uuidOf(caster)] = nil end
end)

Ext.Entity.OnCreateDeferred("SpellCastState", function(entity)
    ensureCastRequestHook()
    local state = entity.SpellCastState
    if not state or not isThrowSpell(state.SpellId.Prototype) then return end

    local casterUuid = uuidOf(state.Caster)
    local pending = casterUuid and pendingThrow[casterUuid]
    if pending then
        local _, itemUuid = pendingItemEntity(casterUuid, pending)
        if itemUuid then sendAimItem(casterUuid, itemUuid) end
    end
end)

Ext.Entity.OnDestroy("SpellCastState", function(entity)
    local state = entity.SpellCastState
    if not state or not isThrowSpell(state.SpellId.Prototype) then return end
    local casterUuid = uuidOf(state.Caster)
    local pending = casterUuid and pendingThrow[casterUuid]
    if not pending or pending.spell ~= state.SpellId.Prototype then return end
    if throwCastOf(casterUuid, nil, tostring(state.SpellCastGuid)) then return end
    returnItem(casterUuid)
end)

Ext.Osiris.RegisterListener("TemplateAddedTo", 4, "after", function(template)
    scheduleRefresh(string.lower(template))
end)

Ext.Osiris.RegisterListener("TemplateRemovedFrom", 3, "after", function(template)
    scheduleRefresh(string.lower(template))
end)

Ext.Osiris.RegisterListener("TemplateUseFinished", 4, "after", function(_, template)
    scheduleRefresh(string.lower(template))
end)

Ext.Osiris.RegisterListener("CharacterJoinedParty", 1, "after", function(character)
    resync()
    if Party.IsPlayable(character) then setupCharacter(character) end
end)

Ext.Osiris.RegisterListener("CharacterLeftParty", 1, "after", function(character)
    grantedByCharacter[character] = nil
    strippedCharacters[character] = nil
    resync()
end)

Ext.Osiris.RegisterListener("LevelGameplayStarted", 2, "after", function()
    countByTemplate, pendingThrow, grantedByCharacter = {}, {}, {}
    strippedCharacters = {}
    appliedContainerSpells = nil
    resync()
    ensureCastRequestHook()
end)

Ext.Events.SessionLoaded:Subscribe(discoverItems)
