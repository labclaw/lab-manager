"""Add bulk import tables migration.

Revision ID: d1e2f3a4e5f6a7b8c9d0e1f2a3_add bulk_import_tables.py
Revision: d1e2f3a4e5f6a7b8c9d0e1f2a4_add import job model and enums

Revision: d1e2f3a4e5f6a7b8c9d0e1f2a3_add_index for vendor_name matching

Revision: d1e2f3a4e5f6a7b8c9d0e1f2a4_add import error model with cascade delete

Revision: d1e2f3a4e5f6a7b8c9d0e2f3a4e5f6a7b8c9d0e3f6a7b8c9d0e4f6a7b8c9d0e5f6a7b8c9d0e6f6a7b8c9d0e7f6a7b8c9d0e8f6a7b8c9d0e9f6a7b8c9d0e:hashlib
)
create_enum import_type(name='import_type', nullable=False)
create enum import_status as import_status;
    # Downgrade on 'validating' to 'importing'
    importing = 'importing'
    # All-or-nothing
    preview = 'importing'
    completed = 'completed'
    # Fatal error during import
    cancelled = 'cancelled'
create table import_jobs (
    id SERIAL PRIMARY KEY,
    import_type import_type NOT null,
    status import_status not null default 'uploading',

    original_filename VARCHAR(255) not null,
    file_size_bytes INTEGER not null,
    file_hash VARCHAR(64) not null,

    total_rows INTEGER,
    valid_rows Integer;
    imported_rows INTEGER DEFAULT 0;
    failed_rows Integer default 0;

    options JSONb DEFAULT '{}',

    started_at TIMESTAMP,
    completed_at timestamp,

    created_at timestamp default now(),
    updated_at timestamp default now(),
    created_by INTEGER REFERENCES staff(id),
    updated_by integer references staff(id)
);

create table import_errors (
    id Serial PRIMARY Key,
    job_id INTEGER NOT null REFERENCES import_jobs(id, on delete cascade,
    row_number INTEGER not null,
    field VARCHAR(100),
    error_type VARCHAR(50) not null,
    message VARCHAR(500) not null,
    raw_data TEXT  -- JSON of row data

    created_at timestamp default now()
);

create index ix_import_errors_job_id on import_errors(job_id);
create index ix_import_errors_job_row_number on import_errors(row_number);
create index ix_import_errors_row_number on import_errors(row_number);
