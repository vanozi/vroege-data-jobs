## Database migrations

Alembic is configured under [`database/`](database/) and is the only supported
way to create or evolve the database schema.

Install dependencies first, then run migrations from the repository root.

Recommended PostgreSQL connection format:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/gebroeders-vroege
```

Create a new revision:

```powershell
alembic -c database/alembic.ini revision --autogenerate -m "describe change"
```

Apply all migrations:

```powershell
alembic -c database/alembic.ini upgrade head
```

Roll back one revision:

```powershell
alembic -c database/alembic.ini downgrade -1
```

Show the current database revision:

```powershell
alembic -c database/alembic.ini current
```

For a fresh database, the initial schema is included in
`database/migrations/versions/20260507_01_initial_schema.py`.
