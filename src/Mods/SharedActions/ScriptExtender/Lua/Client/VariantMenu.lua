local POLL_MS = 100
local MAX_TOP_NODES = 2000
local REOPEN_STEP_MS = 16
local REOPEN_MAX_STEPS = 120
local REOPEN_CLOSED_FRAMES = 3
local REOPEN_CONFIRM_MS = 600
local SCROLL_MENU_HANDLE = "h366930b4g0002"
local SCROLL_CONTAINER = "SA_UseScroll"

local channel = Ext.Net.CreateChannel(ModuleUUID, "SharedActions_VariantMenu")

local menuWasOpen = false
local reopenPendingSince = nil
local reopenExecutedAt = nil
local variantCastActive = false

local function try(fn)
    local ok, value = pcall(fn)
    if ok then return value end
    return nil
end

local function findTopWidget(root, name)
    local queue, head = { root }, 1
    while head <= #queue and head <= MAX_TOP_NODES do
        local node = queue[head]
        head = head + 1
        local isWidget = tostring(try(function() return node.Type end)):find("UIWidget")
        if node ~= root and isWidget then
            if try(function() return node.Name end) == name then return node end
        else
            local count = try(function() return node.VisualChildrenCount end) or 0
            for index = 1, count do
                local child = try(function() return node:VisualChild(index) end)
                if child then queue[#queue + 1] = child end
            end
        end
    end
    return nil
end

local function hotBarContext()
    local root = try(function() return Ext.UI.GetRoot() end)
    local hotBar = root and findTopWidget(root, "HotBar")
    return hotBar and try(function() return hotBar.DataContext end)
end

local function prototypeOfSlot(slot)
    local content = try(function() return slot.Content end)
    return content and try(function() return content.PrototypeID end)
end

local function isScrollMenuOpen(context)
    local filter = try(function() return context.CurrentSingleHotbarFilter end)
    return tostring(filter):find(SCROLL_MENU_HANDLE) ~= nil
end

local function isVariantSpell(spell)
    return tostring(spell):find("_v%d%d$") ~= nil
end

local function menuShowsVariants()
    local stat = Ext.Stats.Get(SCROLL_CONTAINER, nil, false)
    local first = stat and tostring(stat.ContainerSpells):match("^[^;]+")
    return first ~= nil and isVariantSpell(first)
end

local function findMenuSlot(context)
    local bars = try(function() return context.CurrentPlayer.SelectedCharacter.PlayerCharacterProperties.KeyboardHotBars end)
    local barCount = bars and try(function() return #bars end) or 0
    for barIndex = 1, barCount do
        local slots = try(function() return bars[barIndex].SlotList end)
        local slotCount = slots and try(function() return #slots end) or 0
        for slotIndex = 1, slotCount do
            local slot = try(function() return slots[slotIndex] end)
            if slot and prototypeOfSlot(slot) == SCROLL_CONTAINER then return slot end
        end
    end
    return nil
end

local function clearReopen()
    reopenPendingSince, reopenExecutedAt = nil, nil
end

local function onMenuClosed()
    if reopenPendingSince or variantCastActive or not menuShowsVariants() then return end
    channel:SendToServer({ restore = true })
end

local function trackReopen(isOpen)
    if not reopenExecutedAt then return end
    if isOpen or Ext.Timer.MonotonicTime() - reopenExecutedAt > REOPEN_CONFIRM_MS then
        clearReopen()
    end
end

local function poll()
    local context = hotBarContext()
    if context then
        local isOpen = isScrollMenuOpen(context)
        trackReopen(isOpen)
        if menuWasOpen and not isOpen then onMenuClosed() end
        menuWasOpen = isOpen
    end
    Ext.Timer.WaitFor(POLL_MS, poll)
end

local function reopenWhenClosed(stepsLeft, closedFrames)
    local context = hotBarContext()
    local closedNow = context and not isScrollMenuOpen(context) and menuShowsVariants()
    closedFrames = closedNow and closedFrames + 1 or 0

    if closedFrames < REOPEN_CLOSED_FRAMES then
        if stepsLeft <= 0 then
            clearReopen()
            channel:SendToServer({ restore = true })
            return
        end
        return Ext.Timer.WaitFor(REOPEN_STEP_MS, function()
            reopenWhenClosed(stepsLeft - 1, closedFrames)
        end)
    end

    local slot = findMenuSlot(context)
    if not slot then
        clearReopen()
        return
    end
    pcall(function() context.UseSlotCommand:Execute(slot) end)
    reopenExecutedAt = Ext.Timer.MonotonicTime()
end

local function prototypeOf(entity)
    return try(function() return entity.ClientSpellCastState.Spell.Prototype end)
end

local function isPickerSpell(prototype)
    if not prototype or not tostring(prototype):find("^SA_Scroll_") or isVariantSpell(prototype) then
        return false
    end
    local stat = Ext.Stats.Get(prototype, nil, false)
    return stat ~= nil and (stat.UseCosts == nil or stat.UseCosts == "")
end

Ext.Entity.OnCreateDeferred("ClientSpellCastState", function(entity)
    local prototype = prototypeOf(entity)
    if isVariantSpell(prototype) then
        variantCastActive = true
    elseif isPickerSpell(prototype) then
        reopenPendingSince, reopenExecutedAt = Ext.Timer.MonotonicTime(), nil
    end
end)

Ext.Entity.OnDestroy("ClientSpellCastState", function(entity)
    local prototype = prototypeOf(entity)
    if isVariantSpell(prototype) then variantCastActive = false end
    if isPickerSpell(prototype) and reopenPendingSince then
        reopenWhenClosed(REOPEN_MAX_STEPS, 0)
    end
end)

Ext.Events.SessionLoaded:Subscribe(function()
    Ext.Timer.WaitFor(POLL_MS, poll)
end)
