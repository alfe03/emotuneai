"""add spotify columns to users

Revision ID: a51ce20688d6
Revises: 1859552e116e
Create Date: 2026-06-12 22:31:15.909858

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a51ce20688d6'
down_revision: Union[str, Sequence[str], None] = '1859552e116e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'spotify_access_token' not in columns:
        op.add_column('users', sa.Column('spotify_access_token', sa.String(), nullable=True))
    if 'spotify_refresh_token' not in columns:
        op.add_column('users', sa.Column('spotify_refresh_token', sa.String(), nullable=True))
    if 'spotify_token_expires_at' not in columns:
        op.add_column('users', sa.Column('spotify_token_expires_at', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'spotify_token_expires_at')
    op.drop_column('users', 'spotify_refresh_token')
    op.drop_column('users', 'spotify_access_token')
