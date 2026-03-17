# gomokutest

## Chaos Ascension Gomoku

This repository now contains a **full implementation** of a chaotic Gomoku variant with hard power-escalation and roguelike meta progression.

### Features
- Base rules are still Gomoku (five in a row wins).
- Every turn generates energy from passive scaling, board presence, and special stones.
- Energy is spent on escalating abilities, including:
  - placing two stones in one turn,
  - converting enemy territory,
  - meteor-style area destruction,
  - expanding the board size,
  - summoning special stones (Titan, Parasite),
  - rewriting reality across a row and column.
- Abilities become cheaper and stronger as escalation levels rise.
- Between matches, players unlock increasingly ridiculous powers via persistent roguelike progression (`chaos_profile.json`).

## Run

```bash
python3 power_gomoku.py --matches 5 --seed 7 --verbose
```

Options:
- `--matches`: number of bot-vs-bot matches in a campaign.
- `--seed`: reproducible randomness.
- `--verbose`: prints logs and board snapshots.

## Notes on emergent chaos
Early turns look close to normal Gomoku. Mid/late game often explodes into conversion waves, meteors, board expansion, and special-stone chain reactions, generating intentionally overpowered and surprising outcomes.
