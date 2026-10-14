"""Explicit local demo-account command; existing passwords are never reset."""

import argparse
import asyncio
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mts_backend.auth.passwords import hash_password
from mts_backend.core.config import get_settings
from mts_backend.db.models import Organization, User
from mts_backend.db.readiness import build_engine


async def seed(password: str) -> int:
    if len(password) < 12:
        raise ValueError("Demo password must contain at least 12 characters.")
    engine = build_engine(get_settings())
    created = 0
    try:
        async with AsyncSession(engine) as db, db.begin():
            organization = await db.scalar(
                select(Organization).where(Organization.name == "MVP demo")
            )
            if organization is None:
                organization = Organization(name="MVP demo")
                db.add(organization)
                await db.flush()
            for login, name in [("demo", "Демо менеджер"), ("demo2", "Второй менеджер")]:
                existing = await db.scalar(select(User).where(User.login == login))
                if existing is None:
                    db.add(
                        User(
                            organization_id=organization.id,
                            login=login,
                            display_name=name,
                            password_hash=hash_password(password),
                        )
                    )
                    created += 1
    finally:
        await engine.dispose()
    return created


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create demo and demo2 explicitly; no password reset."
    )
    parser.add_argument("--password-env", default="MTS_DEMO_PASSWORD")
    arguments = parser.parse_args()
    password = os.environ.get(arguments.password_env)
    if not password:
        parser.error(f"Set {arguments.password_env}; credentials are never printed.")
    try:
        count = asyncio.run(seed(password))
    except ValueError:
        parser.error("Demo password must contain at least 12 characters.")
    print(f"Demo users created: {count}; existing users preserved.")


if __name__ == "__main__":
    main()
