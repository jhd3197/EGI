"""``egi user`` — manage operator user accounts (plan-08).

Thin Click wrappers over ``server/modules/users.py``. Every callback puts the
server on ``sys.path`` via ``ensure_server_importable()`` before importing it,
so the CLI always touches the same DB as a running ``egi backend``.
"""

import click

# Roles must match users.VALID_ROLES; we duplicate them here only so Click can
# build the --role choice without importing the server at module load time.
_ROLE_CHOICES = ["viewer", "operator", "commander", "admin"]


def _users():
    """Import the server users module lazily (after pinning DB_PATH)."""
    from ..paths import ensure_server_importable

    ensure_server_importable()
    from modules import users  # noqa: E402

    return users


def _echo_password(password):
    click.secho("Generated password (shown only once — save it now):", fg="yellow")
    click.secho(f"  {password}", fg="yellow", bold=True)


@click.group(name="user", context_settings={"help_option_names": ["-h", "--help"]})
def user():
    """Create and manage operator user accounts."""


@user.command()
@click.option("--email", required=True, help="Login email for the new user.")
@click.option(
    "--role",
    required=True,
    type=click.Choice(_ROLE_CHOICES),
    help="Account role (privilege level).",
)
@click.option("--name", default=None, help="Display name (optional).")
@click.option(
    "--password",
    default=None,
    help="Password (omit to auto-generate and print once).",
)
def create(email, role, name, password):
    """Create a new user account."""
    users = _users()
    generated = password is None
    if generated:
        password = users.generate_token()
    try:
        new_user = users.create_user(email=email, password=password, role=role, name=name)
    except ValueError as exc:
        click.secho(f"Error: {exc}", fg="red")
        raise SystemExit(1)

    if generated:
        _echo_password(password)
    click.secho(
        f"Created user {new_user['id']} <{new_user['email']}> role={new_user['role']}",
        fg="green",
    )


@user.command(name="list")
def list_cmd():
    """List all user accounts."""
    users = _users()
    rows = users.list_users()
    if not rows:
        click.echo("No users found.")
        return

    header = f"{'EMAIL':<32} {'ROLE':<10} {'ACTIVE':<7} {'NAME':<20} LAST_LOGIN"
    click.echo(header)
    click.echo("-" * len(header))
    for u in rows:
        active = "yes" if u.get("active") else "no"
        click.echo(
            f"{(u.get('email') or ''):<32} "
            f"{(u.get('role') or ''):<10} "
            f"{active:<7} "
            f"{(u.get('name') or ''):<20} "
            f"{u.get('last_login_at') or '-'}"
        )


@user.command()
@click.option("--email", required=True, help="Email of the user to reset.")
@click.option(
    "--password",
    default=None,
    help="New password (omit to auto-generate and print once).",
)
def passwd(email, password):
    """Reset a user's password (revokes their existing tokens)."""
    users = _users()
    target = users.get_user_by_email(email)
    if not target:
        click.secho(f"Error: no user with email {email!r}", fg="red")
        raise SystemExit(1)

    generated = password is None
    if generated:
        password = users.generate_token()
    users.set_password(target["id"], password)

    if generated:
        _echo_password(password)
    click.secho(f"Password reset for <{target['email']}>.", fg="green")


@user.command(name="set-role")
@click.option("--email", required=True, help="Email of the user to update.")
@click.option(
    "--role",
    required=True,
    type=click.Choice(_ROLE_CHOICES),
    help="New role.",
)
def set_role(email, role):
    """Change a user's role."""
    users = _users()
    target = users.get_user_by_email(email)
    if not target:
        click.secho(f"Error: no user with email {email!r}", fg="red")
        raise SystemExit(1)
    users.update_user(target["id"], role=role)
    click.secho(f"Role for <{target['email']}> set to {role}.", fg="green")


@user.command()
@click.option("--email", required=True, help="Email of the user to deactivate.")
def deactivate(email):
    """Deactivate a user (blocks login, keeps the account)."""
    users = _users()
    target = users.get_user_by_email(email)
    if not target:
        click.secho(f"Error: no user with email {email!r}", fg="red")
        raise SystemExit(1)
    users.update_user(target["id"], active=0)
    click.secho(f"Deactivated <{target['email']}>.", fg="green")


@user.command()
@click.option("--email", required=True, help="Email of the user to activate.")
def activate(email):
    """Reactivate a previously deactivated user."""
    users = _users()
    target = users.get_user_by_email(email)
    if not target:
        click.secho(f"Error: no user with email {email!r}", fg="red")
        raise SystemExit(1)
    users.update_user(target["id"], active=1)
    click.secho(f"Activated <{target['email']}>.", fg="green")


@user.command()
@click.option("--email", required=True, help="Email of the user to delete.")
@click.option("--confirm", is_flag=True, help="Required: confirm permanent deletion.")
def delete(email, confirm):
    """Permanently delete a user and all their tokens."""
    users = _users()
    if not confirm:
        click.secho("Refusing to delete without --confirm.", fg="red")
        raise SystemExit(1)
    target = users.get_user_by_email(email)
    if not target:
        click.secho(f"Error: no user with email {email!r}", fg="red")
        raise SystemExit(1)
    users.delete_user(target["id"])
    click.secho(f"Deleted <{target['email']}>.", fg="green")
