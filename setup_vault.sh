#!/bin/bash
set -e

VAULT="/c/Users/Teddy/Documents/The Thought Vault"
PROJECT="$VAULT/Bid Better"
TEMPLATES="$VAULT/_Templates"

# Create folders
mkdir -p "$PROJECT/00 - Dashboard"
mkdir -p "$PROJECT/10 - Systems"
mkdir -p "$PROJECT/20 - Decisions"
mkdir -p "$PROJECT/30 - Concepts"
mkdir -p "$PROJECT/40 - Brainstorming"
mkdir -p "$PROJECT/50 - References"

# Templates
cat > "$TEMPLATES/Bid Better - Decision Template.md" <<'EOF'
# D{{NUMBER}} — {{TITLE}}

Status:: Proposed
Decided:: 
Affects:: 
Supersedes:: 
Superseded by:: 
Tags:: #decision #bidbetter

## Question
What is being decided.

## Context
What prompted this decision. What constraints apply.

## Options considered
- **A —** 
- **B —** 
- **C —** 

## Decision
What we picked.

## Reasoning
Why. Which design pillars it serves. What tradeoffs we accepted.

## Consequences
**Enables:**
- 

**Rules out:**
- 

**New questions raised:**
- 
EOF

cat > "$TEMPLATES/Bid Better - System MOC Template.md" <<'EOF'
# {{SYSTEM}} MOC

Tags:: #moc #bidbetter

## Current state
*One to three paragraphs. The synthesized answer to "what does this system do right now?" Rewritten when significant decisions land. If this section is empty, the system has no decisions yet.*

## Pillars
- 

## Decisions
*Newest at top.*
- 

## Open questions
- 

## Related concepts
- 

## Related systems
- 
EOF

cat > "$TEMPLATES/Bid Better - Concept Template.md" <<'EOF'
# {{CONCEPT}}

Tags:: #concept #bidbetter

## Definition
One or two sentences.

## Why it matters
How this concept shows up in the design.

## Related
- 
EOF

# Dashboard
cat > "$PROJECT/00 - Dashboard/Home.md" <<'EOF'
# Home

The vault for Bid Better — auction-strategy game (working title).

## Vision
A living, breathing economic simulation. Conservation of currency and items.
Bots play by the same rules as players. The auction is the player's primary
window into the machine; the machine runs whether players are present or not.

The fantasy: sniping an auction below market, tricking opponents into
overpaying, ruling the player-to-player marketplace, avoiding traps.

## Design pillars
1. **Conservation.** Money and items never spawn from nothing or vanish into nothing. Every faucet has a source; every sink has a destination.
2. **Bots are participants, not props.** Bots have bankrolls, collections, goals, and can go bankrupt. They never access information players can't.
3. **Information asymmetry is the core fantasy.** Appraisal, bluffing, and forgery detection are load-bearing. Mechanics that flatten information work against the design.
4. **The world keeps moving.** Real-time expeditions, persistent markets, ongoing bot activity. The player dips in.
5. **Auctions are the primary loop.** 1–7 minutes, sealed-bid per round, multi-round.

## Navigation
- [[Decision Index]] — every decision made, newest first
- [[Open Questions]] — unresolved threads
- [[Economy MOC]]
- [[Auction MOC]]
- [[Items MOC]]
- [[Bots MOC]]
- [[Characters MOC]]
- [[Collections MOC]]
- [[Warehouse MOC]]
- [[World MOC]]

## Working order
Currently resolving in this order:
1. Economy conservation laws
2. Item model
3. Appraisal and information model
4. Auction format
5. Bot architecture
6. Everything else
EOF

cat > "$PROJECT/00 - Dashboard/Decision Index.md" <<'EOF'
# Decision Index

Tags:: #index #bidbetter

*Newest at top. Once Dataview is installed, this will auto-populate.*

## Manual list
- (none yet)

## Dataview version (after installing the plugin)
```dataview
TABLE Status, Decided, Affects
FROM "Bid Better/20 - Decisions"
SORT file.name DESC
```
EOF

cat > "$PROJECT/00 - Dashboard/Open Questions.md" <<'EOF'
# Open Questions

Tags:: #index #bidbetter

*Threads we have not yet resolved. Each links to the system it belongs to.*

## Economy
- 

## Items
- 

## Appraisal
- 

## Auctions
- 

## Bots
- 

## Characters
- 

## Collections
- 

## Warehouse
- 

## World
- 

## Cross-cutting
- 
EOF

# System MOCs
cat > "$PROJECT/10 - Systems/Economy MOC.md" <<'EOF'
# Economy MOC

Tags:: #moc #bidbetter

## Current state
*No decisions yet. About to begin work on conservation laws.*

## Pillars
- Conservation of currency
- Conservation of items
- Vendors, the house, and other NPCs hold real bankrolls
- Faucets and sinks must be explicitly accounted for

## Decisions
- (none yet)

## Open questions
- See [[Open Questions]]

## Related concepts
- [[Faucet]]
- [[Sink]]
- [[Conservation]]

## Related systems
- [[Auction MOC]]
- [[Items MOC]]
- [[Bots MOC]]
EOF

for SYS in Auction Items Bots Characters Collections Warehouse World; do
cat > "$PROJECT/10 - Systems/${SYS} MOC.md" <<EOF
# ${SYS} MOC

Tags:: #moc #bidbetter

## Current state
*No decisions yet.*

## Pillars
- 

## Decisions
- (none yet)

## Open questions
- See [[Open Questions]]

## Related concepts
- 

## Related systems
- 
EOF
done

# Concepts
cat > "$PROJECT/30 - Concepts/Faucet.md" <<'EOF'
# Faucet

Tags:: #concept #bidbetter

## Definition
A mechanism that introduces currency or items into the game economy.

## Why it matters
Every faucet must be explicitly accounted for. Untracked faucets cause inflation
and break the conservation pillar. The source of a faucet is as important as
its rate — money minted by mining a resource behaves differently from money
paid by an NPC vendor with a real bankroll.

## Related
- [[Sink]]
- [[Conservation]]
EOF

cat > "$PROJECT/30 - Concepts/Sink.md" <<'EOF'
# Sink

Tags:: #concept #bidbetter

## Definition
A mechanism that removes currency or items from the game economy.

## Why it matters
Sinks balance faucets. Without sufficient sinks, faucets cause inflation.
A "sink" that just transfers value from one player to another is not a true
sink — it has to leave the system entirely (or enter a tracked reserve like
a vendor bankroll, the house, or a tax authority).

## Related
- [[Faucet]]
- [[Conservation]]
EOF

cat > "$PROJECT/30 - Concepts/Conservation.md" <<'EOF'
# Conservation

Tags:: #concept #bidbetter

## Definition
The principle that money and items in the game cannot spawn from nothing
or vanish into nothing. Every change in supply has a tracked source or
destination.

## Why it matters
This is design pillar #1. It's what makes the simulation honest and what
makes bot behavior meaningful — a bot can actually run out of money,
because money is real.

## Related
- [[Faucet]]
- [[Sink]]
- [[Vendor Bankroll]]
EOF

# Folder index files
cat > "$PROJECT/40 - Brainstorming/_index.md" <<'EOF'
# Brainstorming

Raw notes, working drafts, captures from chat sessions before they become decisions.
EOF

cat > "$PROJECT/50 - References/_index.md" <<'EOF'
# References

External material — Bid King notes, real-world economic references, etc.
EOF

echo "Done. Vault structure created at: $PROJECT"