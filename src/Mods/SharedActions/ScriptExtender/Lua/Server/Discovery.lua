local Catalog = Catalog

local MAX_FAMILY_DEPTH = 12
local RETIRED_SPELLS = { "SA_PotionProbe_OBJ_Potion_Healing" }
local HANDLE_FORMAT = "h%08xg%04xg%04xg%04xg%012x"

local categoryByUseType = {}
for _, category in ipairs(Catalog.Categories) do
    categoryByUseType[category.useType] = category
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

local function itemSpellOf(template)
    local found = nil
    for _, action in ipairs(template.OnUsePeaceActions or {}) do
        if action.Type == "UseSpell" and action.Spell and action.Spell ~= "" then
            found = action.Spell
        end
    end
    if not found then return nil end
    local stat = Ext.Stats.Get(found, nil, false)
    if not stat then return nil end
    if stat.ContainerSpells and stat.ContainerSpells ~= "" then return nil end
    return found
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
    created.UseCosts = stat.UseCosts
    created.DisplayName = handle .. ";1"

    if not category.inheritsItemSpell then
        local description = translatedHandle(template.Description)
        if description then created.Description = description .. ";1" end
    end

    created:Sync()
    return spell
end

local function register(category, statName, stat, template, index)
    local parent = Catalog.BaseEntry
    if category.inheritsItemSpell then
        parent = itemSpellOf(template)
        if not parent then return false end
    end

    local handle = handleFor(index)
    local spell = spellNameFor(category, statName)
    if not createSubSpell(spell, category, statName, stat, template, parent, handle) then
        return false
    end

    local templateKey = template.Name .. "_" .. template.Id
    Catalog.TemplateToSpell[string.lower(templateKey)] = spell
    Catalog.SpellToTemplate[spell] = templateKey
    Catalog.SpellContainer[spell] = category.container
    Catalog.Labels[spell] = { handle, translatedHandle(template.DisplayName) or "" }
    Catalog.LegacySpells[#Catalog.LegacySpells + 1] = category.prefix .. statName
    return true
end

local function discover()
    local started = Ext.Timer.MonotonicTime()
    local templates = Ext.Template.GetAllRootTemplates()
    if not templates then return log("ALERTA: GetAllRootTemplates devolveu nil") end

    local registered, unknownFamilies, index = 0, {}, 0
    local skipped = { sem_template = 0, sem_custo = 0, sem_familia = 0, sem_magia = 0 }

    for _, statName in ipairs(Ext.Stats.GetStats("Object") or {}) do
        local stat = Ext.Stats.Get(statName, nil, false)
        local category = stat and categoryByUseType[stat.ItemUseType]

        if category and statName:sub(1, 1) ~= "_" then
            local template = stat.RootTemplate and templates[stat.RootTemplate]
            if not template then
                skipped.sem_template = skipped.sem_template + 1
            elseif not stat.UseCosts or stat.UseCosts == "" then
                skipped.sem_custo = skipped.sem_custo + 1
            else
                local family = baseFamily(templates, template.Id)
                if not family or not category.families[family] then
                    skipped.sem_familia = skipped.sem_familia + 1
                    if family then
                        unknownFamilies[family] = (unknownFamilies[family] or 0) + 1
                    end
                else
                    index = index + 1
                    if register(category, statName, stat, template, index) then
                        registered = registered + 1
                    else
                        skipped.sem_magia = skipped.sem_magia + 1
                    end
                end
            end
        end
    end

    for _, spell in ipairs(RETIRED_SPELLS) do
        Catalog.LegacySpells[#Catalog.LegacySpells + 1] = spell
    end

    log("descoberta:", registered, "sub-spells em", Ext.Timer.MonotonicTime() - started, "ms")
    log("descartados: sem template", skipped.sem_template,
        "| sem custo", skipped.sem_custo,
        "| fora da familia", skipped.sem_familia,
        "| sem magia usavel", skipped.sem_magia)

    for family, count in pairs(unknownFamilies) do
        log("familia fora das categorias:", family, count)
    end
end

Ext.Events.SessionLoaded:Subscribe(discover)
