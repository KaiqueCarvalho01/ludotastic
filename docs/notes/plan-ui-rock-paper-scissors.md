# UI Improvement Plan: Rock-Paper-Scissors

Status: proposed
Scope: presentation-friendly UI for the bundled Rock-Paper-Scissors game
Target file: `src/ludotastic/games/rock_paper_scissors/ui.py`
Related files: `tests/test_rock_paper_scissors.py`, `docs/notes/rock-paper-scissors.md`
Engine changes: none

## 1. Context

Rock-Paper-Scissors is already implemented under
`src/ludotastic/games/rock_paper_scissors/`:

| File | Responsibility |
|---|---|
| `game.py` | Rules, state, actions, `CounterBot` and the `renderer()` hook |
| `ui.py` | NiceGUI renderer |
| `__init__.py` | Public exports |
| `tests/test_rock_paper_scissors.py` | Rules, bots, match flow and UI tests |
| `docs/notes/rock-paper-scissors.md` | Explanation of the game and the counter bot |

The game logic is complete and tested. The problem is the current renderer: it
works, but it is too compact and too plain for a live presentation. Spectators
far from the screen cannot quickly tell who is playing, what each player threw,
who won the round or who won the match.

## 2. Current UI

`ui.py` currently renders:

- a small scoreboard row: `Player 1: N`, `Round N`, `Player 2: N`;
- one small line describing the previous round, or
  `No rounds have been played yet.`;
- one row of `Rock`, `Paper` and `Scissors` flat buttons per human seat that can
  act;
- all buttons share the same style, with no icons and no color distinction;
- there is no clear round-winner banner and no match-over banner.

### Presentation pain points

- Text is small (`text-lg` at most) and hard to read from a distance.
- The scoreboard has no visual identity per player.
- The three moves look identical, so the audience cannot recognise a throw at a
  glance.
- The previous round is only a sentence, with no color or emphasis.
- Nothing announces "Player 1 wins the round" or "Player 1 wins the match".
- The layout leaves a lot of unused horizontal space, which looks empty on a
  projector.
- There is no visual indication that a player is waiting for the opponent.

## 3. Goals and non-goals

### Goals

- Make the match readable from across a room during a presentation.
- Show both players, their scores and their last throws clearly.
- Turn the round result into a prominent, color-coded banner.
- Give each move a distinct visual identity through color and Material icons.
- Announce the end of the match with a large banner.
- Keep the existing behaviour: simultaneous rounds, hot-seat play, seat gating
  and button disabling after a pick.
- Keep the implementation inside the Rock-Paper-Scissors UI only.

### Non-goals

- No changes to `game.py`, the engine, the action modes or the bot.
- No new game rules, no best-of-N configuration and no timer.
- No snapshots or image views for AI players.
- No changes to how observations are sent to Jev.
- No changes to other games.

## 4. Constraints

The current tests depend on markers and text. Preserve both wherever possible.

### Markers to preserve

| Marker | Element |
|---|---|
| `wins-0` | Player 1 score |
| `wins-1` | Player 2 score |
| `round` | Current round label |
| `last-round` | Previous-round description |
| `turn-{seat}` | "Player N, choose:" label |
| `move-{seat}-{move}` | One button per throw |

### Text to preserve

- `Player 1, choose:` and `Player 2, choose:`
- `No rounds have been played yet.`
- `Round 1`, `Round 2`, ...
- `Last round: Player 1 played rock; Player 2 played scissors. Player 1 won.`
- `Player 1: 1`, `Player 2: 0`, ...

If a text must change, update `tests/test_rock_paper_scissors.py` in the same
change. Prefer keeping the text and adding visual hierarchy around it.

### Coverage

The project requires 100% line and branch coverage. Every new conditional branch
in `ui.py` needs a test.

## 5. Proposed layout

