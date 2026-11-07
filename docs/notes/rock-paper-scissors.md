# Rock-Paper-Scissors: rules, AI players and the counter bot

This note explains the bundled Rock-Paper-Scissors game: its rules, how a
simultaneous round is resolved, what an AI player receives, and how the
`counter` bot decides its throw. It describes the code that ships in
`src/ludotastic/games/rock_paper_scissors/`.

## The game

Two players throw at the same time. Each round is one of:

| Player 1 \ Player 2 | Rock | Paper | Scissors |
|---|---|---|---|
| **Rock** | Tie | Player 2 wins | Player 1 wins |
| **Paper** | Player 1 wins | Tie | Player 2 wins |
| **Scissors** | Player 2 wins | Player 1 wins | Tie |

- A round win scores one point; a tie scores nothing.
- The first player to **3** round wins takes the match.
- If **20** rounds pass without a winner, the match ends with the round wins as
  the final score.
- The game is always played by exactly two seats, both acting in every round.

The constants are `TARGET_WINS` and `MAX_ROUNDS` in the game module.

## State and actions

[`RockPaperScissorsState`][ludotastic.games.rock_paper_scissors.RockPaperScissorsState]
holds only public information:

```python
class RockPaperScissorsState(BaseModel):
    wins: tuple[Count, Count] = (0, 0)
    rounds: Count = 0
    last: tuple[Move | None, Move | None] = (None, None)
```

- `wins` is the score for seats 0 and 1.
- `rounds` is how many rounds have finished.
- `last` is the pair of throws from the previous round, or `(None, None)` before
  the first one.

An action is a
[`Throw`][ludotastic.games.rock_paper_scissors.Throw] with one
[`Move`][ludotastic.games.rock_paper_scissors.Move]: `rock`, `paper` or
`scissors`. The rule helpers are available on the move:

```python
>>> Move.ROCK.beats is Move.SCISSORS
True
>>> Move.ROCK.loses_to is Move.PAPER
True
```

## How a round advances

Rock-Paper-Scissors is the first bundled game that uses simultaneous movement.
The engine already supports it through `to_move`, and no engine changes were
needed:

1. [`to_move`][ludotastic.games.rock_paper_scissors.RockPaperScissors.to_move]
   returns `(0, 1)` while the match is not over, so the engine asks both seats
   to act in the same turn.
2. Both players see the **same** state. Neither player can see the other's
   current throw, because it only becomes public in `state.last` after the
   round.
3. The engine collects both actions and calls
   [`apply`][ludotastic.games.rock_paper_scissors.RockPaperScissors.apply]
   once. `apply` compares the throws, increments the winner's score, stores
   `last` and increments `rounds`.
4. [`outcome`][ludotastic.games.rock_paper_scissors.RockPaperScissors.outcome]
   ends the match when a seat reaches 3 wins, or when the round cap is reached.
5. If a match runs out of engine turns first,
   [`out_of_turns`][ludotastic.games.rock_paper_scissors.RockPaperScissors.out_of_turns]
   keeps the round wins as the score.

A round is a pure state transition: the same seed and the same pair of actions
always produce the same next state.

## What a human sees

The NiceGUI renderer shows:

- a scoreboard with each player's wins and the current round;
- a line describing the previous round, or `No rounds have been played yet.`;
- one row of **Rock**, **Paper** and **Scissors** buttons for every human seat
  that can act.

Clicking a button submits `Throw(move=...)` for that seat and disables that
seat's three buttons until the round finishes. With two human seats the page
works in hot-seat mode: both rows are visible, and each player clicks their own
throw.

## What an AI player receives

AI players go through
[`AIPlayer`][ludotastic.AIPlayer]. Every request starts with the game
name, the player's seat and the rules:

```text
You are playing Rock-Paper-Scissors as Player 1. Play to win.

Rules:
Two players throw simultaneously every round: rock, paper or scissors. ...
```

The prompt is the text from
[`observe`][ludotastic.games.rock_paper_scissors.RockPaperScissors.observe].
Before the first round it looks like this:

```text
You are Player 1. Score: you 0, opponent 0 (first to 3 wins). Round 1. No rounds have been played yet. Choose one: rock (beats scissors, loses to paper), paper (beats rock, loses to scissors), scissors (beats paper, loses to rock).
```

After a round it adds the public result, from that seat's point of view:

