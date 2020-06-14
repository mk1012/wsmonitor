import click

import wsmonitor
from wsmonitor.scripts import wsmon


class ServerConfig:

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host: str = host
        self.port: int = port


pass_config = click.make_pass_decorator(ServerConfig, ensure=True)


@click.group()
@click.option("--host", default="127.0.0.1", help="The host the server is running on")
@click.option("--port", default=8766, help="The port the server is running on")
@pass_config
def cli(ctx: ServerConfig, host: str, port: int):
    ctx.host = host
    ctx.port = port


@cli.command()
@click.option("--initial", default=None, type=click.File("r"))
@pass_config
def server(ctx: ServerConfig, initial: click.File):
    click.echo('Starting ws server: %s' % ctx)
    # wsmon.main(ctx.config.host)


@cli.command()
@click.argument("uid")
@click.argument("cmd")
@click.option("--as-group", is_flag=True, help="Execute the process in its own process group.")
@pass_config
def add(config: ServerConfig, uid: str, cmd: str, as_group: bool):
    """
    Adds a new process with the given unique id and executes the specified command once started.
    """
    click.echo(f'Add command {uid}="{cmd}" group={as_group}')


@cli.command()
@click.argument("uid")
@pass_config
def start(config: ServerConfig, uid: str):
    """
    Starts the process with the given unique id.
    """
    click.echo(f'Start {uid}')


@cli.command()
@click.argument("uid")
@pass_config
def restart(config: ServerConfig, uid: str):
    """
    Re-starts the process with the given unique id.
    """
    click.echo(f'Re-start {uid}')


@cli.command()
@click.argument("uid")
@pass_config
def stop(config: ServerConfig, uid: str):
    """
    Stops the process with the given unique id.
    """
    click.echo(f'Stop {uid}')


@cli.command(name="list")
@pass_config
def list_processes(config: ServerConfig):
    """
    Stops the process with the given unique id.
    """
    click.echo(f'List processes')


if __name__ == "__main__":
    cli()
