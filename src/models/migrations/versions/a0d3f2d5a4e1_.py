"""

Revision ID: a0d3f2d5a4e1
Revises: bd6ef69899bf

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a0d3f2d5a4e1"
down_revision: Union[str, None] = "bd6ef69899bf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("requests", sa.Column("verbose", sa.Text(), nullable=True))
    op.alter_column(
        "requests",
        "response",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        type_=sa.Text(),
        existing_nullable=True,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "requests",
        "response",
        existing_type=sa.Text(),
        type_=postgresql.JSON(astext_type=sa.Text()),
        existing_nullable=True,
    )
    op.drop_column("requests", "verbose")
    # ### end Alembic commands ###
