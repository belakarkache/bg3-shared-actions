local Catalog = Catalog

local MAX_FAMILY_DEPTH = 12
local RETIRED_SPELLS = { "SA_PotionProbe_OBJ_Potion_Healing" }
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

local function castableSpell(name)
    if not name or name == "" then return nil end
    local stat = Ext.Stats.Get(name, nil, false)
    if not stat then return nil end
    if stat.ContainerSpells and stat.ContainerSpells ~= "" then return nil end
    return name
end

local function itemSpellOf(template)
    local found = nil
    for _, action in ipairs(template.OnUsePeaceActions or {}) do
        if action.Type == "UseSpell" and action.Spell and action.Spell ~= "" then
            found = action.Spell
        end
    end
    return castableSpell(found)
end

local function parentSpellOf(category, stat, template)
    if category.inheritsItemSpell then return itemSpellOf(template) end
    if category.inheritsProjectileSpell then
        return castableSpell(Catalog.ProjectileSpells[stat.RootTemplate])
    end
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

local function createSubSpell(spell, category, statName, stat, template, parent, handle)
    if Ext.Stats.Get(spell, nil, false) then return spell end

    local created = Ext.Stats.Create(spell, "SpellData", parent)
    if not created then
        log("ALERTA: Create falhou para", spell, "| parent:", parent)
        return nil
    end

    created.SpellContainerID = category.container
    created.ContainerSpells = ""
    created.Icon = iconFor(statName, template)
    created.UseCosts = category.forcedUseCosts or stat.UseCosts
    created.DisplayName = handle .. ";1"

    if not created.Description or created.Description == "" then
        local description = translatedHandle(template.TechnicalDescription)
        local params = template.TechnicalDescriptionParams
        if not description then
            description = translatedHandle(template.Description)
            params = nil
        end
        if description then
            created.Description = description .. ";1"
            created.DescriptionParams = params or ""
        end
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

local function register(category, statName, stat, template, index)
    local parent = parentSpellOf(category, stat, template)
    if not parent then return false end

    local handle = handleFor(index)
    local spell = spellNameFor(category, statName)
    if not createSubSpell(spell, category, statName, stat, template, parent, handle) then
        return false
    end

    local templateKey = template.Name .. "_" .. template.Id
    local key = string.lower(templateKey)
    local sharing = Catalog.TemplateToSpell[key] or {}
    sharing[#sharing + 1] = spell
    Catalog.TemplateToSpell[key] = sharing
    Catalog.SpellToTemplate[spell] = templateKey
    Catalog.SpellContainer[spell] = category.container
    Catalog.Labels[spell] = { handle, translatedHandle(template.DisplayName) or "" }
    Catalog.LegacySpells[#Catalog.LegacySpells + 1] = category.prefix .. statName
    return true
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
                        index = index + 1
                        if register(category, statName, stat, template, index) then
                            registered = registered + 1
                            perContainer[category.container] =
                                (perContainer[category.container] or 0) + 1
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
