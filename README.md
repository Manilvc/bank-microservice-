# Bank Wallet Microservice

A FastAPI-based microservice for KYC verification using Verifiable Credentials and DIF Presentation Exchange.

## Features

- **Subject Management**: Define KYC document types (Aadhar Card, PAN Card, Voter ID) with custom fields
- **DID Integration**: Generate DIDs using the `evrc` method for each subject
- **Presentation Definitions**: Create DIF-compliant presentation definitions for verification requests
- **QR Code Generation**: Generate QR codes stored in S3 for wallet scanning
- **Standard Error Handling**: Consistent error response format across all endpoints

## Tech Stack

- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - ORM for database operations
- **MySQL** - Database storage
- **AWS S3** - QR code image storage
- **Pydantic** - Data validation and serialization
- **Alembic** - Database migrations

## Project Structure

```
bank-microservice-/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry
│   ├── config.py               # Configuration settings
│   ├── database.py             # Database connection
│   ├── middleware.py           # Custom middleware
│   ├── exceptions/             # Exception handling
│   │   ├── __init__.py
│   │   ├── custom_exceptions.py
│   │   └── handlers.py
│   ├── models/                 # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── subject.py
│   │   └── presentation.py
│   ├── schemas/                # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── error.py
│   │   ├── subject.py
│   │   └── presentation.py
│   ├── routers/                # API endpoints
│   │   ├── __init__.py
│   │   ├── health.py
│   │   ├── subjects.py
│   │   └── presentations.py
│   ├── services/               # Business logic
│   │   ├── __init__.py
│   │   ├── s3_service.py
│   │   ├── qr_service.py
│   │   ├── subject_service.py
│   │   └── presentation_service.py
│   └── utils/                  # Utility functions
│       ├── __init__.py
│       └── did.py
├── alembic/                    # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── scripts/
│   └── seed_data.py            # Database seeding
├── alembic.ini
├── env.example
├── requirements.txt
└── README.md
```

## Installation

1. **Clone and install dependencies**:
```bash
cd bank-microservice-
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
copy env.example .env
# Edit .env with your settings
```

3. **Setup MySQL database**:
```sql
CREATE DATABASE bank_wallet;
```

4. **Run migrations**:
```bash
alembic upgrade head
```

5. **Seed initial data**:
```bash
python scripts/seed_data.py
```

6. **Run the application**:
```bash
uvicorn app.main:app --reload
```

## API Endpoints

### Health
- `GET /api/v1/health` - Health check
- `GET /api/v1/health/ready` - Readiness probe
- `GET /api/v1/health/live` - Liveness probe

### Subjects
- `GET /api/v1/subjects` - List all subjects (Aadhar, PAN, Voter ID)
- `GET /api/v1/subjects/{id}` - Get subject with fields
- `POST /api/v1/subjects` - Create new subject
- `POST /api/v1/subjects/{id}/fields` - Add field to subject

### Presentations
- `POST /api/v1/presentations` - Create presentation definition
- `GET /api/v1/presentations` - List presentations
- `GET /api/v1/presentations/{id}` - Get presentation
- `GET /api/v1/presentations/{id}/qr` - Get QR code URL
- `GET /api/v1/presentations/{id}/definition` - Get DIF definition

## API Usage Examples

### List Subjects
```bash
curl http://localhost:8000/api/v1/subjects
```

Response:
```json
{
  "success": true,
  "message": "Subjects retrieved successfully",
  "data": [
    {
      "id": 1,
      "name": "Aadhar Card",
      "description": "Unique Identification Authority of India (UIDAI) issued ID",
      "icon_name": "fingerprint",
      "icon_color": "#ff6b35",
      "did": "did:evrc:bank-wallet-issuer:aadhar-card-abc123",
      "field_count": 9,
      "is_active": true
    }
  ],
  "total": 3
}
```

### Create Presentation Definition
```bash
curl -X POST http://localhost:8000/api/v1/presentations \
  -H "Content-Type: application/json" \
  -d '{
    "subject_id": 1,
    "account_type": "Savings Account",
    "field_ids": [1, 2, 5],
    "purpose": "KYC verification for account opening"
  }'
```

Response:
```json
{
  "success": true,
  "message": "Presentation definition created successfully",
  "data": {
    "definition_id": "1768025257083-r6tb41323",
    "account_type": "Savings Account",
    "document_name": "Aadhar Card",
    "created_at": "2026-01-10T11:37:37Z",
    "expires_at": "2026-01-11T11:37:37Z",
    "requested_fields": [
      {"field_id": 1, "field_key": "full_name", "field_name": "Full Name", "is_required": true}
    ],
    "qr_code_url": "https://bucket.s3.region.amazonaws.com/qr-codes/presentations/xyz.png",
    "status": "active"
  }
}
```

## Error Response Format

All errors return a standard format:

```json
{
  "success": false,
  "error": "NOT_FOUND",
  "message": "Subject with id '999' not found",
  "status_code": 404,
  "details": null,
  "request_id": "abc123def456",
  "timestamp": "2026-01-10T10:30:00Z",
  "path": "/api/v1/subjects/999"
}
```

## Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Database Schema

### subjects
| Column | Type | Description |
|--------|------|-------------|
| id | INT | Primary key |
| name | VARCHAR(100) | Subject name |
| description | TEXT | Description |
| icon_name | VARCHAR(50) | Icon identifier |
| icon_color | VARCHAR(20) | Hex color |
| did | VARCHAR(255) | Decentralized ID |
| is_active | BOOLEAN | Active status |

### subject_fields
| Column | Type | Description |
|--------|------|-------------|
| id | INT | Primary key |
| subject_id | INT | Foreign key |
| field_key | VARCHAR(50) | Machine key |
| field_name | VARCHAR(100) | Display name |
| field_type | VARCHAR(30) | Data type |
| is_required | BOOLEAN | Required flag |

### presentation_definitions
| Column | Type | Description |
|--------|------|-------------|
| id | INT | Primary key |
| definition_id | VARCHAR(100) | Unique ID |
| subject_id | INT | Foreign key |
| account_type | VARCHAR(50) | Account type |
| definition_json | JSON | DIF definition |
| qr_code_url | TEXT | S3 URL |
| expires_at | DATETIME | Expiration |

## License

MIT
