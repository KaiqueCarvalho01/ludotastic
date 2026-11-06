<div align="center" markdown="1">

  [![Discord][badge-chat]][chat]
  <br>
  <br>

  | | ![Badges][label-badges] |
  |:-|:-|
  | ![Build][label-build] | [![Nox][badge-actions]][actions] [![semantic-release][badge-semantic-release]][semantic-release] [![PyPI][badge-pypi]][pypi] [![Read the Docs][badge-docs]][docs] |
  | ![Tests][label-tests] | [![coverage][badge-coverage]][coverage] [![pre-commit][badge-pre-commit]][pre-commit] |
  | ![Standards][label-standards] | [![SemVer 2.0.0][badge-semver]][semver] [![Conventional Commits][badge-conventional-commits]][conventional-commits] |
  | ![Code][label-code] | [![uv][badge-uv]][uv] [![Ruff][badge-ruff]][ruff] [![Nox][badge-nox]][nox] [![ty][badge-ty]][ty] |
  | ![Repo][label-repo] | [![GitHub issues][badge-issues]][issues] [![GitHub stars][badge-stars]][stars] [![GitHub license][badge-license]][license] [![All Contributors][badge-all-contributors]][contributors] [![Contributor Covenant][badge-code-of-conduct]][code-of-conduct] |
</div>

<!-- Badges -->
[badge-chat]: https://img.shields.io/badge/dynamic/json?color=green&label=chat&query=%24.approximate_presence_count&suffix=%20online&logo=discord&style=flat-square&url=https%3A%2F%2Fdiscord.com%2Fapi%2Fv10%2Finvites%2FYe9yJtZQuN%3Fwith_counts%3Dtrue
[chat]: https://discord.gg/Ye9yJtZQuN

<!-- Labels -->
[label-badges]: https://img.shields.io/badge/%F0%9F%94%96-badges-purple?style=for-the-badge
[label-build]: https://img.shields.io/badge/%F0%9F%94%A7-build-darkblue?style=flat-square
[label-tests]: https://img.shields.io/badge/%F0%9F%A7%AA-tests-darkblue?style=flat-square
[label-standards]: https://img.shields.io/badge/%F0%9F%93%91-standards-darkblue?style=flat-square
[label-code]: https://img.shields.io/badge/%F0%9F%92%BB-code-darkblue?style=flat-square
[label-repo]: https://img.shields.io/badge/%F0%9F%93%81-repo-darkblue?style=flat-square

<!-- Build -->
[badge-actions]: https://img.shields.io/github/actions/workflow/status/MicaelJarniac/ludotastic/ci.yml?branch=main&style=flat-square
[actions]: https://github.com/MicaelJarniac/ludotastic/actions
[badge-semantic-release]: https://img.shields.io/badge/%20%20%F0%9F%93%A6%F0%9F%9A%80-semantic--release-e10079?style=flat-square
[semantic-release]: https://github.com/semantic-release/semantic-release
[badge-pypi]: https://img.shields.io/pypi/v/ludotastic?style=flat-square
[pypi]: https://pypi.org/project/ludotastic
[badge-docs]: https://img.shields.io/readthedocs/ludotastic?style=flat-square
[docs]: https://ludotastic.readthedocs.io

<!-- Tests -->
[badge-coverage]: https://img.shields.io/codecov/c/gh/MicaelJarniac/ludotastic?logo=codecov&style=flat-square
[coverage]: https://codecov.io/gh/MicaelJarniac/ludotastic
[badge-pre-commit]: https://img.shields.io/badge/pre--commit-enabled-brightgreen?style=flat-square&logo=pre-commit&logoColor=white
[pre-commit]: https://github.com/pre-commit/pre-commit

<!-- Standards -->
[badge-semver]: https://img.shields.io/badge/SemVer-2.0.0-blue?style=flat-square&logo=semver
[semver]: https://semver.org/spec/v2.0.0.html
[badge-conventional-commits]: https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow?style=flat-square
[conventional-commits]: https://conventionalcommits.org

<!-- Code -->
[badge-uv]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json&style=flat-square
[uv]: https://github.com/astral-sh/uv
[badge-ruff]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=flat-square
[ruff]: https://github.com/astral-sh/ruff
[badge-nox]: https://img.shields.io/badge/%F0%9F%A6%8A-Nox-D85E00.svg?style=flat-square
[nox]: https://github.com/wntrblm/nox
[badge-ty]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json&style=flat-square
[ty]: https://github.com/astral-sh/ty

