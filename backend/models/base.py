"""
Finance Controller — SQLAlchemy Base
=====================================

Declarative base class shared by all models.
Import ``Base`` from here in every model file.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass
