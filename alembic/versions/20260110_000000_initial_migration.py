"""Initial migration - Create all tables

Revision ID: 001
Revises: 
Create Date: 2026-01-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create subjects table
    op.create_table(
        'subjects',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('icon_name', sa.String(50), nullable=False),
        sa.Column('icon_color', sa.String(20), nullable=False, server_default='#ffffff'),
        sa.Column('did', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('did'),
    )
    op.create_index('ix_subjects_name', 'subjects', ['name'])
    op.create_index('ix_subjects_did', 'subjects', ['did'])
    
    # Create subject_fields table
    op.create_table(
        'subject_fields',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('field_key', sa.String(50), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=False),
        sa.Column('field_description', sa.Text(), nullable=False),
        sa.Column('field_type', sa.String(30), nullable=False, server_default='string'),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_subject_fields_subject_id', 'subject_fields', ['subject_id'])
    op.create_index('ix_subject_fields_field_key', 'subject_fields', ['field_key'])
    
    # Create presentation_definitions table
    op.create_table(
        'presentation_definitions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('definition_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('purpose', sa.Text(), nullable=True),
        sa.Column('subject_id', sa.Integer(), nullable=True),
        sa.Column('account_type', sa.String(50), nullable=False),
        sa.Column('requested_fields', sa.JSON(), nullable=False),
        sa.Column('definition_json', sa.JSON(), nullable=False),
        sa.Column('qr_code_s3_key', sa.String(512), nullable=True),
        sa.Column('qr_code_url', sa.Text(), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('definition_id'),
    )
    op.create_index('ix_presentation_definitions_definition_id', 'presentation_definitions', ['definition_id'])
    op.create_index('ix_presentation_definitions_status', 'presentation_definitions', ['status'])
    op.create_index('ix_presentation_definitions_created_at', 'presentation_definitions', ['created_at'])
    
    # Create presentation_requests table
    op.create_table(
        'presentation_requests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('request_id', sa.String(100), nullable=False),
        sa.Column('definition_id', sa.Integer(), nullable=False),
        sa.Column('holder_did', sa.String(255), nullable=True),
        sa.Column('submission_json', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['definition_id'], ['presentation_definitions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('request_id'),
    )
    op.create_index('ix_presentation_requests_request_id', 'presentation_requests', ['request_id'])
    op.create_index('ix_presentation_requests_status', 'presentation_requests', ['status'])


def downgrade() -> None:
    op.drop_table('presentation_requests')
    op.drop_table('presentation_definitions')
    op.drop_table('subject_fields')
    op.drop_table('subjects')
