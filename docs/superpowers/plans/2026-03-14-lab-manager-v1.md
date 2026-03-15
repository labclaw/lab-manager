# Lab-Manager V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-quality lab inventory management system with OCR document intake, covering materials/devices/orders tracking for a 10-person neuroscience lab.

**Architecture:** PostgreSQL (relational core + JSONB for vendor-specific fields) + FastAPI/SQLModel (API + ORM) + SQLAdmin (admin UI) + Meilisearch (full-text search). Document intake pipeline: scan → Qwen3-VL OCR → Instructor/LLM structured extraction → human confirmation → database. All changes audited.

**Tech Stack:** Python 3.12+, FastAPI, SQLModel, SQLAdmin, PostgreSQL, Alembic (migrations), Meilisearch, Instructor, Pydantic v2, Docker Compose, pytest, ruff

---

## File Structure

```
lab-manager/
├── pyproject.toml                     # UPDATE: add all new dependencies
├── alembic.ini                        # CREATE: Alembic config
├── docker-compose.yml                 # CREATE: PostgreSQL + Meilisearch + app
├── Dockerfile                         # CREATE: app container
├── .env.example                       # CREATE: env template
├── src/
│   └── lab_manager/
│       ├── __init__.py                # CREATE: package init
│       ├── config.py                  # CREATE: pydantic-settings config
│       ├── database.py                # CREATE: engine, session factory
│       ├── models/
│       │   ├── __init__.py            # CREATE: re-export all models
│       │   ├── base.py                # CREATE: shared base model with audit fields
│       │   ├── vendor.py              # CREATE: Vendor model
│       │   ├── product.py             # CREATE: Product (catalog item) model
│       │   ├── order.py               # CREATE: Order + OrderItem models
│       │   ├── inventory.py           # CREATE: InventoryItem model (stock)
│       │   ├── document.py            # CREATE: Document + Extraction models
│       │   ├── staff.py               # CREATE: Staff model
│       │   ├── location.py            # CREATE: StorageLocation model
│       │   └── audit.py               # CREATE: AuditLog model
│       ├── api/
│       │   ├── __init__.py            # CREATE
│       │   ├── app.py                 # CREATE: FastAPI application factory
│       │   ├── deps.py                # CREATE: dependency injection (db session)
│       │   ├── admin.py               # CREATE: SQLAdmin setup
│       │   └── routes/
│       │       ├── __init__.py        # CREATE
│       │       ├── vendors.py         # CREATE: vendor CRUD endpoints
│       │       ├── products.py        # CREATE: product CRUD endpoints
│       │       ├── orders.py          # CREATE: order CRUD endpoints
│       │       ├── inventory.py       # CREATE: inventory endpoints
│       │       ├── documents.py       # CREATE: document upload + review endpoints
│       │       └── search.py          # CREATE: search endpoint
│       ├── intake/
│       │   ├── __init__.py            # CREATE
│       │   ├── schemas.py             # CREATE: Pydantic extraction schemas
│       │   ├── ocr.py                 # CREATE: OCR wrapper (Qwen3-VL + API)
│       │   ├── extractor.py           # CREATE: Instructor-based field extraction
│       │   └── pipeline.py            # CREATE: orchestrate scan → DB
│       └── services/
│           ├── __init__.py            # CREATE
│           ├── search.py              # CREATE: Meilisearch sync
│           └── alerts.py              # CREATE: expiry/low-stock checks
├── alembic/
│   ├── env.py                         # CREATE: migration environment
│   └── versions/                      # CREATE: migration scripts (auto-generated)
├── tests/
│   ├── conftest.py                    # CREATE: fixtures (test DB, client)
│   ├── test_models.py                 # CREATE: model + DB tests
│   ├── test_api_vendors.py            # CREATE: vendor API tests
│   ├── test_api_orders.py             # CREATE: order API tests
│   ├── test_api_inventory.py          # CREATE: inventory API tests
│   ├── test_api_documents.py          # CREATE: document API tests
│   ├── test_intake_schemas.py         # CREATE: extraction schema tests
│   ├── test_intake_pipeline.py        # CREATE: pipeline integration tests
│   └── test_search.py                 # CREATE: search tests
└── scripts/
    ├── seed_vendors.py                # CREATE: seed known vendors from scan data
    └── process_scans.py               # CREATE: batch process shenlab-docs/
```

---

## Chunk 1: Project Foundation

### Task 1: Update pyproject.toml with V1 dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Update pyproject.toml**

```toml
[project]
name = "lab-manager"
version = "0.1.0"
description = "Lab inventory management with OCR document intake"
requires-python = ">=3.12"
dependencies = [
  "fastapi[standard]>=0.115.0",
  "sqlmodel>=0.0.22",
  "sqlalchemy[asyncio]>=2.0.0",
  "psycopg[binary]>=3.2.0",
  "alembic>=1.14.0",
  "sqladmin>=0.20.0",
  "pydantic-settings>=2.6.0",
  "meilisearch>=0.33.0",
  "instructor>=1.7.0",
  "google-genai>=1.0.0",
  "pillow>=11.2.1",
  "python-multipart>=0.0.18",
  "python-ulid>=3.0.0",
]

[dependency-groups]
dev = [
  "pytest>=8.4.0",
  "pytest-asyncio>=0.24.0",
  "httpx>=0.28.0",
  "ruff>=0.11.0",
  "testcontainers[postgres]>=4.0.0",
]
```

- [ ] **Step 2: Install dependencies**

Run: `cd /home/robot/workspace/31-labclaw/lab-manager && uv sync`
Expected: all packages install successfully

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add V1 dependencies (FastAPI, SQLModel, PostgreSQL, Meilisearch, Instructor)"
```

---

### Task 2: Configuration and database setup

**Files:**
- Create: `src/lab_manager/__init__.py`
- Create: `src/lab_manager/config.py`
- Create: `src/lab_manager/database.py`
- Create: `.env.example`

- [ ] **Step 1: Write config test**

Create `tests/test_config.py`:

```python
"""Test configuration loading."""
import os

