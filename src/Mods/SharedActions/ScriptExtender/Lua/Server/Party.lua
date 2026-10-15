Party = {}

function Party.IsPlayable(character)
    return Osi.IsSummon(character) ~= 1 and Osi.IsPartyFollower(character) ~= 1
end

local function partyEntityUuids()
    local uuids = {}
    for _, entity in ipairs(Ext.Entity.GetAllEntitiesWithComponent("PartyMember")) do
        local uuid = entity.Uuid and entity.Uuid.EntityUuid
        if uuid then uuids[#uuids + 1] = uuid end
    end
    return uuids
end

function Party.Members()
    local members = {}
    for _, row in ipairs(Osi.DB_Players:Get(nil) or {}) do
        if Party.IsPlayable(row[1]) then
            members[#members + 1] = row[1]
        end
    end
    return members
end

function Party.Split()
    local members = Party.Members()
    local isMember = {}
    for _, character in ipairs(members) do
        isMember[string.sub(character, -36)] = true
    end

    local others = {}
    for _, row in ipairs(Osi.DB_Players:Get(nil) or {}) do
        if not isMember[string.sub(row[1], -36)] then others[#others + 1] = row[1] end
    end
    for _, uuid in ipairs(partyEntityUuids()) do
        if not isMember[uuid] and not Party.IsPlayable(uuid) then others[#others + 1] = uuid end
    end
    return members, others
end

function Party.StripSpells(character, spells)
    for _, spell in ipairs(spells) do
        if Osi.HasSpell(character, spell) == 1 then
            Osi.RemoveSpell(character, spell, 0)
        end
    end
end
