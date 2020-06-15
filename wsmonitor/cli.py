import click
import json
import logging

from examples.ws_client import run_single_action_client
from wsmonitor.gui import main_window
from wsmonitor.scripts import wsmon

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')


# logging.getLogger().addHandler(logging.StreamHandler())


class ServerConfig:

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host: str = host
        self.port: int = port


pass_config = click.make_pass_decorator(ServerConfig, ensure=True)


@click.group()
@click.option("--host", default="127.0.0.1", help="The host the server is running on")
@click.option("--port", default=8765, help="The port the server is running on")
@click.option("-v", is_flag="True", help="Enable verbose output.")
@click.option("-vv", is_flag="True", help="Enable verbose verbose output.")
@pass_config
def cli(config: ServerConfig, host: str, port: int, v: bool, vv: bool):
    config.host = host
    config.port = port
    if v:
        logging.getLogger().setLevel(logging.INFO)
    if vv:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@pass_config
def gui(config: ServerConfig):
    """
    Start the graphical client.
    """
    click.echo('Starting the GUI: %s' % config)
    main_window.main()


@cli.command()
@click.option("--initial", default=None, type=click.File("r"), help="JSON file with the initial processes to load")
@pass_config
def server(config: ServerConfig, initial: click.File):
    """
    Starts the ProcessMonitor server.
    """
    click.echo('Starting ws server: %s' % config)
    wsmon.main(config.host, config.port)


@cli.command()
@click.argument("uid")
@click.argument("cmd")
@click.option("--as-group", is_flag=True, help="Execute the process in its own process group.")
@pass_config
def add(config: ServerConfig, uid: str, cmd: str, as_group: bool):
    """
    Adds a new process with the given unique id and executes the specified command once started.
    """
    result = run_single_action_client(config.host, config.port, "register", uid=uid, cmd=cmd, group=as_group)
    click.echo(f'Add command {uid}="{cmd}" group={as_group} -> {result}')


@cli.command()
@click.argument("uid")
@pass_config
def remove(config: ServerConfig, uid: str):
    """
    Removes the process with the given unique id.
    """
    result = run_single_action_client(config.host, config.port, "remove", uid=uid)
    click.echo(f'Remove command {uid}="{cmd}" group={as_group} -> {result}')


@cli.command()
@click.argument("uid")
@pass_config
def start(config: ServerConfig, uid: str):
    """
    Starts the process with the given unique id.
    """
    click.echo(f'Start {uid}')
    run_single_action_client(config.host, config.port, "start", uid=uid)


@cli.command()
@click.argument("uid")
@pass_config
def restart(config: ServerConfig, uid: str):
    """
    Re-starts the process with the given unique id.
    """
    click.echo(f'Re-start {uid}')
    run_single_action_client(config.host, config.port, "restart", uid=uid)


@cli.command()
@click.argument("uid")
@pass_config
def stop(config: ServerConfig, uid: str):
    """
    Stops the process with the given unique id.
    """
    click.echo(f'Stop {uid}')
    run_single_action_client(config.host, config.port, "stop", uid=uid)


@cli.command()
@click.option("--uid", default="")
@pass_config
def output(config: ServerConfig, uid: str):
    """
    Logs the output reported from the ProcessMonitor.
    """
    click.echo(f'Output')
    run_single_action_client(config.host, config.port, "output")


@cli.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="Output the process list as simple text not json.")
@pass_config
def list_processes(config: ServerConfig, as_json):
    """
    Lists all processes.
    """
    click.echo(f'Listing processes')
    data = run_single_action_client(config.host, config.port, "list")
    if data is not None:
        result = json.dumps(data, indent=True)
        click.echo(result)


if __name__ == "__main__":
    cli()