```text
┌────────────────────────────────────────────────────────────┐
│                  ROCK-PAPER-SCISSORS                       │
│              Round 3 — first to 3 wins                     │
├───────────────────────┬──────────────┬─────────────────────┤
│  Player 1             │      VS      │  Player 2           │
│  Player 1: 1          │              │  Player 2: 1        │
│  [icon] Rock          │              │  [icon] Scissors    │
├───────────────────────┴──────────────┴─────────────────────┤
│  Player 1 wins the round!                                  │
│  Last round: Player 1 played rock; Player 2 played         │
│  scissors. Player 1 won.                                   │
├────────────────────────────────────────────────────────────┤
│  Player 1, choose:                                         │
│  [ Rock ]      [ Paper ]      [ Scissors ]                 │
├────────────────────────────────────────────────────────────┤
│  Player 2, choose:                                         │
│  [ Rock ]      [ Paper ]      [ Scissors ]                 │
└────────────────────────────────────────────────────────────┘
```

When a player has already picked this round, that player's buttons are disabled
and the other player keeps theirs until both throws are collected. After
`apply`, the renderer runs again with `state.last` filled, so the cards and the
round banner update together.

At the end of the match, a large banner replaces the round banner:

```text
┌────────────────────────────────────────────────────────────┐
│                  PLAYER 1 WINS THE MATCH!                  │
└────────────────────────────────────────────────────────────┘
```

## 6. Component breakdown

### 6.1 Header

- Large title: `Rock-Paper-Scissors` (`text-3xl sm:text-4xl font-black`).
- Subtitle with the round and target: `Round {rounds + 1} — first to 3 wins`.
- Keep `.mark("round")` on the subtitle.
- Keep the substring `Round N` so `should_see("Round 1")` still passes.

### 6.2 Player cards

Two cards side by side, one per seat, with a centered `VS` between them.

Each card contains:

- the seat label (`Player 1` or `Player 2`);
- the score in large text, preserving the `Player 1: N` format and the
  `wins-{seat}` marker;
- the last throw as a large Material icon plus the move name;
- a neutral placeholder before the first round:
  `Waiting for the first round`.

Player identity colors:

| Seat | Card | Name | Score |
|---|---|---|---|
| 0 | `border-blue-200 bg-blue-50 dark:bg-blue-950/40 dark:border-blue-800` | `text-blue-700 dark:text-blue-300` | `text-blue-800 dark:text-blue-200` |
| 1 | `border-rose-200 bg-rose-50 dark:bg-rose-950/40 dark:border-rose-800` | `text-rose-700 dark:text-rose-300` | `text-rose-800 dark:text-rose-200` |

Use literal class strings in constants instead of building class names with
f-strings, so Tailwind/NiceGUI always sees complete class names.

### 6.3 Round result banner

Rendered only when `state.last != (None, None)`.

- Large heading:
  - `Player 1 wins the round! (Rock beats Scissors)`
  - `Player 2 wins the round! (Scissors beats Paper)`
  - `Tie round! Both played Rock.`
- Keep the existing `_last_round(state)` sentence as a smaller line inside the
  banner, marked `last-round`. This preserves the existing UI test and doctest.
- Color:
  - round win: `bg-green-100 text-green-800 border-green-300`;
  - tie: `bg-amber-100 text-amber-800 border-amber-300`.

### 6.4 Action rows

For every seat in `sorted(ctx.seats)` that satisfies `ctx.can_act(seat)`:

- label `Player {seat + 1}, choose:` in large bold text, marked `turn-{seat}`;
- three large buttons with text and Material icons;
- each button keeps the marker `move-{seat}-{move.value}`;
- clicking submits `Throw(move=...)` and disables that seat's three buttons.

Move identity:

| Move | Icon | Button classes |
|---|---|---|
| Rock | `pan_tool` | `bg-slate-100 text-slate-800 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-100` |
| Paper | `description` | `bg-sky-100 text-sky-800 hover:bg-sky-200 dark:bg-sky-900 dark:text-sky-100` |
| Scissors | `content_cut` | `bg-emerald-100 text-emerald-800 hover:bg-emerald-200 dark:bg-emerald-900 dark:text-emerald-100` |

