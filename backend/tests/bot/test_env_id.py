"""Nothing in ``bot/`` that answers a person reads the owner's configured Telegram account or the
owner's sessions (ADR-0089). Handlers get the person from the gate (``gate.served``, checked in
test_app.py) and use that person's sessions, and so do the scheduled messages, from the gate
(``Gate.scheduled``). Only the places listed below may. Like
tests/test_cross_user_access.py, a new site fails until it is listed with a reason, and a
listed site that is gone fails too."""

import ast
from pathlib import Path

import training_coach.bot

BOT = Path(training_coach.bot.__file__).parent

ENV_ID = "telegram_allowed_user_id"
OWNERS = "self.sessions"  # a handler class's own sessions: the owner's

ALLOWED: dict[tuple[str, str], str] = {
    ("app::build_bot", ENV_ID): "refuses to start without the owner's account",
    ("gate::Gate._admit", ENV_ID): "a database error is told to the configured account too",
    ("connect::Connect.claim", ENV_ID): "the owner's configured account can't claim a link",
    ("gate::Person.not_open", OWNERS): "a Person's own sessions, bound to them",
    # Checks still sent to the owner's account only (step 9's second part).
    ("band::BandHandlers.announce", OWNERS): "band workouts offered",
    ("band::BandHandlers.announce", ENV_ID): "band workouts offered",
    ("band::BandHandlers.watch", OWNERS): "band data stopped or back",
    ("band::BandHandlers.watch", ENV_ID): "band data stopped or back",
    ("proposals::ProposalHandlers.announce", OWNERS): "an AI's proposals sent out",
    ("proposals::ProposalHandlers.announce", ENV_ID): "an AI's proposals sent out",
    ("notices::NoticeHandlers.tell", OWNERS): "what a release changed in the plan",
    ("notices::NoticeHandlers.tell", ENV_ID): "what a release changed in the plan",
}


class _Finder(ast.NodeVisitor):
    def __init__(self, module: str) -> None:
        self.module = module
        self.scope: list[str] = []
        self.found: set[tuple[str, str]] = set()

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            self.scope.append(node.name)
            super().generic_visit(node)
            self.scope.pop()
        else:
            super().generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        where = f"{self.module}::{'.'.join(self.scope) or '<module>'}"
        if node.attr == ENV_ID:
            self.found.add((where, ENV_ID))
        on_self = isinstance(node.value, ast.Name) and node.value.id == "self"
        if node.attr == "sessions" and on_self and isinstance(node.ctx, ast.Load):
            self.found.add((where, OWNERS))
        self.generic_visit(node)


def _sites() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for path in sorted(BOT.glob("*.py")):
        finder = _Finder(path.stem)
        finder.visit(ast.parse(path.read_text(encoding="utf-8")))
        found |= finder.found
    return found


def test_only_the_listed_places_read_the_owners_account_or_sessions() -> None:
    found = _sites()
    assert sorted(found - ALLOWED.keys()) == [], "list it with a reason, or use the person's"
    assert sorted(ALLOWED.keys() - found) == [], "gone: take it off the list"


def test_the_finder_sees_both_kinds() -> None:
    finder = _Finder("example")
    finder.visit(
        ast.parse(
            "class A:\n"
            "    def f(self):\n"
            "        return self.sessions, self.settings.telegram_allowed_user_id\n"
        )
    )
    assert finder.found == {("example::A.f", OWNERS), ("example::A.f", ENV_ID)}
