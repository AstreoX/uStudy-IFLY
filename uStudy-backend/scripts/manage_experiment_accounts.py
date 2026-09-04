"""Create or import password-protected experiment accounts.

Generated accounts receive permanent ALPHA access. Existing accounts can be assigned a
read-only teacher role in the fixed course. Plaintext passwords are only written to an
operator-selected CSV path outside the repository.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import re
import secrets
import string
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, or_, select

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.security import hash_password  # noqa: E402
from db.database import get_scoped_session  # noqa: E402
from db.models import SpaceMember, SpaceMemberRole, SubscriptionTier, User  # noqa: E402
from experiment.default_course import (  # noqa: E402
    DEFAULT_SPACE_ID,
    ensure_default_space_membership,
)


USERNAME_RE = re.compile(r"^[a-z][a-z0-9_-]{2,31}$")
PREFIX_RE = re.compile(r"^[a-z][a-z0-9_-]{0,28}$")
PASSWORD_PUNCTUATION = "!@#$%_-"


@dataclass(frozen=True)
class AccountInput:
    username: str
    password: str
    nickname: str


def normalize_username(value: str) -> str:
    username = value.strip().lower()
    if not USERNAME_RE.fullmatch(username):
        raise ValueError(
            "username must start with a letter and contain 3-32 lowercase "
            "letters, digits, underscores, or hyphens"
        )
    return username


def generate_password(length: int = 16) -> str:
    if length < 12:
        raise ValueError("generated passwords must be at least 12 characters")
    chars = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(PASSWORD_PUNCTUATION),
    ]
    alphabet = string.ascii_letters + string.digits + PASSWORD_PUNCTUATION
    chars.extend(secrets.choice(alphabet) for _ in range(length - len(chars)))
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def ensure_output_outside_repo(output_path: Path) -> Path:
    resolved = output_path.expanduser().resolve()
    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved
    raise ValueError("plaintext account CSV must be written outside the repository")


def generated_inputs(prefix: str, count: int, password_length: int) -> list[AccountInput]:
    if count < 1:
        raise ValueError("count must be positive")
    normalized_prefix = prefix.strip().lower()
    if not PREFIX_RE.fullmatch(normalized_prefix):
        raise ValueError("prefix must start with a letter and contain safe username characters")
    width = max(3, len(str(count)))
    return [
        AccountInput(
            username=normalize_username(f"{normalized_prefix}{index:0{width}d}"),
            password=generate_password(password_length),
            nickname=f"实验账号 {index:0{width}d}",
        )
        for index in range(1, count + 1)
    ]


def imported_inputs(csv_path: Path) -> list[AccountInput]:
    rows: list[AccountInput] = []
    with csv_path.expanduser().resolve().open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"username", "password"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("input CSV must contain username and password columns")
        for line_number, row in enumerate(reader, start=2):
            username = normalize_username(row.get("username", ""))
            password = (row.get("password") or "").strip()
            if len(password) < 8:
                raise ValueError(f"line {line_number}: password must be at least 8 characters")
            nickname = (row.get("nickname") or username).strip()[:100]
            rows.append(AccountInput(username, password, nickname))
    if not rows:
        raise ValueError("input CSV contains no accounts")
    return rows


async def apply_accounts(
    accounts: list[AccountInput],
    *,
    reset_existing: bool,
) -> tuple[list[AccountInput], list[str]]:
    changed: list[AccountInput] = []
    skipped: list[str] = []
    async with get_scoped_session() as db:
        for account in accounts:
            result = await db.execute(
                select(User).where(func.lower(User.username) == account.username)
            )
            user = result.scalar_one_or_none()
            if user is not None and not reset_existing:
                await ensure_default_space_membership(db, user.id)
                skipped.append(account.username)
                continue

            if user is None:
                user = User(
                    username=account.username,
                    email=f"{account.username}@experiment.invalid",
                    nickname=account.nickname,
                    password_hash=hash_password(account.password),
                    subscription_tier=SubscriptionTier.ALPHA,
                    subscription_expires_at=None,
                )
                db.add(user)
            else:
                user.nickname = account.nickname
                user.password_hash = hash_password(account.password)
                user.subscription_tier = SubscriptionTier.ALPHA
                user.subscription_expires_at = None
            await db.flush()
            await ensure_default_space_membership(db, user.id)
            changed.append(account)
        await db.commit()
    return changed, skipped


async def set_course_role(identifier: str, role: str) -> User:
    """Assign a pre-provisioned account's role in the fixed course."""
    normalized = identifier.strip().lower()
    if not normalized:
        raise ValueError("identifier is required")
    try:
        target_role = SpaceMemberRole(role)
    except ValueError as exc:
        raise ValueError("role must be teacher or member") from exc
    if target_role not in {SpaceMemberRole.TEACHER, SpaceMemberRole.MEMBER}:
        raise ValueError("role must be teacher or member")

    async with get_scoped_session() as db:
        user = await db.scalar(
            select(User).where(
                or_(
                    func.lower(User.username) == normalized,
                    func.lower(User.email) == normalized,
                )
            )
        )
        if user is None:
            raise ValueError(f"account not found: {identifier}")
        if not await ensure_default_space_membership(db, user.id):
            raise ValueError("default Data Structures course is not initialized")
        member = await db.scalar(
            select(SpaceMember).where(
                SpaceMember.space_id == DEFAULT_SPACE_ID,
                SpaceMember.user_id == user.id,
            )
        )
        if member is None:
            raise ValueError("default course membership could not be created")
        member.role = target_role
        member.can_edit_graph = False
        await db.commit()
        return user


def write_credentials(output_path: Path, accounts: list[AccountInput]) -> None:
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["username", "password", "nickname"])
        writer.writeheader()
        for account in accounts:
            writer.writerow(
                {
                    "username": account.username,
                    "password": account.password,
                    "nickname": account.nickname,
                }
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset-existing",
        action="store_true",
        help="reset passwords and ALPHA access for existing usernames",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="generate numbered accounts")
    generate.add_argument("--prefix", default="exp", help="username prefix")
    generate.add_argument("--count", type=int, required=True)
    generate.add_argument("--password-length", type=int, default=16)
    generate.add_argument("--output", type=Path, required=True)

    import_csv = subparsers.add_parser("import", help="import accounts from CSV")
    import_csv.add_argument("--input", type=Path, required=True)
    import_csv.add_argument(
        "--output",
        type=Path,
        help="optional outside-repository CSV containing changed credentials",
    )
    set_role = subparsers.add_parser(
        "set-role", help="assign teacher or member role in the fixed course"
    )
    set_role.add_argument(
        "--identifier", required=True, help="existing username or email"
    )
    set_role.add_argument(
        "--role", required=True, choices=["teacher", "member"]
    )
    return parser


async def async_main(args: argparse.Namespace) -> int:
    if args.command == "set-role":
        user = await set_course_role(args.identifier, args.role)
        label = user.username or user.email
        print(f"Updated course role: {label} -> {args.role}")
        return 0

    if args.command == "generate":
        accounts = generated_inputs(args.prefix, args.count, args.password_length)
        output = ensure_output_outside_repo(args.output)
    else:
        accounts = imported_inputs(args.input)
        output = ensure_output_outside_repo(args.output) if args.output else None

    changed, skipped = await apply_accounts(
        accounts,
        reset_existing=args.reset_existing,
    )
    if output is not None:
        write_credentials(output, changed)
        print(f"Credentials written to: {output}")
    print(f"Created or updated: {len(changed)}")
    print(f"Skipped existing: {len(skipped)}")
    if skipped:
        print("Skipped usernames: " + ", ".join(skipped))
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(async_main(args))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
