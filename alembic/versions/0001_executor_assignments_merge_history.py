"""executor assignments and merge history

Revision ID: 0001_exec_merge
Revises:
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_exec_merge"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    ticket_columns = {
        column["name"]
        for column in inspector.get_columns("tickets")
    }

    if "assigned_executor_id" not in ticket_columns:

        op.add_column(
            "tickets",
            sa.Column(
                "assigned_executor_id",
                sa.Integer(),
                nullable=True
            )
        )

        op.create_foreign_key(
            "fk_tickets_assigned_executor_id_users",
            "tickets",
            "users",
            ["assigned_executor_id"],
            ["id"]
        )

    tables = set(inspector.get_table_names())

    if "ticket_merge_history" in tables:
        return

    op.create_table(
        "ticket_merge_history",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("primary_ticket_id", sa.Integer(), nullable=False),
        sa.Column("secondary_ticket_id", sa.Integer(), nullable=False),
        sa.Column("merged_by_user_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["primary_ticket_id"],
            ["tickets.id"]
        ),
        sa.ForeignKeyConstraint(
            ["secondary_ticket_id"],
            ["tickets.id"]
        ),
        sa.ForeignKeyConstraint(
            ["merged_by_user_id"],
            ["users.id"]
        ),
    )

    op.create_index(
        "ix_ticket_merge_history_id",
        "ticket_merge_history",
        ["id"]
    )

    op.create_index(
        "ix_ticket_merge_history_primary_ticket_id",
        "ticket_merge_history",
        ["primary_ticket_id"]
    )

    op.create_index(
        "ix_ticket_merge_history_secondary_ticket_id",
        "ticket_merge_history",
        ["secondary_ticket_id"]
    )

    op.create_index(
        "ix_ticket_merge_history_merged_by_user_id",
        "ticket_merge_history",
        ["merged_by_user_id"]
    )


def downgrade():

    op.drop_index(
        "ix_ticket_merge_history_merged_by_user_id",
        table_name="ticket_merge_history"
    )
    op.drop_index(
        "ix_ticket_merge_history_secondary_ticket_id",
        table_name="ticket_merge_history"
    )
    op.drop_index(
        "ix_ticket_merge_history_primary_ticket_id",
        table_name="ticket_merge_history"
    )
    op.drop_index(
        "ix_ticket_merge_history_id",
        table_name="ticket_merge_history"
    )
    op.drop_table("ticket_merge_history")
    op.drop_constraint(
        "fk_tickets_assigned_executor_id_users",
        "tickets",
        type_="foreignkey"
    )
    op.drop_column("tickets", "assigned_executor_id")
