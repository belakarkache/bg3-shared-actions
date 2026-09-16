local Catalog = Catalog

local HANDLE_FORMAT = "h%08xg%04xg%04xg%04xg%012x"
local HANDLE_OFFSET = 500000
local TRANSFER_POLL_MS = 100
local TRANSFER_POLL_ATTEMPTS = 20
local PREVIEW_TARGET_KIND = 5
local PREVIEW_TARGETING_STATE_KIND = 0
local AIMING_TARGETING_STATE = 2
local PREVIEW_INJECT_ATTEMPTS = 30
local PREVIEW_QUEUE = "NetworkPreviewUpdateRequests"

local channel = Ext.Net.CreateChannel(ModuleUUID, "SharedActions_ThrowPanel")

local itemInfo = {}
local countByTemplate = {}
local pendingThrow = {}
local grantedPanelSpell = {}
local castRequestHookRegistered = false

local function log(...)
    print("[SharedActions]", ...)
end

local function isPanelSpell(prototype)
    return prototype == Catalog.ThrowPanelSpell
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

local function partyMembers()
    local members = {}
    for _, row in ipairs(Osi.DB_Players:Get(nil) or {}) do
        members[#members + 1] = row[1]
    end
    return members
end

local function handleFor(index)
    local value = HANDLE_OFFSET + index
    return string.format(HANDLE_FORMAT, value, value % 0x10000, 0, 0, value)
end

local function translatedHandle(translatedString)
    if not translatedString then return nil end
    local handle = translatedString.Handle and translatedString.Handle.Handle
    if not handle or handle == "" then return nil end
    return handle
end

local function discoverItems()
    local templates = Ext.Template.GetAllRootTemplates()
    if not templates then return log("ALERTA: GetAllRootTemplates devolveu nil") end

    local index = 0
    for guid in pairs(Catalog.ThrowableTemplates) do
        local template = templates[guid]
        if template then
            index = index + 1
            local description = translatedHandle(template.TechnicalDescription)
                or translatedHandle(template.Description)
            local key = string.lower(template.Name .. "_" .. template.Id)
            itemInfo[key] = {
                originalKey = template.Name .. "_" .. template.Id,
                handle = handleFor(index),
                nameHandle = translatedHandle(template.DisplayName),
                descHandle = description,
                icon = template.Icon,
            }
        end
    end

    log("painel de arremesso:", index, "itens com metadados")
end

local function countInParty(key, queryAnchor)
    return Osi.TemplateIsInPartyInventory(key, queryAnchor, 0) or 0
end

local function itemPayload()
    local payload = {}
    for key, info in pairs(itemInfo) do
        local count = countByTemplate[key] or 0
        if count > 0 then
            payload[key] = { count, info.handle, info.nameHandle or "", info.descHandle or "",
                             info.icon or "" }
        end
    end
    return payload
end

local function pushSnapshot()
    channel:Broadcast({ items = itemPayload() })
end

local function ensurePanelGranted(character)
    if grantedPanelSpell[character] then return end
    Osi.AddSpell(character, Catalog.ThrowPanelSpell, 0, 0)
    grantedPanelSpell[character] = true
end

local function resync()
    local members = partyMembers()
    if #members == 0 then return end
    local queryAnchor = members[1]

    for _, character in ipairs(members) do
        ensurePanelGranted(character)
    end

    local changed = false
    for key in pairs(itemInfo) do
        local count = countInParty(key, queryAnchor)
        if countByTemplate[key] ~= count then
            countByTemplate[key] = count
            changed = true
        end
    end
    if changed then pushSnapshot() end
end

local function refreshTemplate(key)
    if not itemInfo[key] then return end
    local members = partyMembers()
    if #members == 0 then return end
    local count = countInParty(key, members[1])
    if countByTemplate[key] ~= count then
        countByTemplate[key] = count
        pushSnapshot()
    end
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

local function panelCastOf(casterUuid)
    for _, entity in ipairs(Ext.Entity.GetAllEntitiesWithComponent("SpellCastState")) do
        local state = entity.SpellCastState
        if isPanelSpell(state.SpellId.Prototype) and uuidOf(state.Caster) == casterUuid then
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
    local castEntity = panelCastOf(casterUuid)
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
    if not userId then return log("ALERTA: sem UserID reservado para", casterUuid) end
    channel:SendToClient({ aimItem = itemUuid }, userId)
end

local function waitForItemInInventory(casterUuid, templateKey, attemptsLeft)
    local item = Osi.GetItemByTemplateInInventory(templateKey, casterUuid)
    if item then return sendAimItem(casterUuid, uuidOf(item)) end
    if attemptsLeft <= 0 then return log("ALERTA: item nao chegou ao inventario de quem arremessa:", templateKey) end
    Ext.Timer.WaitFor(TRANSFER_POLL_MS, function()
        waitForItemInInventory(casterUuid, templateKey, attemptsLeft - 1)
    end)
end

local function prepareThrow(caster, key)
    local info = itemInfo[key]
    if not info then return log("ALERTA: item desconhecido no pedido de arremesso:", key) end
    local casterUuid = uuidOf(caster)
    returnItem(casterUuid)
    ensureCastRequestHook()

    local originalOwner = nil
    local ownItem = Osi.GetItemByTemplateInInventory(info.originalKey, casterUuid)
    if not ownItem then
        local ownerItem = Osi.GetItemByTemplateInPartyInventory(info.originalKey, casterUuid)
        if not ownerItem then return log("ALERTA: item nao achado na party:", key) end
        originalOwner = Osi.GetInventoryOwner(ownerItem)
        Osi.ToInventory(ownerItem, casterUuid, 1, 0)
    end

    pendingThrow[casterUuid] = { templateKey = info.originalKey, originalOwner = originalOwner }
    waitForItemInInventory(casterUuid, info.originalKey, TRANSFER_POLL_ATTEMPTS)
end

channel:SetRequestHandler(function()
    return { items = itemPayload() }
end)

channel:SetHandler(function(payload)
    if type(payload) ~= "table" or not payload.caster or not payload.template then return end
    prepareThrow(payload.caster, payload.template)
end)

Ext.Osiris.RegisterListener("CastedSpell", 5, "after", function(caster, spell)
    if isPanelSpell(spell) then pendingThrow[uuidOf(caster)] = nil end
end)

Ext.Entity.OnCreateDeferred("SpellCastState", function(entity)
    ensureCastRequestHook()
    local state = entity.SpellCastState
    if not state or not isPanelSpell(state.SpellId.Prototype) then return end

    local casterUuid = uuidOf(state.Caster)
    local pending = casterUuid and pendingThrow[casterUuid]
    if pending then
        local _, itemUuid = pendingItemEntity(casterUuid, pending)
        if itemUuid then sendAimItem(casterUuid, itemUuid) end
    end
end)

Ext.Entity.OnDestroy("SpellCastState", function(entity)
    local state = entity.SpellCastState
    if not state or not isPanelSpell(state.SpellId.Prototype) then return end
    local casterUuid = uuidOf(state.Caster)
    if casterUuid then returnItem(casterUuid) end
end)

Ext.Osiris.RegisterListener("TemplateAddedTo", 4, "after", function(template)
    refreshTemplate(string.lower(template))
end)

Ext.Osiris.RegisterListener("TemplateRemovedFrom", 3, "after", function(template)
    refreshTemplate(string.lower(template))
end)

Ext.Osiris.RegisterListener("CharacterJoinedParty", 1, "after", function(character)
    resync()
    ensurePanelGranted(character)
end)
Ext.Osiris.RegisterListener("CharacterLeftParty", 1, "after", function(character)
    grantedPanelSpell[character] = nil
    resync()
end)

Ext.Osiris.RegisterListener("LevelGameplayStarted", 2, "after", function()
    countByTemplate, pendingThrow, grantedPanelSpell = {}, {}, {}
    resync()
    ensureCastRequestHook()
end)

Ext.Events.SessionLoaded:Subscribe(discoverItems)