def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/testdb")
    monkeypatch.setenv("MEILISEARCH_URL", "http://localhost:7700")
    from lab_manager.config import get_settings
    s = get_settings.cache_clear()
    s = get_settings()
    assert "testdb" in s.database_url
    assert s.meilisearch_url == "http://localhost:7700"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/robot/workspace/31-labclaw/lab-manager && python -m pytest tests/test_config.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Create package init**

Create `src/lab_manager/__init__.py`:

```python
"""LabClaw Lab Manager — inventory management with OCR document intake."""
```

- [ ] **Step 4: Create config.py**

Create `src/lab_manager/config.py`:

```python
"""Application settings loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration."""

    database_url: str = "postgresql://labmanager:labmanager@localhost:5432/labmanager"
    meilisearch_url: str = "http://localhost:7700"
    meilisearch_api_key: str = ""

    # Document intake
    ocr_model: str = "Qwen/Qwen3-VL-4B-Instruct"
    extraction_model: str = "gemini-2.5-flash-preview"
    extraction_api_key: str = ""
    auto_approve_threshold: float = 0.95

    # File storage
    upload_dir: str = "uploads"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Create database.py**

Create `src/lab_manager/database.py`:

```python
"""Database engine and session management."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from lab_manager.config import get_settings


def get_engine():
    settings = get_settings()
    return create_engine(settings.database_url, echo=False)


def get_session_factory():
    return sessionmaker(bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 6: Create .env.example**

Create `.env.example`:

```bash
DATABASE_URL=postgresql://labmanager:labmanager@localhost:5432/labmanager
MEILISEARCH_URL=http://localhost:7700
MEILISEARCH_API_KEY=
EXTRACTION_API_KEY=
```

- [ ] **Step 7: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/ tests/test_config.py .env.example
git commit -m "feat(core): add config and database module"
```

---

### Task 3: Base model with audit fields

**Files:**
- Create: `src/lab_manager/models/__init__.py`
- Create: `src/lab_manager/models/base.py`

- [ ] **Step 1: Write test for base model**

Create `tests/test_models.py`:

```python
"""Test database models."""
from datetime import datetime, timezone

from lab_manager.models.base import AuditMixin


def test_audit_mixin_has_timestamps():
    """AuditMixin should define created_at, updated_at, created_by."""
    fields = {f for f in AuditMixin.model_fields}
    assert "created_at" in fields
    assert "updated_at" in fields
    assert "created_by" in fields
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py::test_audit_mixin_has_timestamps -v`
Expected: FAIL

- [ ] **Step 3: Create base model**

Create `src/lab_manager/models/base.py`:

```python
"""Shared base for all models."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditMixin(SQLModel):
    """Mixin adding audit timestamp fields to any model."""

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    created_by: Optional[str] = Field(default=None, max_length=100)
```

Create `src/lab_manager/models/__init__.py`:

```python
"""Database models."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lab_manager/models/ tests/test_models.py
git commit -m "feat(models): add AuditMixin base with timestamps"
```

---

### Task 4: Core domain models — Vendor, Product, Staff, Location

**Files:**
- Create: `src/lab_manager/models/vendor.py`
- Create: `src/lab_manager/models/product.py`
- Create: `src/lab_manager/models/staff.py`
- Create: `src/lab_manager/models/location.py`

- [ ] **Step 1: Write model tests**

Append to `tests/test_models.py`:

```python
from lab_manager.models.vendor import Vendor
from lab_manager.models.product import Product
from lab_manager.models.staff import Staff
from lab_manager.models.location import StorageLocation


def test_vendor_model():
    v = Vendor(name="Sigma-Aldrich", aliases=["MilliporeSigma", "Merck"])
    assert v.name == "Sigma-Aldrich"
    assert "MilliporeSigma" in v.aliases


def test_product_model():
    p = Product(
        catalog_number="AB1031",
        name="AGGRECAN, RBX MS-50UG",
        vendor_id=1,
    )
    assert p.catalog_number == "AB1031"


def test_staff_model():
    s = Staff(name="Shiqian Shen", email="sshen@mgh.harvard.edu", role="PI")
    assert s.role == "PI"


def test_location_model():
    loc = StorageLocation(name="Freezer -80C #1", temperature=-80, room="CNY 149")
    assert loc.temperature == -80
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL — import errors

- [ ] **Step 3: Create Vendor model**

Create `src/lab_manager/models/vendor.py`:

```python
"""Vendor / supplier model."""
from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON

from lab_manager.models.base import AuditMixin


class Vendor(AuditMixin, table=True):
    __tablename__ = "vendors"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, index=True, unique=True)
    aliases: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    website: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None)
```

- [ ] **Step 4: Create Product model**

Create `src/lab_manager/models/product.py`:

```python
"""Product / catalog item model."""
from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON

from lab_manager.models.base import AuditMixin


class Product(AuditMixin, table=True):
    __tablename__ = "products"

    id: Optional[int] = Field(default=None, primary_key=True)
    catalog_number: str = Field(max_length=100, index=True)
    name: str = Field(max_length=500)
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendors.id", index=True)
    category: Optional[str] = Field(default=None, max_length=100, index=True)
    cas_number: Optional[str] = Field(default=None, max_length=30)
    storage_temp: Optional[str] = Field(default=None, max_length=50)
    unit: Optional[str] = Field(default=None, max_length=50)
    hazard_info: Optional[str] = Field(default=None, max_length=255)
    extra: dict = Field(default_factory=dict, sa_column=Column(JSON))
```

- [ ] **Step 5: Create Staff model**

Create `src/lab_manager/models/staff.py`:

```python
"""Lab staff / user model."""
from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel

from lab_manager.models.base import AuditMixin


class Staff(AuditMixin, table=True):
    __tablename__ = "staff"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=200, index=True)
    email: Optional[str] = Field(default=None, max_length=255, unique=True)
    role: str = Field(default="member", max_length=50)
    is_active: bool = Field(default=True)
```

- [ ] **Step 6: Create StorageLocation model**

Create `src/lab_manager/models/location.py`:

```python
"""Storage location model."""
from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel

from lab_manager.models.base import AuditMixin


class StorageLocation(AuditMixin, table=True):
    __tablename__ = "locations"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=200, index=True)
    room: Optional[str] = Field(default=None, max_length=100)
    building: Optional[str] = Field(default=None, max_length=100)
    temperature: Optional[int] = Field(default=None)
    description: Optional[str] = Field(default=None)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/lab_manager/models/ tests/test_models.py
git commit -m "feat(models): add Vendor, Product, Staff, StorageLocation models"
```

---

### Task 5: Order and Inventory models

**Files:**
- Create: `src/lab_manager/models/order.py`
- Create: `src/lab_manager/models/inventory.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_models.py`:

```python
from datetime import date
from lab_manager.models.order import Order, OrderItem
from lab_manager.models.inventory import InventoryItem


def test_order_model():
    o = Order(
        po_number="PO-10997931",
        vendor_id=1,
        order_date=date(2026, 3, 4),
        status="received",
    )
    assert o.po_number == "PO-10997931"


def test_order_item_model():
    item = OrderItem(
        order_id=1,
        catalog_number="AB1031",
        description="AGGRECAN, RBX MS-50UG",
        quantity=1,
        lot_number="4361991",
    )
    assert item.lot_number == "4361991"


def test_inventory_item_model():
    inv = InventoryItem(
        product_id=1,
        location_id=1,
        quantity_on_hand=5,
        lot_number="4361991",
    )
    assert inv.quantity_on_hand == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_models.py -v -k "order or inventory"`
Expected: FAIL

- [ ] **Step 3: Create Order models**

Create `src/lab_manager/models/order.py`:

```python
"""Order and order line item models."""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON

from lab_manager.models.base import AuditMixin


class Order(AuditMixin, table=True):
    __tablename__ = "orders"

    id: Optional[int] = Field(default=None, primary_key=True)
    po_number: Optional[str] = Field(default=None, max_length=100, index=True)
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendors.id", index=True)
    order_date: Optional[date] = Field(default=None)
    ship_date: Optional[date] = Field(default=None)
    received_date: Optional[date] = Field(default=None)
    received_by: Optional[str] = Field(default=None, max_length=200)
    status: str = Field(default="pending", max_length=30, index=True)
    delivery_number: Optional[str] = Field(default=None, max_length=100)
    invoice_number: Optional[str] = Field(default=None, max_length=100)
    document_id: Optional[int] = Field(default=None, foreign_key="documents.id")
    extra: dict = Field(default_factory=dict, sa_column=Column(JSON))


class OrderItem(AuditMixin, table=True):
    __tablename__ = "order_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    catalog_number: Optional[str] = Field(default=None, max_length=100, index=True)
    description: Optional[str] = Field(default=None, max_length=1000)
    quantity: float = Field(default=1)
    unit: Optional[str] = Field(default=None, max_length=50)
    lot_number: Optional[str] = Field(default=None, max_length=100, index=True)
    batch_number: Optional[str] = Field(default=None, max_length=100)
    unit_price: Optional[float] = Field(default=None)
    product_id: Optional[int] = Field(default=None, foreign_key="products.id")
    extra: dict = Field(default_factory=dict, sa_column=Column(JSON))
```

- [ ] **Step 4: Create Inventory model**

Create `src/lab_manager/models/inventory.py`:

```python
"""Inventory stock model."""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel

from lab_manager.models.base import AuditMixin


class InventoryItem(AuditMixin, table=True):
    __tablename__ = "inventory"

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: Optional[int] = Field(default=None, foreign_key="products.id", index=True)
    location_id: Optional[int] = Field(default=None, foreign_key="locations.id", index=True)
    lot_number: Optional[str] = Field(default=None, max_length=100)
    quantity_on_hand: float = Field(default=0)
    unit: Optional[str] = Field(default=None, max_length=50)
    expiry_date: Optional[date] = Field(default=None, index=True)
    opened_date: Optional[date] = Field(default=None)
    status: str = Field(default="available", max_length=30)
    notes: Optional[str] = Field(default=None)
    received_by: Optional[str] = Field(default=None, max_length=200)
    order_item_id: Optional[int] = Field(default=None, foreign_key="order_items.id")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/lab_manager/models/ tests/test_models.py
git commit -m "feat(models): add Order, OrderItem, InventoryItem models"
```

---

### Task 6: Document and AuditLog models

**Files:**
- Create: `src/lab_manager/models/document.py`
- Create: `src/lab_manager/models/audit.py`
- Modify: `src/lab_manager/models/__init__.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_models.py`:

```python
from lab_manager.models.document import Document
from lab_manager.models.audit import AuditLog


def test_document_model():
    doc = Document(
        file_path="uploads/scan001.jpg",
        file_name="scan001.jpg",
        document_type="packing_list",
        status="pending",
    )
    assert doc.status == "pending"


def test_audit_log_model():
    log = AuditLog(
        table_name="orders",
        record_id=1,
        action="create",
        changed_by="sshen",
        changes={"po_number": {"old": None, "new": "PO-123"}},
    )
    assert log.action == "create"
```

- [ ] **Step 2: Create Document model**

Create `src/lab_manager/models/document.py`:

```python
"""Scanned document and extraction models."""
from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON, Text

from lab_manager.models.base import AuditMixin


class Document(AuditMixin, table=True):
    __tablename__ = "documents"

    id: Optional[int] = Field(default=None, primary_key=True)
    file_path: str = Field(max_length=1000)
    file_name: str = Field(max_length=255)
    document_type: Optional[str] = Field(default=None, max_length=50, index=True)
    vendor_name: Optional[str] = Field(default=None, max_length=255)
    ocr_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    extracted_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    extraction_model: Optional[str] = Field(default=None, max_length=100)
    extraction_confidence: Optional[float] = Field(default=None)
    status: str = Field(default="pending", max_length=30, index=True)
    review_notes: Optional[str] = Field(default=None)
    reviewed_by: Optional[str] = Field(default=None, max_length=200)
    order_id: Optional[int] = Field(default=None, foreign_key="orders.id")
```

- [ ] **Step 3: Create AuditLog model**

Create `src/lab_manager/models/audit.py`:

```python
"""Audit log for tracking all data changes."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON

