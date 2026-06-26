"""Seeding layer for EGI. Creates clearly-marked TEST DATA (events, cities,
incidents, persons, reports) for local development and demos.

Every seeded row carries the deterministic id prefix ``egi-seed-`` so that
``egi unseed`` can remove exactly what was seeded and nothing else. No row
created here may ever be mistaken for a real crisis record (plan §3)."""
