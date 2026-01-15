"""
Database seed script.
Populates initial subjects and fields for KYC verification.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db_context, init_db
from app.services.subject_service import SubjectService


# Seed data for subjects
SUBJECTS_DATA = [
    {
        "name": "Aadhar Card",
        "description": "Unique Identification Authority of India (UIDAI) issued ID",
        "icon_name": "fingerprint",
        "icon_color": "#ff6b35",
        "fields": [
            {
                "field_key": "full_name",
                "field_name": "Full Name",
                "field_description": "Complete name as per Aadhar",
                "field_type": "string",
                "is_required": True,
                "display_order": 1,
            },
            {
                "field_key": "date_of_birth",
                "field_name": "Date of Birth",
                "field_description": "Date of birth of the holder",
                "field_type": "date",
                "is_required": True,
                "display_order": 2,
            },
            {
                "field_key": "gender",
                "field_name": "Gender",
                "field_description": "Gender of the holder",
                "field_type": "string",
                "is_required": False,
                "display_order": 3,
            },
            {
                "field_key": "address",
                "field_name": "Address",
                "field_description": "Complete residential address",
                "field_type": "string",
                "is_required": True,
                "display_order": 4,
            },
            {
                "field_key": "aadhar_number",
                "field_name": "Aadhar Number",
                "field_description": "12-digit unique identification number",
                "field_type": "string",
                "is_required": True,
                "display_order": 5,
            },
            {
                "field_key": "photo",
                "field_name": "Photo",
                "field_description": "Passport size photograph",
                "field_type": "image",
                "is_required": False,
                "display_order": 6,
            },
            {
                "field_key": "pin_code",
                "field_name": "PIN Code",
                "field_description": "Postal code of address",
                "field_type": "string",
                "is_required": False,
                "display_order": 7,
            },
            {
                "field_key": "state",
                "field_name": "State",
                "field_description": "State of residence",
                "field_type": "string",
                "is_required": False,
                "display_order": 8,
            },
            {
                "field_key": "district",
                "field_name": "District",
                "field_description": "District of residence",
                "field_type": "string",
                "is_required": False,
                "display_order": 9,
            },
        ],
    },
    {
        "name": "PAN Card",
        "description": "Permanent Account Number issued by Income Tax Department",
        "icon_name": "credit_card",
        "icon_color": "#4ecdc4",
        "fields": [
            {
                "field_key": "full_name",
                "field_name": "Full Name",
                "field_description": "Complete name as per PAN",
                "field_type": "string",
                "is_required": True,
                "display_order": 1,
            },
            {
                "field_key": "date_of_birth",
                "field_name": "Date of Birth",
                "field_description": "Date of birth of the holder",
                "field_type": "date",
                "is_required": True,
                "display_order": 2,
            },
            {
                "field_key": "pan_number",
                "field_name": "PAN Number",
                "field_description": "10-character alphanumeric PAN",
                "field_type": "string",
                "is_required": True,
                "display_order": 3,
            },
            {
                "field_key": "fathers_name",
                "field_name": "Father's Name",
                "field_description": "Father's name as per PAN",
                "field_type": "string",
                "is_required": False,
                "display_order": 4,
            },
            {
                "field_key": "photo",
                "field_name": "Photo",
                "field_description": "Photo on PAN card",
                "field_type": "image",
                "is_required": False,
                "display_order": 5,
            },
            {
                "field_key": "signature",
                "field_name": "Signature",
                "field_description": "Signature on PAN card",
                "field_type": "image",
                "is_required": False,
                "display_order": 6,
            },
        ],
    },
    {
        "name": "Voter ID Card",
        "description": "Electoral Photo Identity Card issued by Election Commission",
        "icon_name": "how_to_vote",
        "icon_color": "#9b59b6",
        "fields": [
            {
                "field_key": "full_name",
                "field_name": "Full Name",
                "field_description": "Complete name as per EPIC",
                "field_type": "string",
                "is_required": True,
                "display_order": 1,
            },
            {
                "field_key": "date_of_birth",
                "field_name": "Date of Birth",
                "field_description": "Date of birth of the holder",
                "field_type": "date",
                "is_required": True,
                "display_order": 2,
            },
            {
                "field_key": "gender",
                "field_name": "Gender",
                "field_description": "Gender of the holder",
                "field_type": "string",
                "is_required": False,
                "display_order": 3,
            },
            {
                "field_key": "voter_id",
                "field_name": "Voter ID Number",
                "field_description": "EPIC number",
                "field_type": "string",
                "is_required": True,
                "display_order": 4,
            },
            {
                "field_key": "address",
                "field_name": "Address",
                "field_description": "Residential address",
                "field_type": "string",
                "is_required": True,
                "display_order": 5,
            },
            {
                "field_key": "fathers_name",
                "field_name": "Father's Name",
                "field_description": "Father's name",
                "field_type": "string",
                "is_required": False,
                "display_order": 6,
            },
            {
                "field_key": "photo",
                "field_name": "Photo",
                "field_description": "Passport size photograph",
                "field_type": "image",
                "is_required": False,
                "display_order": 7,
            },
            {
                "field_key": "constituency",
                "field_name": "Constituency",
                "field_description": "Electoral constituency",
                "field_type": "string",
                "is_required": False,
                "display_order": 8,
            },
            {
                "field_key": "part_number",
                "field_name": "Part Number",
                "field_description": "Part number in electoral roll",
                "field_type": "string",
                "is_required": False,
                "display_order": 9,
            },
        ],
    },
]


def seed_database():
    """Seed the database with initial data."""
    print("Initializing database...")
    init_db()
    
    print("Seeding subjects and fields...")
    
    with get_db_context() as db:
        service = SubjectService(db=db)
        
        for subject_data in SUBJECTS_DATA:
            # Check if subject exists
            existing = db.query(
                __import__("app.models.subject", fromlist=["Subject"]).Subject
            ).filter_by(name=subject_data["name"]).first()
            
            if existing:
                print(f"Subject '{subject_data['name']}' already exists, skipping...")
                continue
            
            # Create subject
            subject = service.create_subject(
                name=subject_data["name"],
                description=subject_data["description"],
                icon_name=subject_data["icon_name"],
                icon_color=subject_data["icon_color"],
            )
            print(f"Created subject: {subject.name} (DID: {subject.did})")
            
            # Create fields
            for field_data in subject_data["fields"]:
                field = service.create_subject_field(
                    subject_id=subject.id,
                    field_key=field_data["field_key"],
                    field_name=field_data["field_name"],
                    field_description=field_data["field_description"],
                    field_type=field_data["field_type"],
                    is_required=field_data["is_required"],
                    display_order=field_data["display_order"],
                )
                print(f"  - Created field: {field.field_name}")
    
    print("\nSeeding completed successfully!")


if __name__ == "__main__":
    seed_database()
