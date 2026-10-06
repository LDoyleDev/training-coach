from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests.bot.fakes import OWNER, SETTINGS, STRANGER, button_data, command, press, run, texts
from training_coach.bot import buttons
from training_coach.bot.app import Handlers
from training_coach.bot.messages import STALE
from training_coach.db.models import PlanState, SessionTemplate, Workout
from training_coach.domain.enums import WorkoutStatus

App = Application  # type: ignore[type-arg]  # see build_bot
Sessions = sessionmaker[Session]


def _pointer(sessions: Sessions) -> int:
    with sessions() as session:
        state = session.get(PlanState, 1)
        assert state is not None
        assert state.next_template_id is not None
        return state.next_template_id


def _templates(sessions: Sessions) -> list[tuple[int, str, bool]]:
    with sessions() as session:
        rows = session.execute(
            select(
                SessionTemplate.id, SessionTemplate.name, SessionTemplate.is_rest_optional
            ).order_by(SessionTemplate.position)
        )
        return [(i, n, o) for i, n, o in rows]


def _workouts(sessions: Sessions) -> list[tuple[int | None, str]]:
    with sessions() as session:
        return [(w.template_id, w.status) for w in session.scalars(select(Workout))]


# ------------------------------------------------------------------ parsing


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ("q:rest:5", buttons.Press("rest", 5)),
        ("q:pick:5:9", buttons.Press("pick", 5, 9)),
        ("q:rest", None),
        ("q:dance:5", None),
        ("x:rest:5", None),
        ("q:rest:five", None),
        ("q:pick:5:9:1", None),
        ("q:rest:0", None),
        ("q:rest:-3", None),
        ("q:rest:99999999999999999999", None),
        (None, None),
    ],
)
def test_parse(data: str | None, expected: buttons.Press | None) -> None:
    assert buttons.parse(data) == expected


def test_pick_menu_leaves_out_the_offered_session() -> None:
    markup = buttons.pick(2, [(1, "Legs"), (2, "Zone 2"), (3, "Upper")])
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert labels == ["Legs", "Upper", "Back"]


# ------------------------------------------------------------------ through the bot


async def test_today_carries_the_buttons(application: App, seeded: Sessions) -> None:
    tid = _pointer(seeded)
    calls = await run(application, command("/today", OWNER))
    assert button_data(calls["sendMessage"][0]) == [
        f"q:start:{tid}",
        f"q:rest:{tid}",
        f"q:swap:{tid}",
    ]


async def test_morning_message_carries_the_buttons(seeded: Sessions) -> None:
    bot = AsyncMock()
    await Handlers(SETTINGS, seeded).morning(type("Ctx", (), {"bot": bot})())  # type: ignore[arg-type]
    markup = bot.send_message.await_args.kwargs["reply_markup"]
    assert markup == buttons.morning(_pointer(seeded))


@pytest.mark.parametrize(
    "data",
    ["start", "rest", "swap", "next", "push", "pickmenu", "back", "pick", "dance", "junk"],
)
async def test_strangers_presses_do_nothing(application: App, seeded: Sessions, data: str) -> None:
    """Threat model T1 for buttons: no answer, no message, no change, even for bad data."""
    tid = _pointer(seeded)
    payload = {"pick": f"q:pick:{tid}:{tid + 1}", "junk": "not-a-button"}.get(
        data, f"q:{data}:{tid}"
    )
    calls = await run(application, press(payload, STRANGER))
    assert calls == {}
    assert _workouts(seeded) == []


async def test_start_shows_the_full_session(application: App, seeded: Sessions) -> None:
    calls = await run(application, press(f"q:start:{_pointer(seeded)}", OWNER))
    (text,) = texts(calls)
    assert text.endswith("Log it when you're done.")
    assert "editMessageReplyMarkup" not in calls  # Start keeps the buttons


async def test_rest_holds_a_training_session_and_retires_the_buttons(
    application: App, seeded: Sessions
) -> None:
    tid = _pointer(seeded)
    calls = await run(application, press(f"q:rest:{tid}", OWNER))
    (text,) = texts(calls)
    assert "moves to tomorrow" in text
    assert button_data(calls["editMessageReplyMarkup"][0]) == []
    assert _workouts(seeded) == [(tid, WorkoutStatus.SKIPPED)]
    assert _pointer(seeded) == tid


async def test_swap_opens_the_choices(application: App, seeded: Sessions) -> None:
    tid = _pointer(seeded)
    calls = await run(application, press(f"q:swap:{tid}", OWNER))
    assert button_data(calls["editMessageReplyMarkup"][0]) == [
        f"q:next:{tid}",
        f"q:pickmenu:{tid}",
        f"q:push:{tid}",
        f"q:back:{tid}",
    ]
    back = await run(application, press(f"q:back:{tid}", OWNER))
    assert button_data(back["editMessageReplyMarkup"][0])[0] == f"q:start:{tid}"


async def test_do_the_next_one_first(application: App, seeded: Sessions) -> None:
    (first, _, _), (second, second_name, _) = _templates(seeded)[:2]
    calls = await run(application, press(f"q:next:{first}", OWNER))
    (text,) = texts(calls)
    assert text.startswith(f"{second_name}: ")
    assert button_data(calls["sendMessage"][0])[0] == f"q:start:{second}"
    assert _pointer(seeded) == second


async def test_pick_another_keeps_the_queue(application: App, seeded: Sessions) -> None:
    (first, first_name, _), _, (third, third_name, _) = _templates(seeded)[:3]
    menu = await run(application, press(f"q:pickmenu:{first}", OWNER))
    assert f"q:pick:{first}:{third}" in button_data(menu["editMessageReplyMarkup"][0])
    calls = await run(application, press(f"q:pick:{first}:{third}", OWNER))
    (text,) = texts(calls)
    assert text.startswith(f"{third_name}: ")
    assert text.endswith(f"{first_name} is still next in the plan.")
    assert _pointer(seeded) == first


async def test_push_to_tomorrow(application: App, seeded: Sessions) -> None:
    tid = _pointer(seeded)
    (text,) = texts(await run(application, press(f"q:push:{tid}", OWNER)))
    assert "moves to tomorrow" in text
    assert _workouts(seeded) == [(tid, WorkoutStatus.SKIPPED)]


@pytest.mark.parametrize("action", ["rest", "push", "next", "start"])
async def test_a_stale_button_says_so(application: App, seeded: Sessions, action: str) -> None:
    calls = await run(application, press(f"q:{action}:999", OWNER))
    assert texts(calls) == [STALE]
    assert _workouts(seeded) == []


async def test_a_malformed_press_is_only_acknowledged(application: App) -> None:
    calls = await run(application, press("q:dance:1", OWNER))
    assert list(calls) == ["answerCallbackQuery"]
