Tooltip = {}

local SPELL_TOOLTIP_FIELDS = {
    "Description", "DescriptionParams", "ExtraDescription", "ExtraDescriptionParams",
    "ShortDescription", "ShortDescriptionParams", "TooltipDamageList", "TooltipAttackSave",
    "TooltipStatusApply", "TooltipOnMiss", "TooltipOnSave", "TooltipPermanentWarnings",
    "TooltipUpcastDescription", "TooltipUpcastDescriptionParams",
}
local SPELL_HEADER_FIELDS = { "Level", "SpellSchool" }
local UNKNOWN_HANDLE = "ls::TranslatedStringRepository::s_HandleUnknown"

local function copyFields(target, source, fields)
    for _, field in ipairs(fields) do
        local value = source[field]
        if value ~= nil then pcall(function() target[field] = value end) end
    end
end

function Tooltip.TranslatedHandle(translatedString)
    if not translatedString then return nil end
    local handle = translatedString.Handle and translatedString.Handle.Handle
    if not handle or handle == "" or handle == UNKNOWN_HANDLE then return nil end
    return handle
end

local translatedHandle = Tooltip.TranslatedHandle

function Tooltip.HasDescription(spellName)
    local stat = spellName and spellName ~= "" and Ext.Stats.Get(spellName, nil, false)
    return stat ~= nil and stat ~= false and stat.Description ~= nil and stat.Description ~= ""
end

function Tooltip.CopySpellText(target, sourceSpell)
    local source = Ext.Stats.Get(sourceSpell, nil, false)
    if not source then return false end
    copyFields(target, source, SPELL_TOOLTIP_FIELDS)
    return true
end

function Tooltip.CopySpellHeader(target, sourceSpell)
    local source = Ext.Stats.Get(sourceSpell, nil, false)
    if source then copyFields(target, source, SPELL_HEADER_FIELDS) end
end

function Tooltip.ApplyItemText(target, template)
    local description = translatedHandle(template.TechnicalDescription)
    local params = template.TechnicalDescriptionParams
    if not description then
        description = translatedHandle(template.Description)
        params = nil
    end
    if not description then return end
    target.Description = description .. ";1"
    target.DescriptionParams = params or ""
end
