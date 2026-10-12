"""Every place that can reach more than one person's rows is listed here, with a reason
(multi-user plan, section L1).

A session bound to a user (ADR-0029) can't forget a filter. What can still go wrong is the
session itself: an unbound one, a statement that opts out with ``ALL_USERS``, the app's shared
sessions, or raw SQL that skips the ORM's guard. This walks the source for each of those and
fails on any site not listed below, and on any listed site that is gone, so a new one is
reviewed before it lands, like ``test_every_route_is_public_or_owner_only``.
"""

import ast
from pathlib import Path

import training_coach

SRC = Path(training_coach.__file__).parent

ALL = "ALL_USERS"  # ALL_USERS, EVERYONE or the all_users option itself
UNBOUND = "unbound session"  # make_session_factory(...) without a user_id
SHARED = "shared_sessions"  # app.state.shared_sessions: unbound, made once per app
RAW = "raw SQL"  # sqlalchemy text(), .connection(), .connect(), exec_driver_sql()

# (module::function, kind) -> why it may see more than one person.
ALLOWED: dict[tuple[str, str], str] = {
    ("db.session::<module>", ALL): "defines the option",
    ("db.session::_only_this_users_rows", ALL): "the guard itself, reading the option",
    ("services.auth::<module>", ALL): "EVERYONE: sign-in looks up a token before knowing whose",
    ("services.auth::has_passkeys", ALL): "names the user in the query",
    ("services.auth::redeem_link", ALL): "whose link is this; acts on that user only",
    ("services.auth::_live", ALL): "whose session cookie is this",
    ("services.passkeys::<module>", ALL): "EVERYONE: credentials are unique across people",
    ("services.passkeys::sign_in", ALL): "whose passkey is this",
    ("services.mcp_tokens::<module>", ALL): "EVERYONE: tokens are looked up before knowing whose",
    ("services.mcp_tokens::exchange_code", ALL): "whose code is this",
    ("services.mcp_tokens::refresh", ALL): "whose refresh token is this",
    ("services.mcp_tokens::verify", ALL): "whose access token is this",
    ("services.mcp_tokens::_revoke", ALL): "the tokens of one named connection",
    ("services.mcp_tokens::revoke_all", ALL): "/recover: the named user's connections only",
    ("services.ingest_keys::owner_of", ALL): "whose band secret is this",
    # ADR-0058: the guard refuses bulk updates of per-person rows in a bound session, so these
    # opt out and name the person by hand.
    ("services.proposals::propose", ALL): (
        "write-lock touch of one connection, by its id and the bound user's id"
    ),
    ("services.proposals::_claim", ALL): (
        "conditional claim of one proposal, by its token and the bound user's id"
    ),
    ("services.proposals::discard_for", ALL): (
        "revoke (maybe unbound, /recover): one named connection's waiting proposals"
    ),
    ("services.seed::_preflight", ALL): "is this ladder step in anyone's history",
    ("services.seed::_tests_preflight", ALL): "does anyone have results for this test",
    ("services.seed::_versions_preflight", ALL): "does anyone's history use this version",
    ("services.seed::_apply_versions", ALL): "stamps every workout with its plan version",
    ("services.seed::apply_seed", ALL): "gives every person their starting rows, by user id",
    ("services.ai_key::rotate_all", ALL): "re-seals every person's key with a new app key",
    ("api.app::create_app", UNBOUND): "app.state.shared_sessions, for the lookups below",
    ("api.app::create_app", SHARED): "made once here",
    ("api.app::create_app.lifespan", UNBOUND): "links the owner at start-up (users.link_owner)",
    ("api.account::erase_my_data", UNBOUND): "erase deletes and recreates the user row (ADR-0044)",
    ("api.auth::_shared", SHARED): "sign-in: whose cookie or link is this",
    ("api.passkeys::_shared", SHARED): "passkey sign-in: whose credential is this",
    ("api.oauth::_shared", SHARED): "OAuth runs before anyone is known",
    ("api.ingest::health_connect", SHARED): "whose band secret is this",
    ("api.mcp::connection", SHARED): "whose bearer token is this",
    ("__main__::seed", UNBOUND): "the seed command: shared plan rows and everyone's start",
    ("__main__::rotate_secrets", UNBOUND): "re-seals every person's AI key",
    ("services.backup::create", RAW): "sqlite3's backup API copies the whole file",
}


