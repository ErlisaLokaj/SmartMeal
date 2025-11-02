"""
Shared test helpers and utilities.
"""

import uuid


def unique_email(prefix: str = "test") -> str:
    """
    Generate unique email address using UUID to avoid conflicts.

    This prevents "User with email X already exists" errors when
    tests run multiple times against the same database.

    Args:
        prefix: Prefix for the email address (default: "test")

    Returns:
        Unique email address in format: prefix-uuid@example.com

    Example:
        >>> email = unique_email("user")
        >>> # Returns something like: "user-a1b2c3d4-e5f6-7890-abcd-ef1234567890@example.com"
    """
    return f"{prefix}-{uuid.uuid4()}@example.com"