Button sizing: about `w-32 h-20` on small screens and `sm:w-40 sm:h-24` on
larger ones, with `rounded-xl`, `font-bold` and a mild shadow.

### 6.5 Match-over banner

Rendered when `ctx.game.outcome(state) is not None`.

- If `len(outcome.winners) == 1`:
  `Player {winner + 1} wins the match!`
- Otherwise:
  `Match over — it is a draw!`
- Style: `bg-purple-100 text-purple-800 border-purple-300`, large and centered,
  marked `match-over`.
- The round banner may stay visible above it.

## 7. Implementation sketch

```python
"""Rock-Paper-Scissors in NiceGUI."""

__all__: tuple[str, ...] = ("render",)

from typing import Final

from nicegui import ui

from ludotastic.engine.render import RenderContext
from ludotastic.games.rock_paper_scissors.game import (
    TARGET_WINS,
    Move,
    RockPaperScissorsState,
    Throw,
)

LABELS: Final = ("Player 1", "Player 2")

PLAYER_STYLES: Final = (
    {
        "card": "border-blue-200 bg-blue-50 dark:bg-blue-950/40 dark:border-blue-800",
        "name": "text-blue-700 dark:text-blue-300",
        "score": "text-blue-800 dark:text-blue-200",
    },
    {
        "card": "border-rose-200 bg-rose-50 dark:bg-rose-950/40 dark:border-rose-800",
        "name": "text-rose-700 dark:text-rose-300",
        "score": "text-rose-800 dark:text-rose-200",
    },
)

MOVE_STYLES: Final = {
    Move.ROCK: {
        "icon": "pan_tool",
        "button": (
            "bg-slate-100 text-slate-800 hover:bg-slate-200 "
            "dark:bg-slate-700 dark:text-slate-100"
        ),
    },
    Move.PAPER: {
        "icon": "description",
        "button": (
            "bg-sky-100 text-sky-800 hover:bg-sky-200 "
            "dark:bg-sky-900 dark:text-sky-100"
        ),
    },
    Move.SCISSORS: {
        "icon": "content_cut",
        "button": (
            "bg-emerald-100 text-emerald-800 hover:bg-emerald-200 "
            "dark:bg-emerald-900 dark:text-emerald-100"
        ),
    },
}


def _last_round(state: RockPaperScissorsState) -> str:
    """Keep the existing helper and its doctests unchanged."""
    ...  # Existing implementation stays as is.


def _header(state: RockPaperScissorsState) -> None:
    with ui.column().classes("items-center gap-1"):
        ui.label("Rock-Paper-Scissors").classes(
            "text-3xl sm:text-4xl font-black tracking-tight"
        )
        ui.label(
            f"Round {state.rounds + 1} — first to {TARGET_WINS} wins"
        ).classes("text-lg text-slate-600 dark:text-slate-300").mark("round")


def _player_card(state: RockPaperScissorsState, seat: int) -> None:
    style = PLAYER_STYLES[seat]
    last = state.last[seat]
    with ui.card().classes(
        "w-48 sm:w-64 p-4 items-center text-center border-2 rounded-2xl "
        f"{style['card']}"
    ):
        ui.label(LABELS[seat]).classes(f"text-xl font-bold {style['name']}")
        ui.label(f"{LABELS[seat]}: {state.wins[seat]}").classes(
            f"text-4xl font-mono font-black {style['score']}"
        ).mark(f"wins-{seat}")
        if last is None:
            ui.label("Waiting for the first round").classes(
                "text-sm text-slate-500"
            )
        else:
            ui.icon(MOVE_STYLES[last]["icon"]).classes("text-5xl")
            ui.label(last.value.title()).classes("text-lg font-semibold")


def _round_banner(state: RockPaperScissorsState) -> None:
    first, second = state.last
    if first is None or second is None:
        heading = "Ready to play"
        classes = "bg-slate-100 text-slate-700 border-slate-300"
    elif first.beats is second:
        heading = (
            f"Player 1 wins the round! "
            f"({first.value.title()} beats {second.value.title()})"
        )
        classes = "bg-green-100 text-green-800 border-green-300"
    elif second.beats is first:
        heading = (
            f"Player 2 wins the round! "
            f"({second.value.title()} beats {first.value.title()})"
        )
        classes = "bg-green-100 text-green-800 border-green-300"
    else:
        heading = f"Tie round! Both played {first.value.title()}."
        classes = "bg-amber-100 text-amber-800 border-amber-300"
    with ui.column().classes(
        f"w-full items-center gap-1 border-2 rounded-xl px-4 py-3 {classes}"
    ):
        ui.label(heading).classes("text-xl font-bold")
        ui.label(_last_round(state)).classes("text-sm").mark("last-round")


def _action_row(ctx: RenderContext, seat: int) -> None:
    buttons: list[ui.button] = []

    def play(move: Move) -> None:
        ctx.submit(seat, Throw(move=move))
        for button in buttons:
            button.disable()

    with ui.column().classes("items-center gap-3 w-full"):
        ui.label(f"{LABELS[seat]}, choose:").classes(
            "text-xl font-bold"
        ).mark(f"turn-{seat}")
        with ui.row().classes("gap-3 flex-wrap justify-center"):
            for move in Move:
                style = MOVE_STYLES[move]
                button = ui.button(
                    move.value.title(),
                    icon=style["icon"],
                    on_click=lambda _, move=move: play(move),
                    color=None,
                ).classes(
                    "w-32 h-20 sm:w-40 sm:h-24 text-base sm:text-lg font-bold "
                    f"rounded-xl shadow-sm {style['button']}"
                ).mark(f"move-{seat}-{move.value}")
                buttons.append(button)


def _match_over_banner(ctx: RenderContext, state: RockPaperScissorsState) -> None:
    outcome = ctx.match.game.outcome(state)
    assert outcome is not None  # noqa: S101
    if len(outcome.winners) == 1:
        text = f"{LABELS[outcome.winners[0]]} wins the match!"
    else:
        text = "Match over: it is a draw!"
    ui.label(text).classes(
        "w-full text-center text-2xl font-black bg-purple-100 text-purple-800 "
        "border-2 border-purple-300 rounded-xl px-4 py-3"
    ).mark("match-over")


def render(ctx: RenderContext) -> None:
    state = ctx.match.state
    assert isinstance(state, RockPaperScissorsState)  # noqa: S101
    with ui.column().classes(
        "items-center gap-6 w-full max-w-4xl px-4 py-4"
    ):
        _header(state)
        with ui.row().classes(
            "w-full flex-nowrap justify-center gap-4 sm:gap-8 items-stretch"
        ):
            _player_card(state, 0)
            ui.label("VS").classes(
                "text-2xl font-black text-slate-400 self-center"
            )
            _player_card(state, 1)
        _round_banner(state)
        for seat in sorted(ctx.seats):
            if ctx.can_act(seat):
                _action_row(ctx, seat)
        if ctx.match.game.outcome(state) is not None:
            _match_over_banner(ctx, state)
```

