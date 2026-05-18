"""Admin CLI — instance management commands.

Usage:
    uv run python -m app.admin_cli create-admin --email TEXT --password TEXT
    uv run python -m app.admin_cli promote-admin --email TEXT
    uv run python -m app.admin_cli demote-admin  --email TEXT

Requires a running database (DATABASE_URL env var or .env file).
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import click
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    from app.config import get_settings

    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _run(coro: Any) -> None:  # noqa: ANN401
    asyncio.run(coro)


@click.group()
def cli() -> None:
    """WDIAG instance administration."""


@cli.command("create-admin")
@click.option("--email", required=True, help="Admin email address.")
@click.option("--password", required=True, help="Admin password (min 8 chars).")
def create_admin(email: str, password: str) -> None:
    """Create an admin user, or promote + reset password if already exists."""
    _run(_create_admin(email, password))


async def _create_admin(email: str, password: str) -> None:
    from app.households import service
    from app.households.models import User
    from app.security import password as pwd_service

    factory = _get_session_factory()
    async with factory() as session:
        stmt = sa.select(User).where(User.email == email.lower())
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.is_app_admin = True
            existing.password_hash = pwd_service.hash_password(password)
            await session.commit()
            click.echo(f"Promoted and reset password for: {existing.email}")
        else:
            try:
                user = await service.create_user(
                    session,
                    email=email,
                    display_name="Admin",
                    password=password,
                    is_app_admin=True,
                )
                await session.commit()
                click.echo(f"Admin created: {user.email}")
            except service.ConflictError as exc:
                click.echo(f"Error: {exc}", err=True)
                sys.exit(1)


@cli.command("promote-admin")
@click.option("--email", required=True, help="Email of user to promote.")
def promote_admin(email: str) -> None:
    """Set is_app_admin=True on an existing user."""
    _run(_promote_admin(email))


async def _promote_admin(email: str) -> None:
    from app.households.models import User

    factory = _get_session_factory()
    async with factory() as session:
        stmt = sa.select(User).where(User.email == email.lower())
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            click.echo(f"No user found with email: {email}", err=True)
            sys.exit(1)
        user.is_app_admin = True
        await session.commit()
        click.echo(f"Promoted to admin: {user.email}")


@cli.command("demote-admin")
@click.option("--email", required=True, help="Email of admin to demote.")
def demote_admin(email: str) -> None:
    """Set is_app_admin=False. Blocked if this is the last admin."""
    _run(_demote_admin(email))


async def _demote_admin(email: str) -> None:
    from app.households.models import User

    factory = _get_session_factory()
    async with factory() as session:
        stmt = sa.select(User).where(User.email == email.lower())
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            click.echo(f"No user found with email: {email}", err=True)
            sys.exit(1)

        if not user.is_app_admin:
            click.echo(f"{email} is not an admin.", err=True)
            sys.exit(1)

        admin_count_result = await session.execute(
            sa.select(sa.func.count()).select_from(User).where(User.is_app_admin.is_(True))
        )
        admin_count: int = admin_count_result.scalar_one()

        if admin_count <= 1:
            click.echo(
                "Cannot demote: this is the last admin account. Promote another user first.",
                err=True,
            )
            sys.exit(1)

        user.is_app_admin = False
        await session.commit()
        click.echo(f"Demoted from admin: {user.email}")


if __name__ == "__main__":
    cli()
