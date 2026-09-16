local channel = Ext.Net.CreateChannel(ModuleUUID, "SharedActions_Labels")

local function log(...)
    print("[SharedActions]", ...)
end

local function applyLabels(payload)
    for spell, entry in pairs(payload) do
        local count, ownHandle, vanillaHandle, variantHandle = entry[1], entry[2], entry[3], entry[4]
        local baseName = vanillaHandle ~= "" and Ext.Loca.GetTranslatedString(vanillaHandle)

        if not baseName or baseName == "" then
            baseName = Ext.Loca.GetTranslatedString(ownHandle)
            log("sem nome do jogo:", spell, "handle:", vanillaHandle)
        end

        if baseName and baseName ~= "" then
            if variantHandle and variantHandle ~= "" then
                local variantName = Ext.Loca.GetTranslatedString(variantHandle)
                if variantName and variantName ~= "" then
                    baseName = baseName .. " — " .. variantName
                end
            end
            Ext.Loca.UpdateTranslatedString(ownHandle, baseName .. " (" .. count .. ")")
        end
    end
end

channel:SetHandler(function(payload)
    if type(payload) == "table" then applyLabels(payload) end
end)

Ext.Events.SessionLoaded:Subscribe(function()
    channel:RequestToServer({}, function(payload)
        if type(payload) == "table" then applyLabels(payload) end
    end)
end)
