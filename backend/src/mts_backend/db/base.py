"""Declarative base shared by the MVP business modules."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
