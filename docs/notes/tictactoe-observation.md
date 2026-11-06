# Tic-Tac-Toe: how the board is shown to AI players

*Measured on 2026-11-05 with `typesafe:jev-latest` (`jev-1.14.0`), in the
`choice` action mode. No code was changed as a result; this records what we
found, for when we revisit it.*

## Question

In a live match, Jev missed an obvious block. Was it our fault (it not receiving
the board, or receiving it in a poor format), or a limitation of the model?

## What Jev receives

Jev gets the whole board correctly. For the position it lost on, the request
carried the ASCII board from
[`TicTacToe.observe`][ludotastic.games.tictactoe.TicTacToe.observe], whose turn
it is, the list of empty cells, the rules, and one option per legal move. Jev
leaned 58/42 towards the wrong cell, and answered the same every time it was
asked.

## Benchmark

60 positions where exactly one move is right (30 immediate wins, 30 forced
blocks), sampled from every reachable position with at least 3 empty cells.
Random guessing would score 25%.

| Format | Score | Wins | Blocks | Fair? |
|---|---|---|---|---|
| A. ASCII board (**current**) | 87% | 28/30 | 24/30 | Yes |
| B. The 8 lines listed in words (`top row: top left=O, ...`) | 97% | 29/30 | 29/30 | Yes |
| C. ASCII board; each option lists what else is on its lines | 95% | 30/30 | 27/30 | Yes |
| D. Each option says whether it wins or blocks, computed in Python | 100% | 30/30 | 30/30 | No: gives away the answer |
| E. Current format, question spelled out ("win if you can, otherwise block") | 87% | 25/30 | 27/30 | Yes |

The whole run cost about 200k input tokens over roughly 310 requests.

## Findings

- **Jev is reading the board.** 87% against a 25% baseline is not chance.
- **The weak spot is spotting threats.** Most misses are blocks: to see the
  opponent is about to win, Jev has to trace a line across the 2D drawing, cell
  by cell. TypeSafe list this kind of indirection, and counting, among
  [what Jev answers badly](https://pydantic.dev/docs/ai/models/typesafe/#what-jev-answers-badly).
- **Layout matters more than wording.** Spelling out the strategy in the
  question (E) did not help; listing the lines (B) did.
- **Some misses survive every fair format.** The position from the live match
  (`OXO / XX. / .OX`, O to move, must block at 5) is still answered wrong in
  format B. Answers are stable: asked three times, Jev gives the same answer.

## Options, not taken

1. Make the line-by-line layout (B, possibly combined with C) the default. It
   only describes the board, so it stays a fair test, and it would likely help
   language models too.
2. Add an opt-in "hints" mode like D, to measure Jev as an assisted player. It
   should not be the default: computing the tactics measures our code, not the
   model.

For now the observation is unchanged, so results stay comparable with matches
already played.