from lab_manager.models.base import utcnow


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    table_name: str = Field(max_length=100, index=True)
    record_id: int = Field(index=True)
    action: str = Field(max_length=20)  # create, update, delete
    changed_by: Optional[str] = Field(default=None, max_length=100)
    changes: dict = Field(default_factory=dict, sa_column=Column(JSON))
    timestamp: datetime = Field(default_factory=utcnow)
```

- [ ] **Step 4: Update models __init__.py to re-export all models**

Update `src/lab_manager/models/__init__.py`:

```python
"""Database models — import all for Alembic discovery."""
from lab_manager.models.base import AuditMixin
from lab_manager.models.vendor import Vendor
from lab_manager.models.product import Product
from lab_manager.models.staff import Staff
from lab_manager.models.location import StorageLocation
from lab_manager.models.order import Order, OrderItem
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.document import Document
from lab_manager.models.audit import AuditLog

__all__ = [
    "AuditMixin",
    "Vendor",
    "Product",
    "Staff",
    "StorageLocation",
    "Order",
    "OrderItem",
    "InventoryItem",
    "Document",
    "AuditLog",
]
```

- [ ] **Step 5: Run all model tests**

Run: `python -m pytest tests/test_models.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/lab_manager/models/ tests/test_models.py
git commit -m "feat(models): add Document, AuditLog; export all models"
```

---

### Task 7: Docker Compose + Alembic migrations

**Files:**
- Create: `docker-compose.yml`
- Create: `Dockerfile`
- Create: `alembic.ini`
- Create: `alembic/env.py`

- [ ] **Step 1: Create docker-compose.yml**

```yaml
services:
  db:
    image: postgres:17-alpine
    environment:
      POSTGRES_USER: labmanager
      POSTGRES_PASSWORD: labmanager
      POSTGRES_DB: labmanager
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  search:
    image: getmeili/meilisearch:v1.12
    ports:
      - "7700:7700"
    volumes:
      - msdata:/meili_data
    environment:
      MEILI_ENV: development

