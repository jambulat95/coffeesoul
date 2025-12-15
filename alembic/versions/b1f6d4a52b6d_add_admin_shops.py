"""Add admin_shops table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1f6d4a52b6d"
down_revision: Union[str, Sequence[str], None] = "29ea4810d821"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "admin_shops",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("admin_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("shop_name", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "admin_tg_id",
            "shop_name",
            name="uq_admin_shops_admin_shop",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("admin_shops")