def _module(path: Path) -> str:
    return ".".join(path.relative_to(SRC).with_suffix("").parts)


class _Finder(ast.NodeVisitor):
    def __init__(self, module: str) -> None:
        self.module = module
        self.scope: list[str] = []
        self.texts: set[str] = set()  # local names bound to sqlalchemy's text()
        self.found: set[tuple[str, str]] = set()

    def _hit(self, kind: str) -> None:
        self.found.add((f"{self.module}::{'.'.join(self.scope) or '<module>'}", kind))

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            self.scope.append(node.name)
            super().generic_visit(node)
            self.scope.pop()
        else:
            super().generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if (node.module or "").startswith("sqlalchemy"):
            self.texts |= {a.asname or a.name for a in node.names if a.name == "text"}

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in {"ALL_USERS", "EVERYONE"} and isinstance(node.ctx, ast.Load):
            self._hit(ALL)

    def visit_Constant(self, node: ast.Constant) -> None:
        if node.value == "all_users":
            self._hit(ALL)

    def visit_keyword(self, node: ast.keyword) -> None:
        if node.arg == "all_users":
            self._hit(ALL)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == "shared_sessions":
            self._hit(SHARED)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name == "make_session_factory":
            user = next((k.value for k in node.keywords if k.arg == "user_id"), None)
            unset = user is None or (isinstance(user, ast.Constant) and user.value is None)
            if len(node.args) < 2 and unset:
                self._hit(UNBOUND)
        if isinstance(func, ast.Attribute) and name in {"connection", "connect", "exec_driver_sql"}:
            self._hit(RAW)
        if (isinstance(func, ast.Name) and name in self.texts) or (
            isinstance(func, ast.Attribute) and name == "text" and _is_sqlalchemy(func.value)
        ):
            self._hit(RAW)
        self.generic_visit(node)


def _is_sqlalchemy(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and node.id in {"sqlalchemy", "sa"}


def cross_user_sites() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for path in sorted(SRC.rglob("*.py")):
        finder = _Finder(_module(path))
        finder.visit(ast.parse(path.read_text(encoding="utf-8")))
        found |= finder.found
    return found


def test_every_cross_user_site_is_reviewed() -> None:
    found = cross_user_sites()
    new = sorted(found - ALLOWED.keys())
    gone = sorted(ALLOWED.keys() - found)
    assert not new, f"review and list these (can they see another person's rows?): {new}"
    assert not gone, f"listed but no longer in the code, remove them: {gone}"
    assert all(ALLOWED.values()), "every entry says why"


def test_the_finder_sees_each_kind() -> None:
    """The walk itself: one example of each kind, and lookalikes it must ignore."""
    source = """
from sqlalchemy import text as raw
from training_coach.db.session import ALL_USERS

def f(engine, user, s):
    s.scalars(q, execution_options={ALL_USERS: True})
    make_session_factory(engine)
    make_session_factory(engine, user_id=None)
    request.app.state.shared_sessions
    s.connection()
    raw("select 1")

def g(engine, user, message):
    make_session_factory(engine, user_id=user)
    make_session_factory(engine, user)
    message.reply_text("hi")
    text("not sqlalchemy's")
"""
    finder = _Finder("m")
    finder.visit(ast.parse(source))
    assert finder.found == {("m::f", ALL), ("m::f", UNBOUND), ("m::f", SHARED), ("m::f", RAW)}
