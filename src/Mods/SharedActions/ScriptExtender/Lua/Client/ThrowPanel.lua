local ICON_SIZE = { 48, 48 }
local COLUMNS = 8
local THROW_TARGETING_TYPE = "Throw"
local AIMING_STATE = 2
local AIM_OPTIONS = { "IsPreview", "Forced", "ShowPrepareAnimation" }

local channel = Ext.Net.CreateChannel(ModuleUUID, "SharedActions_ThrowPanel")

local function log(...)
    print("[SharedActions]", ...)
end

local items = {}
local aimingCast = nil
local window = nil
local originalFlags = nil

local function uuidOf(value)
    if value == nil then return nil end
    if type(value) == "string" then return string.sub(value, -36) end
    local ok, uuid = pcall(function() return value.Uuid.EntityUuid end)
    if ok then return uuid end
    return nil
end

local function nameOf(entry)
    local nameHandle = entry[3]
    if nameHandle == "" then return "?" end
    return Ext.Loca.GetTranslatedString(nameHandle) or "?"
end

local function descriptionOf(entry)
    local descHandle = entry[4]
    if descHandle == "" then return "" end
    return Ext.Loca.GetTranslatedString(descHandle) or ""
end

local function sortedKeys()
    local keys = {}
    for key in pairs(items) do keys[#keys + 1] = key end
    table.sort(keys)
    return keys
end

local function closeWindow()
    if window then window.Open = false end
end

local function isPanelCast(entity)
    local ok, prototype = pcall(function() return entity.ClientSpellCastState.Spell.Prototype end)
    return ok and prototype == Catalog.ThrowPanelSpell
end

local function flagsList(stat)
    local ok, list = pcall(function() return Ext.Json.Parse(Ext.Json.Stringify(stat.SpellFlags)) end)
    if ok and type(list) == "table" then return list end
    return nil
end

local function applyStrip()
    local stat = Ext.Stats.Get(Catalog.ThrowPanelSpell)
    if not stat then return log("ALERTA: stat do painel de arremesso nao encontrada no cliente") end
    local current = flagsList(stat)
    if not current then return end
    if not originalFlags then originalFlags = current end

    local flags = {}
    for _, flag in ipairs(originalFlags) do
        if flag ~= "InventorySelection" then flags[#flags + 1] = flag end
    end
    pcall(function() stat.SpellFlags = flags end)
    pcall(function() stat:Sync() end)
end

local function aimWithItem(itemUuid)
    if not aimingCast then return log("ALERTA: a mira fechou antes de o item chegar") end
    local state, targeting = aimingCast.ClientSpellCastState, aimingCast.ClientSpellCastTargeting
    if not state or not targeting then return log("ALERTA: mira sem estado de targeting") end

    local itemEntity = Ext.Entity.Get(itemUuid)
    pcall(function()
        targeting.Targets[1] = { TargetingType = THROW_TARGETING_TYPE, Target2 = { Target = itemEntity } }
    end)
    pcall(function() targeting.CurrentTargetIndex = 0 end)
    pcall(function() targeting.SpellTargetingState = AIMING_STATE end)
    pcall(function() state.CastOptions = AIM_OPTIONS end)
end

local function chooseItem(key)
    if not aimingCast then return end
    local caster = uuidOf(aimingCast.ClientSpellCastState.Caster)
    closeWindow()
    channel:SendToServer({ caster = caster, template = key })
end

local function clearWindow()
    local children = {}
    for _, child in ipairs(window.Children) do
        children[#children + 1] = child
    end
    for _, child in ipairs(children) do
        window:RemoveChild(child)
    end
end

local function rebuildWindow()
    if not window then return end
    clearWindow()

    local index = 0
    for _, key in ipairs(sortedKeys()) do
        local entry = items[key]
        local count, icon = entry[1], entry[5]

        local button = window:AddImageButton(key, icon, ICON_SIZE)
        if index % COLUMNS ~= 0 then button.SameLine = true end
        index = index + 1
        button.OnClick = function() chooseItem(key) end

        local tooltip = button:Tooltip()
        tooltip:AddText(nameOf(entry) .. " (" .. count .. ")")
        local description = descriptionOf(entry)
        if description ~= "" then tooltip:AddText(description) end
    end
end

local function ensureWindow()
    if window then return window end
    window = Ext.IMGUI.NewWindow("Arremessar")
    window.Closeable = true
    return window
end

channel:SetHandler(function(payload)
    if type(payload) ~= "table" then return end
    if payload.aimItem then return aimWithItem(payload.aimItem) end
    if type(payload.items) ~= "table" then return end
    items = payload.items
    rebuildWindow()
end)

Ext.Events.SessionLoaded:Subscribe(applyStrip)

Ext.Entity.OnCreateDeferred("ClientSpellCastState", function(entity)
    if not isPanelCast(entity) then return end
    aimingCast = entity
    channel:RequestToServer({}, function(reply)
        if type(reply) == "table" and type(reply.items) == "table" then items = reply.items end
        ensureWindow().Open = true
        rebuildWindow()
    end)
end)

Ext.Entity.OnDestroy("ClientSpellCastState", function(entity)
    if not isPanelCast(entity) then return end
    aimingCast = nil
    closeWindow()
end)
