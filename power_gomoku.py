#!/usr/bin/env python3
"""Overpowered Gomoku: an escalating, roguelike chaos variant of five-in-a-row.

This module provides:
- A complete game engine with escalating energy and abilities.
- A bot-vs-bot simulator that demonstrates emergent chaos.
- Persistent roguelike progression between matches via JSON profile storage.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

Coord = Tuple[int, int]


@dataclass
class Cell:
    owner: Optional[int] = None
    kind: str = "normal"  # normal, titan, parasite, mine
    charge: int = 0

    def is_empty(self) -> bool:
        return self.owner is None


@dataclass
class Ability:
    name: str
    base_cost: int
    description: str
    min_turn: int = 0
    unlock_rank: int = 0


@dataclass
class PlayerState:
    player_id: int
    energy: int = 0
    escalation_level: int = 1
    abilities: List[str] = field(default_factory=list)


class Board:
    def __init__(self, size: int = 13):
        self.size = size
        self.grid: List[List[Cell]] = [[Cell() for _ in range(size)] for _ in range(size)]

    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.size and 0 <= c < self.size

    def get(self, r: int, c: int) -> Cell:
        return self.grid[r][c]

    def empty_cells(self) -> List[Coord]:
        out = []
        for r in range(self.size):
            for c in range(self.size):
                if self.grid[r][c].is_empty():
                    out.append((r, c))
        return out

    def place(self, r: int, c: int, owner: int, kind: str = "normal") -> bool:
        if not self.in_bounds(r, c):
            return False
        cell = self.grid[r][c]
        if not cell.is_empty():
            return False
        self.grid[r][c] = Cell(owner=owner, kind=kind)
        return True

    def expand(self, rings: int) -> None:
        for _ in range(rings):
            self.size += 2
            new_grid = [[Cell() for _ in range(self.size)] for _ in range(self.size)]
            for r in range(self.size - 2):
                for c in range(self.size - 2):
                    new_grid[r + 1][c + 1] = self.grid[r][c]
            self.grid = new_grid

    def render(self) -> str:
        glyph = {None: ".", 1: "X", 2: "O"}
        special = {"titan": "T", "parasite": "P", "mine": "M"}
        lines = []
        for row in self.grid:
            line = []
            for cell in row:
                if cell.owner is None:
                    line.append(".")
                elif cell.kind == "normal":
                    line.append(glyph[cell.owner])
                else:
                    marker = special.get(cell.kind, "?")
                    line.append(marker.lower() if cell.owner == 2 else marker)
            lines.append(" ".join(line))
        return "\n".join(lines)


class ChaosGomoku:
    ABILITIES: Dict[str, Ability] = {
        "double_strike": Ability(
            "Double Strike",
            base_cost=6,
            description="Place two stones in one turn.",
            unlock_rank=0,
        ),
        "convert_pulse": Ability(
            "Convert Pulse",
            base_cost=9,
            description="Convert enemy stones in an area.",
            min_turn=4,
            unlock_rank=1,
        ),
        "meteor": Ability(
            "Meteor Collapse",
            base_cost=12,
            description="Destroy a square area of stones.",
            min_turn=6,
            unlock_rank=2,
        ),
        "board_bloom": Ability(
            "Board Bloom",
            base_cost=14,
            description="Grow the board with new space.",
            min_turn=8,
            unlock_rank=2,
        ),
        "summon_titan": Ability(
            "Summon Titan",
            base_cost=16,
            description="Place a titan stone that counts as 2 in line scoring.",
            min_turn=9,
            unlock_rank=3,
        ),
        "parasite_seed": Ability(
            "Parasite Seed",
            base_cost=18,
            description="Plant a parasite stone that may spread each turn.",
            min_turn=10,
            unlock_rank=3,
        ),
        "reality_fracture": Ability(
            "Reality Fracture",
            base_cost=24,
            description="Rewrite a full row and column into your control.",
            min_turn=12,
            unlock_rank=4,
        ),
    }

    def __init__(self, board_size: int, profile: dict, seed: Optional[int] = None):
        self.random = random.Random(seed)
        self.board = Board(board_size)
        self.turn = 1
        self.current_player = 1
        self.winner: Optional[int] = None
        self.log: List[str] = []
        rank = profile.get("rank", 0)
        unlocked = set(profile.get("unlocked_abilities", ["double_strike"]))
        self.players: Dict[int, PlayerState] = {
            1: PlayerState(1, abilities=self._ability_list(rank, unlocked)),
            2: PlayerState(2, abilities=self._ability_list(rank, unlocked)),
        }

    def _ability_list(self, rank: int, unlocked: set) -> List[str]:
        out = []
        for key, ability in self.ABILITIES.items():
            if ability.unlock_rank <= rank and key in unlocked:
                out.append(key)
        return out

    def ability_cost(self, player_id: int, ability_key: str) -> int:
        base = self.ABILITIES[ability_key].base_cost
        escalation_discount = self.players[player_id].escalation_level - 1
        return max(1, base - escalation_discount)

    def passive_energy_gain(self, player_id: int) -> None:
        stones = sum(1 for row in self.board.grid for c in row if c.owner == player_id)
        level = self.players[player_id].escalation_level
        gain = 2 + stones // 4 + level
        self.players[player_id].energy += gain

    def resolve_special_stones(self, player_id: int) -> None:
        for r in range(self.board.size):
            for c in range(self.board.size):
                cell = self.board.get(r, c)
                if cell.owner != player_id:
                    continue
                if cell.kind == "parasite":
                    dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
                    self.random.shuffle(dirs)
                    for dr, dc in dirs[:2]:
                        rr, cc = r + dr, c + dc
                        if self.board.in_bounds(rr, cc):
                            target = self.board.get(rr, cc)
                            if target.owner not in (None, player_id) and self.random.random() < 0.35:
                                target.owner = player_id
                                target.kind = "normal"
                elif cell.kind == "titan":
                    self.players[player_id].energy += 1

    def choose_move(self, player_id: int) -> Tuple[str, List[Coord]]:
        p = self.players[player_id]
        available = self.board.empty_cells()
        if not available:
            return ("none", [])

        # Prefer ability plays as escalation ramps up.
        ability_candidates = []
        for key in p.abilities:
            ability = self.ABILITIES[key]
            if self.turn < ability.min_turn:
                continue
            cost = self.ability_cost(player_id, key)
            if p.energy >= cost:
                score = self.turn + p.escalation_level * 2 - cost
                ability_candidates.append((score, key))

        if ability_candidates and self.random.random() < min(0.25 + self.turn * 0.02, 0.9):
            ability_candidates.sort(reverse=True)
            return (ability_candidates[0][1], [])

        # Normal placement: try win/block first.
        tactical = self.find_tactical_move(player_id)
        if tactical:
            return ("place", [tactical])
        return ("place", [self.random.choice(available)])

    def find_tactical_move(self, player_id: int) -> Optional[Coord]:
        enemy = 2 if player_id == 1 else 1
        candidates = self.board.empty_cells()
        self.random.shuffle(candidates)
        for r, c in candidates[:50]:
            if self.would_win(player_id, (r, c)):
                return (r, c)
        for r, c in candidates[:50]:
            if self.would_win(enemy, (r, c)):
                return (r, c)
        return None

    def would_win(self, player_id: int, move: Coord) -> bool:
        r, c = move
        self.board.place(r, c, player_id)
        ok = self.has_five(player_id)
        self.board.grid[r][c] = Cell()
        return ok

    def apply_action(self, player_id: int, action: str, coords: List[Coord]) -> None:
        if action == "place":
            if not coords:
                return
            r, c = coords[0]
            if self.board.place(r, c, player_id):
                self.log.append(f"P{player_id} placed at {(r, c)}")
            return

        method = getattr(self, f"ability_{action}", None)
        if not method:
            return
        cost = self.ability_cost(player_id, action)
        if self.players[player_id].energy < cost:
            return
        self.players[player_id].energy -= cost
        method(player_id)
        self.log.append(f"P{player_id} cast {self.ABILITIES[action].name} (cost {cost})")

    def ability_double_strike(self, player_id: int) -> None:
        empties = self.board.empty_cells()
        self.random.shuffle(empties)
        for pos in empties[:2]:
            self.board.place(pos[0], pos[1], player_id)

    def ability_convert_pulse(self, player_id: int) -> None:
        enemy = 2 if player_id == 1 else 1
        targets = [(r, c) for r in range(self.board.size) for c in range(self.board.size) if self.board.get(r, c).owner == enemy]
        if not targets:
            return
        center = self.random.choice(targets)
        radius = 1 + self.players[player_id].escalation_level // 3
        for r in range(center[0] - radius, center[0] + radius + 1):
            for c in range(center[1] - radius, center[1] + radius + 1):
                if self.board.in_bounds(r, c):
                    cell = self.board.get(r, c)
                    if cell.owner == enemy:
                        cell.owner = player_id
                        if cell.kind == "mine":
                            cell.kind = "normal"

    def ability_meteor(self, player_id: int) -> None:
        center = self.random.choice([(r, c) for r in range(self.board.size) for c in range(self.board.size)])
        radius = 1 + self.players[player_id].escalation_level // 4
        for r in range(center[0] - radius, center[0] + radius + 1):
            for c in range(center[1] - radius, center[1] + radius + 1):
                if self.board.in_bounds(r, c):
                    self.board.grid[r][c] = Cell()

    def ability_board_bloom(self, player_id: int) -> None:
        rings = 1 + self.players[player_id].escalation_level // 5
        self.board.expand(rings)

    def ability_summon_titan(self, player_id: int) -> None:
        empties = self.board.empty_cells()
        if empties:
            r, c = self.random.choice(empties)
            self.board.place(r, c, player_id, kind="titan")

    def ability_parasite_seed(self, player_id: int) -> None:
        empties = self.board.empty_cells()
        if empties:
            r, c = self.random.choice(empties)
            self.board.place(r, c, player_id, kind="parasite")

    def ability_reality_fracture(self, player_id: int) -> None:
        row = self.random.randrange(self.board.size)
        col = self.random.randrange(self.board.size)
        for c in range(self.board.size):
            if not self.board.get(row, c).is_empty():
                self.board.get(row, c).owner = player_id
                self.board.get(row, c).kind = "normal"
        for r in range(self.board.size):
            if not self.board.get(r, col).is_empty():
                self.board.get(r, col).owner = player_id
                self.board.get(r, col).kind = "normal"

    def has_five(self, player_id: int) -> bool:
        dirs = [(1, 0), (0, 1), (1, 1), (1, -1)]
        for r in range(self.board.size):
            for c in range(self.board.size):
                cell = self.board.get(r, c)
                if cell.owner != player_id:
                    continue
                for dr, dc in dirs:
                    score = 0
                    rr, cc = r, c
                    while self.board.in_bounds(rr, cc):
                        cur = self.board.get(rr, cc)
                        if cur.owner != player_id:
                            break
                        score += 2 if cur.kind == "titan" else 1
                        if score >= 5:
                            return True
                        rr += dr
                        cc += dc
        return False

    def step(self) -> None:
        pid = self.current_player
        self.passive_energy_gain(pid)
        self.resolve_special_stones(pid)

        if self.turn % 3 == 0:
            self.players[pid].escalation_level += 1

        action, coords = self.choose_move(pid)
        self.apply_action(pid, action, coords)

        if self.has_five(pid):
            self.winner = pid

        self.current_player = 2 if self.current_player == 1 else 1
        self.turn += 1

    def play(self, max_turns: int = 220) -> int:
        while self.winner is None and self.turn <= max_turns and self.board.empty_cells():
            self.step()

        if self.winner is None:
            p1 = sum(1 for row in self.board.grid for c in row if c.owner == 1)
            p2 = sum(1 for row in self.board.grid for c in row if c.owner == 2)
            self.winner = 1 if p1 >= p2 else 2
            self.log.append(f"Timeout judge by territory: P1={p1}, P2={p2}")
        return self.winner


class RogueProgression:
    PROFILE_PATH = Path("chaos_profile.json")

    def __init__(self):
        self.profile = self.load_profile()

    def load_profile(self) -> dict:
        if self.PROFILE_PATH.exists():
            return json.loads(self.PROFILE_PATH.read_text())
        return {
            "rank": 0,
            "shards": 0,
            "unlocked_abilities": ["double_strike"],
            "wins": {"1": 0, "2": 0},
            "matches_played": 0,
        }

    def save(self) -> None:
        self.PROFILE_PATH.write_text(json.dumps(self.profile, indent=2))

    def reward(self, winner: int) -> List[str]:
        self.profile["matches_played"] += 1
        self.profile["wins"][str(winner)] += 1
        self.profile["shards"] += 3 + self.profile["rank"]

        unlocked_now = []
        costs = [4, 6, 8, 11, 15, 20]
        ability_order = [
            "convert_pulse",
            "meteor",
            "board_bloom",
            "summon_titan",
            "parasite_seed",
            "reality_fracture",
        ]

        while self.profile["rank"] < len(costs) and self.profile["shards"] >= costs[self.profile["rank"]]:
            self.profile["shards"] -= costs[self.profile["rank"]]
            unlock = ability_order[self.profile["rank"]]
            self.profile["rank"] += 1
            if unlock not in self.profile["unlocked_abilities"]:
                self.profile["unlocked_abilities"].append(unlock)
                unlocked_now.append(unlock)

        self.save()
        return unlocked_now


def run_campaign(matches: int, seed: Optional[int], verbose: bool) -> None:
    progression = RogueProgression()
    base_rng = random.Random(seed)

    for i in range(matches):
        match_seed = base_rng.randint(0, 10**9)
        game = ChaosGomoku(board_size=13, profile=progression.profile, seed=match_seed)
        winner = game.play()
        unlocked = progression.reward(winner)

        print(f"\n=== Match {i + 1} ===")
        print(f"Winner: Player {winner}")
        print(f"Turns: {game.turn - 1} | Final board size: {game.board.size}")
        print(
            f"Energy P1={game.players[1].energy}, P2={game.players[2].energy} | "
            f"Escalation P1={game.players[1].escalation_level}, P2={game.players[2].escalation_level}"
        )
        if unlocked:
            print("Unlocked:", ", ".join(unlocked))
        else:
            print("Unlocked: none")

        if verbose:
            print("\nLast 25 log entries:")
            for entry in game.log[-25:]:
                print("-", entry)
            print("\nBoard snapshot:")
            print(game.board.render())

    print("\n=== Roguelike Profile ===")
    print(json.dumps(progression.profile, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Overpowered roguelike Gomoku")
    parser.add_argument("--matches", type=int, default=3, help="Number of matches to simulate")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible runs")
    parser.add_argument("--verbose", action="store_true", help="Print board and action logs")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_campaign(args.matches, args.seed, args.verbose)


if __name__ == "__main__":
    main()
