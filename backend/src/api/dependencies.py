"""Shared API dependencies."""

import os

from fastapi import Header, HTTPException, status


def verify_admin_secret(x_admin_secret: str = Header(default=None)) -> None:
    """Ensure the request carries the correct admin secret header."""
    admin_secret = os.getenv("ADMIN_SECRET")

    if not admin_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_SECRET is not configured",
        )

    if x_admin_secret != admin_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin secret",
        )
