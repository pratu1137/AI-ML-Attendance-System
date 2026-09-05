"""add lecture schedule integrity constraints

Revision ID: 8f2d6a1c4e90
Revises: 5dbad95cc15b
"""

from alembic import op


revision = "8f2d6a1c4e90"
down_revision = "5dbad95cc15b"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("lectures") as batch_op:
        batch_op.create_unique_constraint(
            "uq_lecture_schedule",
            ["subject_id", "faculty_id", "lecture_date", "start_time", "end_time"],
        )
        batch_op.create_check_constraint("ck_lecture_time_order", "start_time < end_time")


def downgrade():
    with op.batch_alter_table("lectures") as batch_op:
        batch_op.drop_constraint("ck_lecture_time_order", type_="check")
        batch_op.drop_constraint("uq_lecture_schedule", type_="unique")
