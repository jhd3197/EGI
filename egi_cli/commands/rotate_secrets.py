"""``egi rotate-secrets`` — incident-response credential rotation (plan-15 §9.3).

After a suspected breach, invalidate every active bearer token so all sessions
must re-authenticate. Optionally scope to a single user. This does NOT change
passwords (users keep their credentials and simply log in again); pair it with a
forced password reset and a rotated ``BACKUP_ENCRYPT_KEY`` / ``OPERATOR_TOKENS``
per docs/OPERATIONS.md.

Touches the same DB as a running ``egi backend`` (paths pinned to server/).
"""

import click


@click.command(name="rotate-secrets")
@click.option("--user-id", default=None, help="Only revoke this user's tokens (default: all).")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
def rotate_secrets(user_id, yes):
    """Invalidate all bearer tokens (forces re-login) after a suspected breach."""
    from ..paths import ensure_server_importable

    ensure_server_importable()
    import db  # noqa: E402
    from modules import users  # noqa: E402

    db.init_db()  # idempotent

    scope = f"user {user_id}" if user_id else "ALL users"
    if not yes:
        click.secho(f"This revokes every bearer token for {scope}.", fg="red")
        click.echo("Affected sessions must log in again. Re-run with --yes to proceed.")
        return

    revoked = users.revoke_all_tokens(user_id=user_id)
    click.secho(f"Revoked {revoked} token(s) for {scope}.", fg="green")

    # Record the rotation as a system + audit event (best-effort).
    try:
        from modules import audit, system_events

        actor = "egi rotate-secrets"
        system_events.record(
            "secrets_rotated",
            f"Revoked {revoked} token(s) for {scope}",
            level="warning",
        )
        audit.log_action(actor, "rotate_secrets", "auth", user_id, detail=f"revoked={revoked}")
    except Exception:
        pass

    click.secho("Next steps (docs/OPERATIONS.md):", fg="yellow")
    click.echo("  - Force password resets for affected users (egi user passwd …).")
    click.echo("  - Rotate BACKUP_ENCRYPT_KEY and any OPERATOR_TOKENS / provider keys.")
    click.echo("  - Review GET /audit/log and GET /system/events for the breach window.")
