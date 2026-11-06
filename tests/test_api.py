"""The REST API."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx2
import pytest
from fastapi import FastAPI

from ludotastic.api import mount_api
from ludotastic.service import MatchService


@pytest.fixture
async def client(service: MatchService) -> AsyncIterator[httpx2.AsyncClient]:
    app = FastAPI()
    mount_api(app, service)
    transport = httpx2.ASGITransport(app)
    async with httpx2.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        yield client


async def wait_for_turn(
    client: httpx2.AsyncClient, match_id: str, seat: int
) -> dict[str, Any]:
    for _ in range(100):
        view = (await client.get(f"/api/matches/{match_id}")).json()
        if seat in view["to_move"]:
            return view
        await asyncio.sleep(0.01)
    raise AssertionError  # pragma: no cover


async def test_games(client: httpx2.AsyncClient) -> None:
    games = (await client.get("/api/games")).json()
    assert [g["id"] for g in games] == ["2048", "snake", "tictactoe"]
    game = (await client.get("/api/games/tictactoe")).json()
    assert game["bots"] == ["random", "minimax"]
    assert "cell" in game["action_schema"]["properties"]
    assert (await client.get("/api/games/nope")).status_code == 404


async def test_play_through_the_api(client: httpx2.AsyncClient) -> None:
    response = await client.post(
        "/api/matches",
        json={
            "game_id": "tictactoe",
            "players": [{"kind": "human"}, {"kind": "bot", "bot": "minimax"}],
            "seed": 1,
        },
    )
    assert response.status_code == 201
    match_id = response.json()["id"]
    view = await wait_for_turn(client, match_id, 0)
    assert len(view["legal_actions"]["0"]) == 9
    assert [m["id"] for m in (await client.get("/api/matches")).json()] == [match_id]

    url = f"/api/matches/{match_id}/seats/0/action"
    assert (await client.post(url, json={"cell": 4})).status_code == 200
    assert (await client.post(url, json={"cell": 4})).status_code == 409
    seat_1 = f"/api/matches/{match_id}/seats/1/action"
    assert (await client.post(seat_1, json={"cell": 0})).status_code == 403
    seat_9 = f"/api/matches/{match_id}/seats/9/action"
    assert (await client.post(seat_9, json={"cell": 0})).status_code == 404

    view = await wait_for_turn(client, match_id, 0)
    assert view["state"]["board"][4] == "X"
    assert len(view["history"]) == 2

    assert (await client.delete(f"/api/matches/{match_id}")).status_code == 204
    await asyncio.sleep(0.01)
    record = (await client.get(f"/api/history/{match_id}")).json()
    assert record["status"] == "aborted"
    assert (await client.get("/api/history")).json()[0]["id"] == match_id


async def test_bot_match_and_stats(
    client: httpx2.AsyncClient, service: MatchService
) -> None:
    response = await client.post(
        "/api/matches",
        json={
            "game_id": "tictactoe",
            "players": [{"kind": "bot", "bot": "minimax"}, {"kind": "bot"}],
        },
    )
    match = service.get(response.json()["id"])
    assert match is not None
    await match.start()
    view = (await client.get(f"/api/matches/{match.id}")).json()
    assert view["status"] == "finished"
    assert view["scores"] is not None
    stats = (await client.get("/api/stats", params={"game_id": "tictactoe"})).json()
    assert {s["group"] for s in stats} == {"bot:minimax", "bot:random"}


async def test_errors(client: httpx2.AsyncClient) -> None:
    assert (await client.get("/api/matches/nope")).status_code == 404
    assert (await client.get("/api/history/nope")).status_code == 404
    unknown = {"game_id": "nope", "players": [{"kind": "bot"}]}
    assert (await client.post("/api/matches", json=unknown)).status_code == 404
    bad_bot = {"game_id": "tictactoe", "players": [{"kind": "bot", "bot": "x"}] * 2}
    assert (await client.post("/api/matches", json=bad_bot)).status_code == 422
    too_many = {"game_id": "tictactoe", "players": [{"kind": "bot"}] * 3}
    assert (await client.post("/api/matches", json=too_many)).status_code == 422