```text
You are Player 1. Score: you 1, opponent 0 (first to 3 wins). Round 3. Last round: you played rock; your opponent played scissors; you won. Choose one: rock (beats scissors, loses to paper), paper (beats rock, loses to scissors), scissors (beats paper, loses to rock).
```

The other seat gets the mirrored description: `you lost` instead of `you won`,
and its own throw first.

The observation contains no hidden information. It only reports throws that
have already happened, so an AI cannot know what the opponent is about to play.
That is a property of the game, not something the engine has to hide.

### Action modes

The game defaults to
[`ActionMode.CHOICE`][ludotastic.ActionMode.CHOICE], the mode that suits
TypeSafe's Jev. The three modes behave like this:

| Mode | What the model gets | What it returns |
|---|---|---|
| `choice` (**default**) | One named option per legal throw, described in words | The chosen option |
| `structured` | The observation and the `Throw` model | A filled-in `Throw` |
| `tools` | The observation, the `Throw` model and tools to inspect the game | A filled-in `Throw` |

In `choice` mode the options are:

```text
rock:     Play rock. Rock beats scissors and loses to paper.
paper:    Play paper. Paper beats rock and loses to scissors.
scissors: Play scissors. Scissors beats paper and loses to rock.
```

The rules in the option text are public. They explain the game, not the
opponent's next move, so they do not give the answer away.

In `structured` and `tools` modes the model submits a `Throw`. If it submits
something illegal, the engine sends it back with the legal action keys and lets
it retry. In `tools` mode the model can also call `look_at_game` and
`list_legal_moves` before submitting.

The engine also has a forced-move shortcut: when only one action is legal, it
plays that action without asking the model. Rock-Paper-Scissors always has
three legal actions while the match is running, so this shortcut does not apply
to it.

## How the counter bot responds

[`CounterBot`][ludotastic.games.rock_paper_scissors.CounterBot] is the
scripted opponent registered as `bot:counter`.

### First round

There is no previous throw to react to, so the bot picks a move with the
match's seeded random source:

```python
last = state.last[1 - ctx.player]
move = ctx.rng.choice(tuple(Move)) if last is None else last.loses_to
```

### Later rounds

The bot looks at the opponent's throw from the previous round and plays the move
that defeats it. If the opponent played rock, the bot plays paper; if the
opponent played paper, the bot plays scissors; if the opponent played scissors,
the bot plays rock.

The code uses `Move.loses_to` for this. `Move.beats` is the move that a throw
defeats, so using `beats` here would make the bot play the throw that **loses**
to the opponent's last move. The plan text used `beats`, but the shipped bot
uses `loses_to` so that it actually counters.

The bot has no other memory: everything it knows is in `state.last`. If the
opponent changes strategy, the bot only reacts one round later.

### Example match

With `seed=1`, `CounterBot` against the engine's `RandomBot` plays out like
this:

| Round | Counter bot | Random bot | Result | Score |
|---|---|---|---|---|
| 1 | rock | rock | Tie | 0-0 |
| 2 | paper | rock | Counter bot wins | 1-0 |
| 3 | paper | rock | Counter bot wins | 2-0 |
| 4 | paper | rock | Counter bot wins | 3-0 |

The match ends with `Player 1 reached 3 wins`. The counter bot's first throw is
random, and after that it only has to beat the last throw it saw.

Because the bot reacts to the previous round, it is predictable against an
opponent that has noticed the pattern. That is intentional: it is a scripted
baseline, not a solver.

## Running it

From the repository root:

```bash
uv run ludotastic games
uv run ludotastic play rock-paper-scissors typesafe:jev-latest bot:counter --rounds 5
uv run ludotastic serve
```

In the web playground, open <http://127.0.0.1:8080>, create a
Rock-Paper-Scissors match and confirm the scoreboard, the last-round line and
the result at the end.

## Tests

`tests/test_rock_paper_scissors.py` covers:

- the initial state and the simultaneous `to_move`;
- all nine throw combinations;
- winning by target wins and by the round cap;
- `out_of_turns`;
- observations before and after a round;
- action descriptions, keys and parsing;
- `CounterBot` on the first round and after an opponent throw;
- a complete match against `RandomBot`;
- the UI flow for two human seats and the seat-gating rule.

The game and UI modules are covered at 100% line and branch coverage.
