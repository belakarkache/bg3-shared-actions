local Catalog = Catalog

local MAX_FAMILY_DEPTH = 12
local RETIRED_SPELLS = { "SA_PotionProbe_OBJ_Potion_Healing", "SA_Dig", "SA_ThrowItem",
                         "SA_OpenThrowPanel", "SA_ThrowProbe" }
local AREA_FIELDS = { "AreaRadius", "ExplodeRadius" }

local categoriesByUseType = {}
for _, category in ipairs(Catalog.Categories) do
    for useType in pairs(category.useTypes) do
        local sharing = categoriesByUseType[useType] or {}
        sharing[#sharing + 1] = category
        categoriesByUseType[useType] = sharing
    end
end

local function baseFamily(templates, id)
    local depth = 0
    while id and depth < MAX_FAMILY_DEPTH do
        local template = templates[id]
        if not template then return nil end
        local name = template.Name or ""
        if name:sub(1, 5) == "BASE_" then return name end
        id = template.ParentTemplateId
        depth = depth + 1
    end
    return nil
end

local function existingSpell(name)
    if not name or name == "" then return nil end
    if not Ext.Stats.Get(name, nil, false) then return nil end
    return name
end

local function itemSpellOf(template)
    local found = nil
    for _, action in ipairs(template.OnUsePeaceActions or {}) do
        if action.Type == "UseSpell" and action.Spell and action.Spell ~= "" then
            found = action.Spell
        end
    end
    return existingSpell(found)
end

local function containerVariantsOf(name)
    local stat = Ext.Stats.Get(name, nil, false)
    if not stat or not stat.ContainerSpells or stat.ContainerSpells == "" then return nil end
    local variants = {}
    for variant in stat.ContainerSpells:gmatch("[^;]+") do
        variants[#variants + 1] = variant
    end
    return variants
end

local function parentSpellOf(category, stat, template)
    if category.inheritsItemSpell then return itemSpellOf(template) end
    return Catalog.BaseEntry
end

local translatedHandle = Tooltip.TranslatedHandle

local function iconFor(statName, template)
    local key = "SA_Icon_" .. statName
    if Catalog.IconKeys[key] then return key end
    return template.Icon
end

local function spellNameFor(category, statName)
    return category.prefix .. statName .. "_" .. #statName
end

local function subSpellFields(category, statName, stat, template, parent, handle, icon)
    local parentStat = Ext.Stats.Get(parent, nil, false)
    local fields = {
        SpellContainerID = category.container,
        ContainerSpells = "",
        Icon = (icon and icon ~= "") and icon or iconFor(statName, template),
        UseCosts = category.forcedUseCosts or stat.UseCosts,
        DisplayName = handle .. ";1",
    }

    if not parentStat or not parentStat.Description or parentStat.Description == "" then
        Tooltip.ApplyItemText(fields, template)
    end

    for _, field in ipairs(AREA_FIELDS) do
        local inherited = parentStat and parentStat[field]
        if inherited and inherited ~= "" then fields[field] = inherited end
    end

    for field, value in pairs(category.overrides) do
        fields[field] = value
    end
    return fields
end

local function linkToTemplate(category, template, spell)
    local templateKey = template.Name .. "_" .. template.Id
    local key = string.lower(templateKey)
    local sharing = Catalog.TemplateToSpell[key] or {}
    sharing[#sharing + 1] = spell
    Catalog.TemplateToSpell[key] = sharing
    Catalog.SpellToTemplate[spell] = templateKey
    Catalog.SpellContainer[spell] = category.container
end

local function registerSingle(category, statName, stat, template, parent)
    local name = spellNameFor(category, statName)
    local handle = Spells.HandleFor(name)
    local fields = subSpellFields(category, statName, stat, template, parent, handle)
    if not Spells.Define(name, parent, fields) then return 0 end

    linkToTemplate(category, template, name)
    Catalog.Labels[name] = { handle, translatedHandle(template.DisplayName) or "" }
    return 1
end

local function requirementFor(useCosts)
    local conditions = {}
    for resource, amount in tostring(useCosts or ""):gmatch("([%a_]+):(%d+)") do
        conditions[#conditions + 1] = string.format("HasActionResource('%s', %s, 0, false)", resource, amount)
    end
    return table.concat(conditions, " and ")
end

local function existingVariants(variants)
    local existing = {}
    for variantIndex, variantSpell in ipairs(variants) do
        local variantStat = Ext.Stats.Get(variantSpell, nil, false)
        if variantStat then
            existing[#existing + 1] = { index = variantIndex, spell = variantSpell, stat = variantStat }
        end
    end
    return existing
end

local function defineVariantLeaf(category, statName, stat, template, container, picker, variant)
    local leafName = string.format("%s_v%02d", picker, variant.index)
    local leafHandle = Spells.HandleFor(leafName)
    local fields = subSpellFields(category, statName, stat, template, variant.spell, leafHandle, variant.stat.Icon)
    if not Tooltip.HasDescription(variant.spell) and Tooltip.HasDescription(container) then
        Tooltip.CopySpellText(fields, container)
    end
    if not Spells.Define(leafName, variant.spell, fields) then return nil end

    Catalog.VariantGroupOf[leafName] = picker
    Catalog.Labels[leafName] = { leafHandle, translatedHandle(template.DisplayName) or "",
                                 translatedHandle(variant.stat.DisplayName) or "" }
    linkToTemplate(category, template, leafName)
    return leafName
end

local function definePicker(category, statName, stat, template, container, picker)
    local fields = subSpellFields(category, statName, stat, template, Catalog.BaseEntry, Spells.HandleFor(picker))
    fields.RequirementConditions = requirementFor(category.forcedUseCosts or stat.UseCosts)
    fields.UseCosts = ""
    if Tooltip.HasDescription(container) then
        Tooltip.CopySpellText(fields, container)
        Tooltip.CopySpellHeader(fields, container)
    end
    return Spells.Define(picker, Catalog.BaseEntry, fields)
end

local function registerWithVariants(category, statName, stat, template, container, variants)
    local variantsWithStats = existingVariants(variants)
    if #variantsWithStats == 0 then return 0 end

    local picker = spellNameFor(category, statName)
    local pickerInPak = definePicker(category, statName, stat, template, container, picker)

    local leaves = {}
    for _, variant in ipairs(variantsWithStats) do
        local leafName = defineVariantLeaf(category, statName, stat, template, container, picker, variant)
        if leafName then leaves[#leaves + 1] = leafName end
    end

    if not pickerInPak or #leaves == 0 then return 0 end

    Catalog.ScrollVariants[picker] = leaves
    Catalog.Labels[picker] = { Spells.HandleFor(picker), translatedHandle(template.DisplayName) or "" }
    linkToTemplate(category, template, picker)
    return 1 + #leaves
end

local function register(category, statName, stat, template)
    local parent = parentSpellOf(category, stat, template)
    if not parent then return 0 end

    local variants = containerVariantsOf(parent)
    local registered = variants
        and registerWithVariants(category, statName, stat, template, parent, variants)
        or registerSingle(category, statName, stat, template, parent)

    if registered > 0 then
        Catalog.LegacySpells[#Catalog.LegacySpells + 1] = category.prefix .. statName
    end
    return registered
end

local function accepts(category, stat, family)
    if not category.forcedUseCosts and (not stat.UseCosts or stat.UseCosts == "") then
        return false
    end
    if next(category.families) == nil then return true end
    return family ~= nil and category.families[family] == true
end

local function discover()
    local templates = Ext.Template.GetAllRootTemplates()
    if not templates then return end

    for _, statName in ipairs(Ext.Stats.GetStats("Object") or {}) do
        local stat = Ext.Stats.Get(statName, nil, false)
        local sharing = stat and categoriesByUseType[stat.ItemUseType]
        local template = sharing and statName:sub(1, 1) ~= "_" and stat.RootTemplate and templates[stat.RootTemplate]

        if template then
            local family = baseFamily(templates, template.Id)
            for _, category in ipairs(sharing) do
                if accepts(category, stat, family) then
                    register(category, statName, stat, template)
                end
            end
        end
    end

    for _, spell in ipairs(RETIRED_SPELLS) do
        Catalog.LegacySpells[#Catalog.LegacySpells + 1] = spell
    end
end

Ext.Events.SessionLoaded:Subscribe(discover)