volumes:
  pgdata:
  msdata:
```

- [ ] **Step 2: Create alembic.ini**

```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql://labmanager:labmanager@localhost:5432/labmanager

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

- [ ] **Step 3: Create alembic/env.py**

```python
"""Alembic migration environment."""
from alembic import context
from sqlalchemy import create_engine
from sqlmodel import SQLModel

# Import all models so they register with SQLModel.metadata
from lab_manager.models import *  # noqa: F401, F403
from lab_manager.config import get_settings

target_metadata = SQLModel.metadata


def run_migrations_online():
    settings = get_settings()
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
```

Create `alembic/versions/.gitkeep` (empty file).

- [ ] **Step 4: Start services and generate initial migration**

Run:
```bash
docker compose up -d db search
sleep 3
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```
Expected: Migration generated and applied, all 9 tables created.

- [ ] **Step 5: Verify tables exist**

Run: `docker compose exec db psql -U labmanager -c '\dt'`
Expected: vendors, products, staff, locations, orders, order_items, inventory, documents, audit_log

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml alembic.ini alembic/ Dockerfile
git commit -m "feat(infra): add Docker Compose (PG + Meilisearch) and Alembic migrations"
```

---

## Chunk 2: FastAPI Application + CRUD API

### Task 8: FastAPI app factory + SQLAdmin

**Files:**
- Create: `src/lab_manager/api/app.py`
- Create: `src/lab_manager/api/deps.py`
- Create: `src/lab_manager/api/admin.py`
- Create: `src/lab_manager/api/__init__.py`

- [ ] **Step 1: Write test for app startup**

Create `tests/conftest.py`:

```python
"""Shared test fixtures."""
import os
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["MEILISEARCH_URL"] = "http://localhost:7700"

from lab_manager.config import get_settings
get_settings.cache_clear()


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(db_session):
    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
```

Create `tests/test_api_vendors.py`:

```python
"""Test vendor API endpoints."""


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

- [ ] **Step 2: Create deps.py**

Create `src/lab_manager/api/__init__.py` (empty).

Create `src/lab_manager/api/deps.py`:

```python
"""Dependency injection for FastAPI routes."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from lab_manager.database import get_session_factory


def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 3: Create app.py**

Create `src/lab_manager/api/app.py`:

```python
"""FastAPI application factory."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse


def create_app() -> FastAPI:
    app = FastAPI(
        title="LabClaw Lab Manager",
        description="Lab inventory management with OCR document intake",
        version="0.1.0",
    )

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    # Register route modules
    from lab_manager.api.routes import vendors, products, orders, inventory, documents

    app.include_router(vendors.router, prefix="/api/vendors", tags=["vendors"])
    app.include_router(products.router, prefix="/api/products", tags=["products"])
    app.include_router(orders.router, prefix="/api/orders", tags=["orders"])
    app.include_router(inventory.router, prefix="/api/inventory", tags=["inventory"])
    app.include_router(documents.router, prefix="/api/documents", tags=["documents"])

    return app
```

- [ ] **Step 4: Create stub route modules**

Create `src/lab_manager/api/routes/__init__.py` (empty).

Create `src/lab_manager/api/routes/vendors.py`:

```python
"""Vendor CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.models.vendor import Vendor

router = APIRouter()


@router.get("/")
def list_vendors(db: Session = Depends(get_db)):
    return db.query(Vendor).all()


@router.post("/", status_code=201)
def create_vendor(vendor: Vendor, db: Session = Depends(get_db)):
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


