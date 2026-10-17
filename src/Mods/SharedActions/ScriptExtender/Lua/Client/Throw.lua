local SPELL_PREFIX = "SA_Throwable_"
local STRIPPED_FLAG = "InventorySelection"
local THROW_TARGETING_TYPE = "Throw"
local AIMING_STATE = 2
local AIM_OPTIONS = { "IsPreview", "Forced", "ShowPrepareAnimation" }

local channel = Ext.Net.CreateChannel(ModuleUUID, "SharedActions_Throw")

local aimingCast = nil

local function uuidOf(value)
    if value == nil then return nil end
    if type(value) == "string" then return string.sub(value, -36) end
    local ok, uuid = pcall(function() return value.Uuid.EntityUuid end)
    if ok then return uuid end
    return nil
end

local function isThrowSpell(prototype)
    return type(prototype) == "string" and prototype:sub(1, #SPELL_PREFIX) == SPELL_PREFIX
end

local function prototypeOf(entity)
    local ok, prototype = pcall(function() return entity.ClientSpellCastState.Spell.Prototype end)
    if ok then return prototype end
    return nil
end

local function sameEntity(a, b)
    if a == nil or b == nil then return false end
    if rawequal(a, b) then return true end
    local ok, same = pcall(function() return a:GetHandle() == b:GetHandle() end)
    return ok and same
end

local function flagsList(stat)
    local ok, list = pcall(function() return Ext.Json.Parse(Ext.Json.Stringify(stat.SpellFlags)) end)
    if ok and type(list) == "table" then return list end
    return nil
end

local function stripInventorySelection(spell)
    local stat = Ext.Stats.Get(spell, nil, false)
    local current = stat and flagsList(stat)
    if not current then return end

    local flags = {}
    for _, flag in ipairs(current) do
        if flag ~= STRIPPED_FLAG then flags[#flags + 1] = flag end
    end
    if #flags == #current then return end
    pcall(function()
        stat.SpellFlags = flags
        stat:Sync()
    end)
end

local function applyItems(payload)
    if type(payload) ~= "table" then return end
    for spell, entry in pairs(payload) do
        stripInventorySelection(spell)
        local count, ownHandle, nameHandle = entry[1], entry[2], entry[3]
        local name = nameHandle ~= "" and Ext.Loca.GetTranslatedString(nameHandle) or ""
        if name ~= "" then Ext.Loca.UpdateTranslatedString(ownHandle, name .. " (" .. count .. ")") end
    end
end

local function aimWithItem(itemUuid)
    if not aimingCast then return end
    local state, targeting = aimingCast.ClientSpellCastState, aimingCast.ClientSpellCastTargeting
    if not state or not targeting then return end

    local itemEntity = Ext.Entity.Get(itemUuid)
    pcall(function()
        targeting.Targets[1] = { TargetingType = THROW_TARGETING_TYPE, Target2 = { Target = itemEntity } }
    end)
    pcall(function() targeting.CurrentTargetIndex = 0 end)
    pcall(function() targeting.SpellTargetingState = AIMING_STATE end)
    pcall(function() state.CastOptions = AIM_OPTIONS end)
end

channel:SetHandler(function(payload)
    if type(payload) == "table" and payload.aimItem then return aimWithItem(payload.aimItem) end
    applyItems(payload)
end)

Ext.Events.SessionLoaded:Subscribe(function()
    channel:RequestToServer({}, applyItems)
end)

Ext.Entity.OnCreateDeferred("ClientSpellCastState", function(entity)
    local prototype = prototypeOf(entity)
    if not isThrowSpell(prototype) then return end
    aimingCast = entity
    channel:SendToServer({ caster = uuidOf(entity.ClientSpellCastState.Caster), spell = prototype })
end)

Ext.Entity.OnDestroy("ClientSpellCastState", function(entity)
    if sameEntity(entity, aimingCast) then aimingCast = nil end
end)