The renderer calls `_match_over_banner` only when
`ctx.match.game.outcome(state)` is not `None`, so the helper can assert that the
outcome exists. The round banner is always drawn; before the first round it
shows the ready message and the existing "No rounds have been played yet."
sentence, which keeps the original UI test green.

## 8. Behaviour details

- Both seats still act simultaneously through `to_move == (0, 1)`.
- `ctx.submit` is only offered for seats in `ctx.seats` that `ctx.can_act`.
- Clicking a throw disables that seat's three buttons immediately, as today.
- When both throws arrive, the engine applies the round and re-renders the
  match. The cards, the round banner and the score all update together.
- Hot-seat play with two humans continues to work: both action rows appear.
- When only one seat is `thinking`, only that seat's action row appears. This
  preserves `test_renderer_skips_seats_that_cannot_act`.
- The `VS` label is decorative and not marked.

## 9. Accessibility and responsiveness

- Use semantic text labels on buttons (`Rock`, `Paper`, `Scissors`) in addition
  to icons, so the buttons are understandable without the icon font.
- Keep good contrast: dark text on light backgrounds in light mode, light text
  on dark backgrounds in dark mode.
- Use `flex-wrap` on action rows and `w-48 sm:w-64` on cards so the layout works
  on a laptop and on a phone.
