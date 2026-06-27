"""``egi deploy-staging`` — bring up the minimal staging stack (plan-15 §10.3).

A convenience wrapper around ``deploy/docker-compose.staging.yml``. By default it
is **safe and non-destructive**: it only prints the steps (compose up, seeding
demo data, health check). Pass ``--up`` to actually shell out to
``docker compose ... up -d --build``.

    egi deploy-staging            # print the steps (does nothing to docker)
    egi deploy-staging --up       # launch the staging stack
    egi deploy-staging --up --seed  # launch, then seed demo data

Top-level imports are limited to ``click``; everything else is imported lazily in
the callback, mirroring the other operator commands.
"""

import click


@click.command(name="deploy-staging")
@click.option("--up", is_flag=True,
              help="Actually run `docker compose ... up -d --build` (default: just print steps).")
@click.option("--seed", is_flag=True,
              help="With --up: also seed demo data (egi seed + generate-synthetic) in the container.")
@click.option("--detach/--no-detach", default=True, show_default=True,
              help="Run compose detached (-d).")
def deploy_staging(up, seed, detach):
    """Print (or, with --up, launch) the staging Docker Compose stack."""
    import os
    import shutil
    import subprocess

    from ..paths import REPO_ROOT

    compose_file = REPO_ROOT / "deploy" / "docker-compose.staging.yml"
    if not compose_file.exists():
        raise click.ClickException(f"Compose file not found: {compose_file}")

    rel = os.path.relpath(compose_file, REPO_ROOT)
    base = f"docker compose -f {rel}"

    up_args = ["docker", "compose", "-f", str(compose_file), "up", "--build"]
    if detach:
        up_args.append("-d")

    seed_cmds = [
        f"{base} exec egi egi seed",
        f"{base} exec egi egi generate-synthetic --count 500",
    ]

    if not up:
        click.secho("EGI staging stack — steps (dry run; nothing executed)", fg="cyan", bold=True)
        click.echo(f"\nCompose file: {compose_file}")
        click.echo("\n1. Create staging.env (keep secrets out of git):")
        click.echo("     cp server/.env.example deploy/staging.env   # then edit")
        click.echo("\n2. Build and start the stack:")
        click.echo(f"     {base} up --build{' -d' if detach else ''}")
        click.echo("\n3. Seed demo data (optional, safe for staging):")
        for c in seed_cmds:
            click.echo(f"     {c}")
        click.echo("\n4. Verify it is healthy:")
        click.echo("     curl -s http://127.0.0.1:3000/health | python3 -m json.tool")
        click.echo("\nRe-run with --up to execute step 2 (add --seed to also run step 3).")
        click.secho("\nStaging is for FAKE data only — never point it at real records.", fg="yellow")
        return

    # --up: actually launch. Make sure docker is available first.
    if shutil.which("docker") is None:
        raise click.ClickException("`docker` not found on PATH. Install Docker or run without --up.")

    click.secho(f"$ {' '.join(up_args)}", fg="cyan")
    result = subprocess.run(up_args, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        raise click.ClickException(f"docker compose up failed (exit {result.returncode}).")
    click.secho("Staging stack started.", fg="green")

    if seed:
        for c in seed_cmds:
            click.secho(f"$ {c}", fg="cyan")
            r = subprocess.run(c.split(), cwd=str(REPO_ROOT))
            if r.returncode != 0:
                click.secho(f"  seeding step failed (exit {r.returncode}); continuing.", fg="yellow")

    click.echo("\nVerify: curl -s http://127.0.0.1:3000/health | python3 -m json.tool")
    click.secho("Staging is for FAKE data only — never point it at real records.", fg="yellow")
