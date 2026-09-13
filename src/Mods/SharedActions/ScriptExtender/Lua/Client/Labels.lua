local channel = Ext.Net.CreateChannel(ModuleUUID, "SharedActions_Labels")

local function log(...)
    print("[SharedActions]", ...)
end

local function applyLabels(payload)
    local applied = 0
    for spell, entry in pairs(payload) do
        local count, ownHandle, vanillaHandle = entry[1], entry[2], entry[3]
        local baseName = vanillaHandle ~= "" and Ext.Loca.GetTranslatedString(vanillaHandle)

        if not baseName or baseName == "" then
            baseName = Ext.Loca.GetTranslatedString(ownHandle)
            log("sem nome do jogo:", spell, "handle:", vanillaHandle)
        end

        if baseName and baseName ~= "" then
            Ext.Loca.UpdateTranslatedString(ownHandle, baseName .. " (" .. count .. ")")
            applied = applied + 1
        end
    end
    return applied
end

channel:SetHandler(function(payload)
    if type(payload) == "table" then applyLabels(payload) end
end)

Ext.Events.SessionLoaded:Subscribe(function()
    channel:RequestToServer({}, function(payload)
        if type(payload) == "table" then
            log("rotulos aplicados:", applyLabels(payload))
        end
    end)
end)