- Do not rely on color alone: the round banner also spells out the result, and
  each card shows the throw name next to the icon.

## 10. Tests

### Existing tests to keep green

- `test_play_hot_seat`: still expects both action rows, the scoreboard text and
  the previous-round sentence after one round.
- `test_renderer_skips_seats_that_cannot_act`: still expects only the seat that
  can act.
- `test_descriptions_and_keys`: still checks `callable(GAME.renderer())`.
- Doctest on `_last_round` remains unchanged.

### Tests to add

- **Match-over banner (win):** create a match with `start=False`, set
  `match.state` to a terminal state such as `wins=(TARGET_WINS, 0)`,
  `rounds=TARGET_WINS`, open the match, assert
  `should_see("Player 1 wins the match!")` and assert that no action row is
  shown.
- **Match-over banner (draw at cap):** set `wins=(0, 0)` and
  `rounds=MAX_ROUNDS`, open the match and assert the draw text. This covers the
  `else` branch of `_match_over_banner`.
- **Round banner branches:** a parametrized UI test covers a Player 2 round win
  and a tie round, so the new heading strings and the tie branch are exercised.
- **Icons and classes:** not asserted directly. Tests check visible text and
  markers, so they stay readable if the Tailwind classes change.

Keep coverage at 100% line and branch.

## 11. Documentation

Update the "What a human sees" section of
`docs/notes/rock-paper-scissors.md` to describe:

- the header and round subtitle;
- the two colored player cards with scores and last throws;
- the round-result banner;
- the large icon buttons;
- the match-over banner.

No changes are needed in `docs/api.md`, because the game is already listed.

## 12. Validation

Run from the repository root:

```bash
uv run pytest --cov
uv run ty check
uv run ruff check .
uv run ruff format --check .
```

Manual presentation check:

```bash
uv run ludotastic serve
```

Then:

1. Open <http://127.0.0.1:8080>.
2. Create a Rock-Paper-Scissors match with two human seats.
3. Confirm both action rows are visible and readable from a distance.
4. Play one round and confirm the cards, the round banner and the scores update.
5. Play until the match ends and confirm the match-over banner.
6. Switch to dark mode and confirm contrasts are acceptable.
7. Resize the window to a phone width and confirm the layout wraps cleanly.

## 13. Acceptance criteria

- [ ] Only `rock_paper_scissors/ui.py` changes for the UI itself.
- [ ] The game still defaults to `ActionMode.CHOICE` for Jev.
- [ ] Both player cards show name, score and last throw.
- [ ] The round result is a large, color-coded banner.
- [ ] Rock, Paper and Scissors buttons have distinct colors and Material icons.
- [ ] The match-over banner appears for a win and for a draw.
- [ ] Existing markers and tested text are preserved, or their tests are
  updated in the same change.
- [ ] `test_play_hot_seat` and `test_renderer_skips_seats_that_cannot_act` pass.
- [ ] `uv run pytest --cov` reports 100% line and branch coverage.
- [ ] `uv run ty check`, `uv run ruff check .` and
  `uv run ruff format --check .` pass.
- [ ] `docs/notes/rock-paper-scissors.md` reflects the new renderer.

## 14. Out of scope

- No engine changes.
- No changes to the rules, scoring, target wins or round cap.
- No animation, sound or confetti.
- No timer, countdown or auto-play.
- No changes to the AI observation or to the counter bot.
- No changes to Tic-Tac-Toe, Snake or 2048.
- No internationalisation of the UI; labels stay in English.