<!-- Repo -->
[badge-issues]: https://img.shields.io/github/issues/MicaelJarniac/ludotastic?style=flat-square
[issues]: https://github.com/MicaelJarniac/ludotastic/issues
[badge-stars]: https://img.shields.io/github/stars/MicaelJarniac/ludotastic?style=flat-square
[stars]: https://github.com/MicaelJarniac/ludotastic/stargazers
[badge-license]: https://img.shields.io/github/license/MicaelJarniac/ludotastic?style=flat-square
[license]: https://github.com/MicaelJarniac/ludotastic/blob/main/LICENSE
<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[badge-all-contributors]: https://img.shields.io/badge/all_contributors-0-orange.svg?style=flat-square
<!-- ALL-CONTRIBUTORS-BADGE:END -->
[contributors]: #Contributors-✨
[badge-code-of-conduct]: https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa?style=flat-square
[code-of-conduct]: CODE_OF_CONDUCT.md
<!---->

# Ludotastic

Welcome to **Ludotastic's** documentation!

Where humans and AI come to play.

[Read the Docs][docs]

## Installation

### PyPI
[*ludotastic*][pypi] is available on PyPI:

```bash
# With uv
uv add ludotastic
# With pip
pip install ludotastic
# With Poetry
poetry add ludotastic
```

### GitHub
You can also install the latest version of the code directly from GitHub:
```bash
# With uv
uv add git+https://github.com/MicaelJarniac/ludotastic
# With pip
pip install git+git://github.com/MicaelJarniac/ludotastic
# With Poetry
poetry add git+git://github.com/MicaelJarniac/ludotastic
```

## Usage
Ludotastic is a playground for pitting people, scripted bots and AI models
against each other in games. Any model [Pydantic AI][pydantic-ai] supports can
play, including decision models such as TypeSafe's
[Jev][jev] (`typesafe:jev-latest`).

Set the API keys for the models you want to use, such as `TYPESAFE_API_KEY` or
`OPENAI_API_KEY`, then start the playground:

```bash
ludotastic serve
```

Open <http://127.0.0.1:8080> to set up and watch matches, browse past matches
and compare results. The REST API lives under `/api`, documented at `/docs`.

Matches can also run headless, which is handy for comparing models:

```bash
ludotastic games
ludotastic play tictactoe typesafe:jev-latest bot:minimax --rounds 10
ludotastic play tictactoe openai:gpt-6.1-sol@structured anthropic:claude-opus-5-5@tools
```

Each player is `bot:NAME`, or a model name with an optional action mode:

- `@choice`: pick one of the legal moves, each described in words. The model can
  never make an illegal move, and this mode suits decision models best.
- `@structured`: fill in the game's move model. Illegal moves go back to the
  model for another try.
- `@tools`: look at the game through tools, then submit a move.

Settings come from `LUDOTASTIC_*` environment variables or a `.env` file; see
[`Settings`][ludotastic.Settings].

### Writing a game
A game is a [`Game`][ludotastic.Game] subclass whose states and moves are
Pydantic models. Ludotastic finds games through the `ludotastic.games` entry
point group, so a game can ship in its own package:

```toml
[project.entry-points."ludotastic.games"]
connect-four = "ludotastic_connect_four:ConnectFour"
```

The bundled games, such as [Tic-Tac-Toe][tictactoe], are registered the same way
and make good templates. A game can also provide its own scripted bots, extra AI
tools and a NiceGUI renderer; games without one get a generic text view. Games
are turn-based (`Timing.STEP`) or real-time (`Timing.TICK`), where a player that
is too slow on a tick loses its turn.

How a game describes its state in [`observe`][ludotastic.Game.observe] affects
how well models play it, sometimes a lot: see the
[Tic-Tac-Toe notes](notes/tictactoe-observation.md) for a measured example.

[pydantic-ai]: https://ai.pydantic.dev
[jev]: https://pydantic.dev/docs/ai/models/typesafe/
[tictactoe]: https://github.com/MicaelJarniac/ludotastic/tree/main/src/ludotastic/games/tictactoe

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

More details can be found in [CONTRIBUTING](CONTRIBUTING.md).

## Contributors ✨
<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

## License
[MIT](../LICENSE)

This project was created with the [MicaelJarniac/crustypy](https://github.com/MicaelJarniac/crustypy) template.
