local Catalog = Catalog

local MAX_FAMILY_DEPTH = 12
local RETIRED_SPELLS = { "SA_PotionProbe_OBJ_Potion_Healing", "SA_Dig", "SA_ThrowItem",
                         "SA_OpenThrowPanel", "SA_ThrowProbe" }
local AREA_FIELDS = { "AreaRadius", "ExplodeRadius" }
local HANDLE_FORMAT = "h%08xg%04xg%04xg%04xg%012x"

local categoriesByUseType = {}
for _, category in ipairs(Catalog.Categories) do
    for useType in pairs(category.useTypes) do
        local sharing = categoriesByUseType[useType] or {}
        sharing[#sharing + 1] = category
        categoriesByUseType[useType] = sharing
    end
end

local function log(...)
    print("[SharedActions]", ...)
end

local function handleFor(index)
    return string.format(HANDLE_FORMAT, index, index % 0x10000, 0, 0, index)
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

local function translatedHandle(translatedString)
    if not translatedString then return nil end
    local handle = translatedString.Handle and translatedString.Handle.Handle
    if not handle or handle == "" then return nil end
    return handle
end

local function iconFor(statName, template)
    local key = "SA_Icon_" .. statName
    if Catalog.IconKeys[key] then return key end
    return template.Icon
end

local function spellNameFor(category, statName)
    return category.prefix .. statName .. "_" .. #statName
end

local function createSubSpell(spell, category, statName, stat, template, parent, handle, icon)
    if Ext.Stats.Get(spell, nil, false) then return spell end

    local created = Ext.Stats.Create(spell, "SpellData", parent)
    if not created then
        log("ALERTA: Create falhou para", spell, "| parent:", parent)
        return nil
    end

    created.SpellContainerID = category.container
    created.ContainerSpells = ""
    created.Icon = (icon and icon ~= "") and icon or iconFor(statName, template)
    created.UseCosts = category.forcedUseCosts or stat.UseCosts
    created.DisplayName = handle .. ";1"

    if not created.Description or created.Description == "" then
        Tooltip.ApplyItemText(created, template)
    end

    local parentStat = Ext.Stats.Get(parent, nil, false)
    for _, field in ipairs(AREA_FIELDS) do
        local inherited = parentStat and parentStat[field]
        if inherited and inherited ~= "" then
            if created[field] ~= inherited then
                log("raio nao herdado:", spell, field, tostring(created[field]),
                    "| pai", parent, tostring(inherited))
            end
            created[field] = inherited
        end
    end

    for field, value in pairs(category.overrides) do
        created[field] = value
    end

    created:Sync()
    return spell
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

local function registerSingle(category, statName, stat, template, parent, nextIndex)
    local name = spellNameFor(category, statName)
    local handle = handleFor(nextIndex())
    if not createSubSpell(name, category, statName, stat, template, parent, handle) then
        return 0
    end

    linkToTemplate(category, template, name)
    Catalog.Labels[name] = { handle, translatedHandle(template.DisplayName) or "" }
    return 1
end

local function registerWithVariants(category, statName, stat, template, container, variants, nextIndex)
    local pickerHandle = handleFor(nextIndex())
    local picker = spellNameFor(category, statName)

    local leaves = {}
    for variantIndex, variantSpell in ipairs(variants) do
        if Ext.Stats.Get(variantSpell, nil, false) then
            local leafName = string.format("%s_v%02d", picker, variantIndex)
            local leafHandle = handleFor(nextIndex())
            local variantStat = Ext.Stats.Get(variantSpell, nil, false)
            if createSubSpell(leafName, category, statName, stat, template, variantSpell, leafHandle,
                              variantStat.Icon) then
                if not Tooltip.HasDescription(variantSpell) and Tooltip.HasDescription(container) then
                    local leafStat = Ext.Stats.Get(leafName, nil, false)
                    Tooltip.CopySpellText(leafStat, container)
                    leafStat:Sync()
                end
                leaves[#leaves + 1] = leafName
                Catalog.VariantGroupOf[leafName] = picker
                Catalog.Labels[leafName] = { leafHandle, translatedHandle(template.DisplayName) or "",
                                             translatedHandle(variantStat.DisplayName) or "" }
                linkToTemplate(category, template, leafName)
            end
        end
    end

    if #leaves == 0 then return 0 end

    if not createSubSpell(picker, category, statName, stat, template, Catalog.BaseEntry, pickerHandle) then
        return 0
    end
    local pickerStat = Ext.Stats.Get(picker, nil, false)
    pickerStat.UseCosts = ""
    if Tooltip.HasDescription(container) then
        Tooltip.CopySpellText(pickerStat, container)
        Tooltip.CopySpellHeader(pickerStat, container)
    end
    pickerStat:Sync()

    Catalog.ScrollVariants[picker] = leaves
    Catalog.Labels[picker] = { pickerHandle, translatedHandle(template.DisplayName) or "" }
    linkToTemplate(category, template, picker)
    return 1 + #leaves
end

local function register(category, statName, stat, template, nextIndex)
    local parent = parentSpellOf(category, stat, template)
    if not parent then return 0 end

    local variants = containerVariantsOf(parent)
    local registered = variants
        and registerWithVariants(category, statName, stat, template, parent, variants, nextIndex)
        or registerSingle(category, statName, stat, template, parent, nextIndex)

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
    local started = Ext.Timer.MonotonicTime()
    local templates = Ext.Template.GetAllRootTemplates()
    if not templates then return log("ALERTA: GetAllRootTemplates devolveu nil") end

    local registered, unknownFamilies, index = 0, {}, 0
    local perContainer, missingParent = {}, {}
    local skipped = { sem_template = 0, recusado = 0, sem_magia = 0 }

    for _, statName in ipairs(Ext.Stats.GetStats("Object") or {}) do
        local stat = Ext.Stats.Get(statName, nil, false)
        local sharing = stat and categoriesByUseType[stat.ItemUseType]

        if sharing and statName:sub(1, 1) ~= "_" then
            local template = stat.RootTemplate and templates[stat.RootTemplate]
            if not template then
                skipped.sem_template = skipped.sem_template + 1
            else
                local family = baseFamily(templates, template.Id)
                for _, category in ipairs(sharing) do
                    if not accepts(category, stat, family) then
                        skipped.recusado = skipped.recusado + 1
                        if family then
                            unknownFamilies[family] = (unknownFamilies[family] or 0) + 1
                        end
                    else
                        local function nextIndex()
                            index = index + 1
                            return index
                        end
                        local count = register(category, statName, stat, template, nextIndex)
                        if count > 0 then
                            registered = registered + count
                            perContainer[category.container] =
                                (perContainer[category.container] or 0) + count
                        else
                            skipped.sem_magia = skipped.sem_magia + 1
                            missingParent[category.container] =
                                (missingParent[category.container] or 0) + 1
                        end
                    end
                end
            end
        end
    end

    for _, spell in ipairs(RETIRED_SPELLS) do
        Catalog.LegacySpells[#Catalog.LegacySpells + 1] = spell
    end

    log("descoberta:", registered, "sub-spells em", Ext.Timer.MonotonicTime() - started, "ms")
    for container, count in pairs(perContainer) do
        log("container:", container, count, "| sem magia para herdar:",
            missingParent[container] or 0)
    end
    log("descartados: sem template", skipped.sem_template,
        "| fora da categoria", skipped.recusado,
        "| sem magia usavel", skipped.sem_magia)

    for family, count in pairs(unknownFamilies) do
        log("familia fora das categorias:", family, count)
    end
end

Ext.Events.SessionLoaded:Subscribe(discover)
