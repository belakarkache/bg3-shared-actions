Spells = {}

local HANDLE_FORMAT = "h%08xg%04xg%04xg%04xg%012x"
local EXPORT_PATH = "SharedActions/spells.json"
local EXPORT_COMMAND = "sa_export"

local definitions = {}

local function fnv1a(text, seed)
    local hash = seed
    for i = 1, #text do
        hash = ((hash ~ text:byte(i)) * 16777619) & 0xffffffff
    end
    return hash
end

function Spells.HandleFor(name)
    local high, low = fnv1a(name, 2166136261), fnv1a(name, 0x5a5a5a5a)
    return string.format(HANDLE_FORMAT, high, low >> 16, low & 0xffff, 0, low)
end

local function textOf(value)
    local kind = type(value)
    if kind == "string" then return value end
    if kind == "number" then
        if math.type(value) == "float" and value == math.floor(value) then
            return tostring(math.tointeger(value))
        end
        return tostring(value)
    end
    if kind == "boolean" then return tostring(value) end
    local ok, list = pcall(function() return Ext.Json.Parse(Ext.Json.Stringify(value)) end)
    if ok and type(list) == "table" then return table.concat(list, ";") end
    return nil
end

function Spells.Define(name, parent, fields)
    local parentStat = Ext.Stats.Get(parent, nil, false)
    fields.SpellType = fields.SpellType or (parentStat and parentStat.SpellType)

    local texts = {}
    for field, value in pairs(fields) do
        texts[field] = textOf(value)
    end
    definitions[name] = { parent = parent, fields = texts }

    if not Ext.Stats.Get(name, nil, false) then return nil end
    return name
end

local function export()
    local names = {}
    for name in pairs(definitions) do
        names[#names + 1] = name
    end
    table.sort(names)

    local entries = {}
    for _, name in ipairs(names) do
        local definition = definitions[name]
        entries[#entries + 1] = { name = name, parent = definition.parent, fields = definition.fields }
    end

    Ext.IO.SaveFile(EXPORT_PATH, Ext.Json.Stringify(entries))
end

Ext.RegisterConsoleCommand(EXPORT_COMMAND, export)
