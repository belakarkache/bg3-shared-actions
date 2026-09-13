local Labels = Catalog.Labels

local channel = Ext.Net.CreateChannel(ModuleUUID, "SharedActions_Labels")

local function log(...)
    print("[SharedActions]", ...)
end

local function applyCounts(counts)
    for spell, count in pairs(counts) do
        local handles = Labels[spell]
        if handles then
            local ownHandle, vanillaHandle = handles[1], handles[2]
            local baseName = Ext.Loca.GetTranslatedString(vanillaHandle)

            if not baseName or baseName == "" then
                baseName = Ext.Loca.GetTranslatedString(ownHandle)
                log("sem nome do jogo:", spell, "handle:", vanillaHandle)
            end

            if baseName and baseName ~= "" then
                Ext.Loca.UpdateTranslatedString(ownHandle, baseName .. " (" .. count .. ")")
            end
        end
    end
end

channel:SetHandler(function(counts)
    if type(counts) == "table" then applyCounts(counts) end
end)

Ext.Events.SessionLoaded:Subscribe(function()
    channel:RequestToServer({}, function(reply)
        if type(reply) == "table" then applyCounts(reply) end
    end)
end)