@router.get("/{vendor_id}")
def get_vendor(vendor_id: int, db: Session = Depends(get_db)):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor
```

Create similarly for `products.py`, `orders.py`, `inventory.py`, `documents.py` — each with basic `list` and `create` endpoints following the same pattern. (See vendor.py as template, substitute model name.)

- [ ] **Step 5: Run test**

Run: `python -m pytest tests/test_api_vendors.py -v`
Expected: PASS

- [ ] **Step 6: Write vendor CRUD tests**

Append to `tests/test_api_vendors.py`:

```python
def test_create_vendor(client):
    resp = client.post("/api/vendors/", json={"name": "Sigma-Aldrich"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Sigma-Aldrich"


def test_list_vendors(client):
    client.post("/api/vendors/", json={"name": "Sigma"})
    resp = client.get("/api/vendors/")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_get_vendor_not_found(client):
    resp = client.get("/api/vendors/999")
    assert resp.status_code == 404
```

- [ ] **Step 7: Run tests**

Run: `python -m pytest tests/test_api_vendors.py -v`
Expected: ALL PASS

- [ ] **Step 8: Create SQLAdmin setup**

Create `src/lab_manager/api/admin.py`:

```python
"""SQLAdmin configuration — admin UI for all models."""
from __future__ import annotations

from sqladmin import Admin, ModelView

from lab_manager.models.vendor import Vendor
from lab_manager.models.product import Product
from lab_manager.models.staff import Staff
from lab_manager.models.location import StorageLocation
from lab_manager.models.order import Order, OrderItem
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.document import Document
from lab_manager.models.audit import AuditLog


class VendorAdmin(ModelView, model=Vendor):
    column_list = [Vendor.id, Vendor.name, Vendor.website, Vendor.created_at]
    column_searchable_list = [Vendor.name]


class ProductAdmin(ModelView, model=Product):
    column_list = [Product.id, Product.catalog_number, Product.name, Product.category]
    column_searchable_list = [Product.catalog_number, Product.name]


class StaffAdmin(ModelView, model=Staff):
    column_list = [Staff.id, Staff.name, Staff.email, Staff.role, Staff.is_active]


class LocationAdmin(ModelView, model=StorageLocation):
    column_list = [StorageLocation.id, StorageLocation.name, StorageLocation.room, StorageLocation.temperature]


class OrderAdmin(ModelView, model=Order):
    column_list = [Order.id, Order.po_number, Order.order_date, Order.status, Order.received_by]
    column_searchable_list = [Order.po_number, Order.delivery_number]


class OrderItemAdmin(ModelView, model=OrderItem):
    column_list = [OrderItem.id, OrderItem.catalog_number, OrderItem.description, OrderItem.lot_number, OrderItem.quantity]
    column_searchable_list = [OrderItem.catalog_number, OrderItem.lot_number]


class InventoryAdmin(ModelView, model=InventoryItem):
    column_list = [InventoryItem.id, InventoryItem.quantity_on_hand, InventoryItem.lot_number, InventoryItem.expiry_date, InventoryItem.status]


class DocumentAdmin(ModelView, model=Document):
    column_list = [Document.id, Document.file_name, Document.document_type, Document.vendor_name, Document.status]
    column_searchable_list = [Document.file_name, Document.vendor_name]


class AuditLogAdmin(ModelView, model=AuditLog):
    column_list = [AuditLog.id, AuditLog.table_name, AuditLog.action, AuditLog.changed_by, AuditLog.timestamp]


def setup_admin(app, engine):
    admin = Admin(app, engine, title="LabClaw Manager")
    admin.add_view(VendorAdmin)
    admin.add_view(ProductAdmin)
    admin.add_view(StaffAdmin)
    admin.add_view(LocationAdmin)
    admin.add_view(OrderAdmin)
    admin.add_view(OrderItemAdmin)
    admin.add_view(InventoryAdmin)
    admin.add_view(DocumentAdmin)
    admin.add_view(AuditLogAdmin)
```

- [ ] **Step 9: Commit**

```bash
git add src/lab_manager/api/ tests/
git commit -m "feat(api): add FastAPI app, vendor CRUD, SQLAdmin panel"
```

---

## Chunk 3: Document Intake Pipeline

### Task 9: Extraction schemas (Pydantic models for OCR output)

**Files:**
- Create: `src/lab_manager/intake/__init__.py`
- Create: `src/lab_manager/intake/schemas.py`

- [ ] **Step 1: Write schema tests**

Create `tests/test_intake_schemas.py`:

```python
"""Test extraction schemas."""
from lab_manager.intake.schemas import ExtractedDocument, ExtractedItem


def test_extracted_document_from_dict():
    data = {
        "vendor_name": "Sigma-Aldrich",
        "document_type": "packing_list",
        "po_number": "PO-10997931",
        "order_date": "2026-03-04",
        "items": [
            {
                "catalog_number": "AB1031",
                "description": "AGGRECAN, RBX MS-50UG",
                "quantity": 1,
                "lot_number": "4361991",
            }
        ],
    }
    doc = ExtractedDocument(**data)
    assert doc.vendor_name == "Sigma-Aldrich"
    assert len(doc.items) == 1
    assert doc.items[0].catalog_number == "AB1031"


def test_extracted_document_optional_fields():
    """Minimal valid document."""
    doc = ExtractedDocument(vendor_name="Unknown", document_type="other", items=[])
    assert doc.po_number is None
```

- [ ] **Step 2: Create schemas**

Create `src/lab_manager/intake/__init__.py` (empty).

Create `src/lab_manager/intake/schemas.py`:

```python
"""Pydantic schemas for structured extraction from OCR text."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ExtractedItem(BaseModel):
    """A single line item from a packing list / invoice."""

    catalog_number: Optional[str] = Field(None, description="Product catalog or item number")
    description: Optional[str] = Field(None, description="Product description")
    quantity: Optional[float] = Field(None, description="Quantity ordered/shipped")
    unit: Optional[str] = Field(None, description="Unit of measure (EA, UL, MG, etc.)")
    lot_number: Optional[str] = Field(None, description="Lot or batch number")
    batch_number: Optional[str] = Field(None, description="Batch number if different from lot")
    cas_number: Optional[str] = Field(None, description="CAS registry number")
    storage_temp: Optional[str] = Field(None, description="Storage temperature requirement")
    unit_price: Optional[float] = Field(None, description="Price per unit")


class ExtractedDocument(BaseModel):
    """Structured data extracted from a scanned lab document."""

    vendor_name: str = Field(description="Supplier / vendor company name")
    document_type: str = Field(description="Type: packing_list, invoice, package, shipping_label")
    po_number: Optional[str] = Field(None, description="Purchase order number")
    order_number: Optional[str] = Field(None, description="Sales or order number")
    invoice_number: Optional[str] = Field(None, description="Invoice number")
    delivery_number: Optional[str] = Field(None, description="Delivery or shipment number")
    order_date: Optional[str] = Field(None, description="Order date in ISO format")
    ship_date: Optional[str] = Field(None, description="Shipping date")
    received_date: Optional[str] = Field(None, description="Handwritten receiving date")
    received_by: Optional[str] = Field(None, description="Person who received the package")
    ship_to_address: Optional[str] = Field(None, description="Shipping destination address")
    bill_to_address: Optional[str] = Field(None, description="Billing address")
    items: list[ExtractedItem] = Field(default_factory=list, description="Line items")
    confidence: Optional[float] = Field(None, description="Extraction confidence 0-1")
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_intake_schemas.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/lab_manager/intake/ tests/test_intake_schemas.py
git commit -m "feat(intake): add Pydantic extraction schemas for lab documents"
```

---

### Task 10: LLM-based structured extractor

**Files:**
- Create: `src/lab_manager/intake/extractor.py`

- [ ] **Step 1: Write extractor test**

Create `tests/test_intake_extractor.py`:

```python
"""Test structured extraction from OCR text."""
from lab_manager.intake.extractor import extract_from_text
from lab_manager.intake.schemas import ExtractedDocument

SAMPLE_OCR = """MILLIPORE SIGMA
PACKING LIST
DELIVERY NO. 236655726
CUSTOMER PO PO-10997931
CATALOG NUMBER AB1031
AGGRECAN, RBX MS-50UG
Lot#: 4361991 (Qty: 1 EA)"""


def test_extract_from_text_returns_schema(monkeypatch):
    """Test that extraction returns valid ExtractedDocument."""
    # Mock the LLM call for testing
    def mock_extract(text: str) -> ExtractedDocument:
        return ExtractedDocument(
            vendor_name="EMD Millipore Corporation",
            document_type="packing_list",
            po_number="PO-10997931",
            items=[{
                "catalog_number": "AB1031",
                "description": "AGGRECAN, RBX MS-50UG",
                "quantity": 1,
                "lot_number": "4361991",
            }],
        )

    monkeypatch.setattr("lab_manager.intake.extractor._call_llm", mock_extract)
    result = extract_from_text(SAMPLE_OCR)
    assert isinstance(result, ExtractedDocument)
    assert result.po_number == "PO-10997931"
    assert result.items[0].catalog_number == "AB1031"
```

- [ ] **Step 2: Create extractor**

Create `src/lab_manager/intake/extractor.py`:

```python
"""Extract structured data from OCR text using LLM + Instructor."""
from __future__ import annotations

import instructor
from google import genai

from lab_manager.config import get_settings
from lab_manager.intake.schemas import ExtractedDocument

EXTRACTION_PROMPT = """You are extracting structured data from OCR text of a lab supply document (packing list, invoice, or shipping label).

Extract ALL fields you can find. Be precise — use exact text from the document.

Rules:
- vendor_name: the supplier company (e.g., "Sigma-Aldrich", "EMD Millipore Corporation")
- document_type: one of packing_list, invoice, package, shipping_label
- dates: convert to ISO format (YYYY-MM-DD) when possible
- catalog_number: exact product ID as printed
- lot_number / batch_number: exact as printed
- quantity: numeric value
- Do NOT guess or hallucinate. If a field is not visible, leave it null.
"""


def _call_llm(ocr_text: str) -> ExtractedDocument:
    """Call LLM via Instructor to extract structured data."""
    settings = get_settings()
    client = genai.Client(api_key=settings.extraction_api_key)
    client = instructor.from_genai(client)

    return client.chat.completions.create(
        model=settings.extraction_model,
        messages=[
            {"role": "user", "content": f"{EXTRACTION_PROMPT}\n\n---\nOCR TEXT:\n{ocr_text}"},
        ],
        response_model=ExtractedDocument,
    )


def extract_from_text(ocr_text: str) -> ExtractedDocument:
    """Extract structured fields from OCR text.

    Returns an ExtractedDocument with all fields populated from the text.
    """
    return _call_llm(ocr_text)
```

- [ ] **Step 3: Run test**

Run: `python -m pytest tests/test_intake_extractor.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/lab_manager/intake/extractor.py tests/test_intake_extractor.py
git commit -m "feat(intake): add LLM-based structured extractor with Instructor"
```

---

### Task 11: Document intake pipeline orchestrator

**Files:**
- Create: `src/lab_manager/intake/pipeline.py`
- Create: `src/lab_manager/intake/ocr.py`

- [ ] **Step 1: Create OCR wrapper**

Create `src/lab_manager/intake/ocr.py`:

```python
"""OCR text extraction from document images."""
from __future__ import annotations

import base64
from pathlib import Path

from google import genai

from lab_manager.config import get_settings

OCR_PROMPT = """You are performing OCR on a scanned lab supply document (packing list, invoice, or shipping label).
Transcribe ALL visible text as faithfully as possible, character by character.

Critical rules:
- Output plain text only.
- Preserve reading order from top to bottom, left to right.
- Keep line breaks where they appear on the document.
- Pay extra attention to:
  * Catalog/part numbers (e.g., AB2251-1, MAB5406) — distinguish digit 1 from letter I carefully.
  * Batch/lot numbers (e.g., SDBB4556, 4361991) — include ALL batch numbers even if partially visible.
  * Handwritten text and dates (e.g., 3/9/26, 2026.3.07) — transcribe handwritten notes exactly as written.
  * PO numbers, delivery numbers, order numbers.
- Include ALL text including fine print, footer text, and handwritten annotations.
- Do not summarize or explain. Do not add any commentary.
- Do not skip any text region.
"""


def extract_text_from_image(image_path: Path) -> str:
    """Run OCR on a document image and return raw text."""
    settings = get_settings()
    client = genai.Client(api_key=settings.extraction_api_key)

    image_bytes = image_path.read_bytes()
    b64 = base64.b64encode(image_bytes).decode()
    suffix = image_path.suffix.lower().lstrip(".")
    mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"

    response = client.models.generate_content(
        model=settings.extraction_model,
        contents=[
            {"role": "user", "parts": [
                {"inline_data": {"mime_type": mime, "data": b64}},
                {"text": OCR_PROMPT},
            ]},
        ],
    )
    return response.text
```

- [ ] **Step 2: Create pipeline orchestrator**

Create `src/lab_manager/intake/pipeline.py`:

```python
"""Document intake pipeline: image → OCR → extract → store."""
from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from lab_manager.config import get_settings
from lab_manager.intake.ocr import extract_text_from_image
from lab_manager.intake.extractor import extract_from_text
from lab_manager.intake.schemas import ExtractedDocument
from lab_manager.models.document import Document
from lab_manager.models.order import Order, OrderItem
from lab_manager.models.vendor import Vendor


def process_document(image_path: Path, db: Session) -> Document:
    """Process a scanned document image end-to-end.

    1. Copy file to uploads/
    2. Run OCR
    3. Extract structured data
    4. Save Document record
    5. If high confidence, create Order + OrderItems
    """
    settings = get_settings()

    # 1. Copy to uploads
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / image_path.name
    if not dest.exists():
        shutil.copy2(image_path, dest)

    # 2. OCR
    ocr_text = extract_text_from_image(image_path)

    # 3. Extract structured data
    extracted = extract_from_text(ocr_text)

    # 4. Save Document
    doc = Document(
        file_path=str(dest),
        file_name=image_path.name,
        document_type=extracted.document_type,
        vendor_name=extracted.vendor_name,
        ocr_text=ocr_text,
        extracted_data=extracted.model_dump(),
        extraction_model=settings.extraction_model,
        extraction_confidence=extracted.confidence,
        status="extracted",
    )
    db.add(doc)
    db.flush()

    # 5. Auto-create order if confidence is high enough
    threshold = settings.auto_approve_threshold
    if extracted.confidence and extracted.confidence >= threshold:
        _create_order_from_extraction(extracted, doc, db)
        doc.status = "approved"
    else:
        doc.status = "needs_review"

    db.commit()
    db.refresh(doc)
    return doc


def _create_order_from_extraction(
    extracted: ExtractedDocument, doc: Document, db: Session
) -> Order:
    """Create Order + OrderItems from extracted data."""
    # Find or create vendor
    vendor = db.query(Vendor).filter(Vendor.name == extracted.vendor_name).first()
    if not vendor:
        vendor = Vendor(name=extracted.vendor_name)
        db.add(vendor)
        db.flush()

    order = Order(
        po_number=extracted.po_number,
        vendor_id=vendor.id,
        delivery_number=extracted.delivery_number,
        invoice_number=extracted.invoice_number,
        status="received",
        document_id=doc.id,
        received_by=extracted.received_by,
    )

    # Parse dates safely
    if extracted.order_date:
        try:
            from datetime import date

            order.order_date = date.fromisoformat(extracted.order_date)
        except ValueError:
            pass

    db.add(order)
    db.flush()

    for item_data in extracted.items:
        order_item = OrderItem(
            order_id=order.id,
            catalog_number=item_data.catalog_number,
            description=item_data.description,
            quantity=item_data.quantity or 1,
            unit=item_data.unit,
            lot_number=item_data.lot_number,
            batch_number=item_data.batch_number,
        )
        db.add(order_item)

    return order
```

- [ ] **Step 3: Commit**

```bash
git add src/lab_manager/intake/
git commit -m "feat(intake): add OCR wrapper and intake pipeline orchestrator"
```

---

## Chunk 4: Search, Alerts, and Deployment

### Task 12: Meilisearch integration

**Files:**
- Create: `src/lab_manager/services/__init__.py`
- Create: `src/lab_manager/services/search.py`

- [ ] **Step 1: Create search service**

```python
"""Meilisearch integration for full-text search."""
from __future__ import annotations

import meilisearch
from sqlalchemy.orm import Session

from lab_manager.config import get_settings
from lab_manager.models.product import Product
from lab_manager.models.order import Order, OrderItem
from lab_manager.models.vendor import Vendor


def get_search_client():
    settings = get_settings()
    return meilisearch.Client(settings.meilisearch_url, settings.meilisearch_api_key)


def sync_products(db: Session):
    """Sync all products to Meilisearch."""
    client = get_search_client()
    products = db.query(Product).all()
    docs = [
        {
            "id": p.id,
            "catalog_number": p.catalog_number,
            "name": p.name,
            "category": p.category,
            "cas_number": p.cas_number,
            "vendor_id": p.vendor_id,
        }
        for p in products
    ]
    if docs:
        client.index("products").add_documents(docs)


def sync_orders(db: Session):
    """Sync order items to Meilisearch for search."""
    client = get_search_client()
    items = db.query(OrderItem).all()
    docs = [
        {
            "id": i.id,
            "catalog_number": i.catalog_number,
            "description": i.description,
            "lot_number": i.lot_number,
            "order_id": i.order_id,
        }
        for i in items
    ]
    if docs:
        client.index("order_items").add_documents(docs)


def search(query: str, index: str = "products", limit: int = 20) -> list[dict]:
    """Search across indexed data."""
    client = get_search_client()
    result = client.index(index).search(query, {"limit": limit})
    return result["hits"]
```

- [ ] **Step 2: Commit**

```bash
git add src/lab_manager/services/
git commit -m "feat(search): add Meilisearch sync and search service"
```

---

### Task 13: Expiry alerts service

**Files:**
- Create: `src/lab_manager/services/alerts.py`

- [ ] **Step 1: Create alerts service**

```python
"""Expiry and low-stock alert checks."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from lab_manager.models.inventory import InventoryItem


def get_expiring_items(db: Session, days_ahead: int = 30) -> list[InventoryItem]:
    """Find inventory items expiring within the given number of days."""
    cutoff = date.today() + timedelta(days=days_ahead)
    return (
        db.query(InventoryItem)
        .filter(
            InventoryItem.expiry_date is not None,
            InventoryItem.expiry_date <= cutoff,
            InventoryItem.status == "available",
        )
        .all()
    )


def get_low_stock_items(db: Session, threshold: float = 1) -> list[InventoryItem]:
    """Find items at or below minimum stock level."""
    return (
        db.query(InventoryItem)
        .filter(
            InventoryItem.quantity_on_hand <= threshold,
            InventoryItem.status == "available",
        )
        .all()
    )
```

- [ ] **Step 2: Commit**

```bash
git add src/lab_manager/services/alerts.py
git commit -m "feat(alerts): add expiry and low-stock alert checks"
```

---

### Task 14: Batch processing script for existing scans

**Files:**
- Create: `scripts/seed_vendors.py`
- Create: `scripts/process_scans.py`

- [ ] **Step 1: Create vendor seed script**

Create `scripts/seed_vendors.py`:

```python
#!/usr/bin/env python3
"""Seed the database with known vendors from our scan data."""
from sqlalchemy.orm import Session
from lab_manager.database import get_engine
from lab_manager.models.vendor import Vendor
from sqlmodel import SQLModel

VENDORS = [
    {"name": "EMD Millipore Corporation", "aliases": ["MilliporeSigma", "Merck", "Sigma-Aldrich"]},
    {"name": "Sigma-Aldrich", "aliases": ["Merck"]},
    {"name": "Targetmol Chemicals Inc.", "aliases": ["TargetMol"]},
    {"name": "Biohippo Inc.", "aliases": ["biohippo"]},
    {"name": "Thermo Fisher Scientific", "aliases": ["Invitrogen", "Life Technologies", "Pierce"]},
    {"name": "BioLegend Inc", "aliases": ["BioLegend"]},
    {"name": "VWR International", "aliases": ["Avantor", "VWR"]},
    {"name": "Genesee Scientific", "aliases": []},
    {"name": "ALSTEM Inc.", "aliases": ["ALSTEM"]},
    {"name": "Westnet Inc.", "aliases": ["Westnet"]},
    {"name": "Staples Inc.", "aliases": ["Staples"]},
]


def main():
    engine = get_engine()
    with Session(engine) as db:
        for v in VENDORS:
            existing = db.query(Vendor).filter(Vendor.name == v["name"]).first()
            if not existing:
                db.add(Vendor(name=v["name"], aliases=v["aliases"]))
                print(f"  Added: {v['name']}")
            else:
                print(f"  Exists: {v['name']}")
        db.commit()
    print("Done.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create batch scan processor**

Create `scripts/process_scans.py`:

```python
#!/usr/bin/env python3
"""Process all scanned documents in shenlab-docs/ through the intake pipeline."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from sqlalchemy.orm import Session

from lab_manager.database import get_engine
from lab_manager.intake.pipeline import process_document


def main():
    scan_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("shenlab-docs")
    if not scan_dir.exists():
        raise SystemExit(f"Directory not found: {scan_dir}")

    engine = get_engine()
    images = sorted(
        p for p in scan_dir.iterdir()
        if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    )
    print(f"Found {len(images)} images in {scan_dir}")

    for i, img in enumerate(images, 1):
        print(f"[{i}/{len(images)}] {img.name}...", end=" ", flush=True)
        t0 = time.time()
        try:
            with Session(engine) as db:
                doc = process_document(img, db)
                print(f"-> {doc.status} ({time.time() - t0:.1f}s)")
        except Exception as e:
            print(f"ERROR: {e}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Commit**

```bash
git add scripts/
git commit -m "feat(scripts): add vendor seeder and batch scan processor"
```

---

### Task 15: Dockerfile and deployment

**Files:**
- Create: `Dockerfile`
- Modify: `docker-compose.yml` (add app service)

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "lab_manager.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Add app service to docker-compose.yml**

Add to `docker-compose.yml`:

```yaml
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://labmanager:labmanager@db:5432/labmanager
      MEILISEARCH_URL: http://search:7700
    depends_on:
      - db
      - search
    volumes:
      - uploads:/app/uploads
```

Add `uploads:` to the volumes section.

- [ ] **Step 3: Test full deployment**

Run:
```bash
docker compose up -d
sleep 5
curl http://localhost:8000/api/health
curl http://localhost:8000/admin/
```

Expected: health returns `{"status":"ok"}`, admin UI loads.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "feat(deploy): add Dockerfile and full Docker Compose stack"
```

---

## Summary

| Chunk | Tasks | What it delivers |
|-------|-------|-----------------|
| 1: Foundation | T1-T7 | Models, DB schema, migrations, Docker infra |
| 2: API | T8 | FastAPI CRUD + SQLAdmin panel |
| 3: Intake | T9-T11 | OCR → extraction → database pipeline |
| 4: Deploy | T12-T15 | Search, alerts, batch processing, Docker deploy |

**After completing all tasks:**
- PostgreSQL with 9 tables, full schema, audit trail
- FastAPI REST API for all entities
- SQLAdmin web UI at `/admin/` for browse/edit/search
- Document intake pipeline: scan → OCR → extract → review → DB
- Meilisearch full-text search
- Expiry/low-stock alerts
- Docker Compose one-command deployment
- Batch processor for 279 existing scanned documents
