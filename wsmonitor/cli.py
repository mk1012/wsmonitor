import asyncio
import json
import logging

import click

from wsmonitor.process.process import Process
from wsmonitor.ws_client import run_single_action_client

try:
    from wsmonitor.gui import main_window
except ImportError:
    print("PySide2 is not installed")
from wsmonitor.util import run
from wsmonitor.ws_process_monitor import WebsocketProcessMonitor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s',
                    datefmt='%H:%M:%S')


class ServerConfig:

    def __init__(self, host: str = "127.0.0.1", port: int = 8766):
        self.host: str = host
        self.port: int = port


pass_config = click.make_pass_decorator(ServerConfig, ensure=True)


def run_server(host, port, config_filepath=None):
    wpm = WebsocketProcessMonitor()

    if config_filepath is not None:
        with open(config_filepath, "r") as config_file:
            data = config_file.read()
            config_file.close()

            import json
            processes = json.loads(data)
            for process_config in processes:
                process = wpm.add_process(process_config["uid"],
                                          process_config["cmd"],
                                          process_config["group"])

                autostart = process_config.get("auto_start", None)
                if isinstance(process, Process) and bool(autostart):
                    delay = autostart if isinstance(autostart, int) else 0
                    asyncio.get_event_loop().call_later(
                        delay, process.start_as_task)

    run(wpm.run(host, port), wpm.shutdown)


@click.group()
@click.option("--host", default="127.0.0.1",
              help="The host the server is running on")
@click.option("--port", default=8766, help="The port the server is running on")
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
@click.option("--initial", default=None,
              help="JSON file with the initial processes to load")
@pass_config
def server(config: ServerConfig, initial: str):
    """
    Starts the ProcessMonitor server.
    """
    click.echo('Starting ws server: %s' % config)
    run_server(config.host, config.port, initial)


@cli.command()
@click.argument("uid")
@click.argument("cmd")
@click.option("--as-group", is_flag=True,
              help="Execute the process in its own process group.")
@pass_config
def add(config: ServerConfig, uid: str, cmd: str, as_group: bool):
    """
    Adds a new process with the given unique id and executes the specified command once started.
    """
    result = run_single_action_client(config.host, config.port, "add", uid=uid,
                                      cmd=cmd, group=as_group)
    click.echo(f'Add command {uid}="{cmd}" group={as_group} -> {result}')


@cli.command()
@click.argument("uid")
@pass_config
def remove(config: ServerConfig, uid: str):
    """
    Removes the process with the given unique id.
    """
    result = run_single_action_client(config.host, config.port, "remove",
                                      uid=uid)
    click.echo(f'Remove command {uid} -> {result}')


@cli.command()
@click.argument("uid")
@pass_config
def start(config: ServerConfig, uid: str):
    """
    Starts the process with the given unique id.
    """
    result = run_single_action_client(config.host, config.port, "start",
                                      uid=uid)
    click.echo(f'Start "{uid}" -> {result}')


@cli.command()
@click.argument("action")
@click.argument("project")
@click.argument("uid")
@pass_config
def action(config: ServerConfig, action: str, project: str, uid: str):
    """
    Sends the given action command.
    """
    result = run_single_action_client(config.host, config.port, action,
                                      uid=uid, project=project)
    click.echo(f'Action "{action}" -> {result}')


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
    run_single_action_client(config.host, config.port, "output")


@cli.command(name="list")
@click.option("--json", "as_json", is_flag=True,
              help="Output the process list as simple text not json.")
@pass_config
def list_processes(config: ServerConfig, as_json):
    """
    Lists all processes.
    """
    data = run_single_action_client(config.host, config.port, "list")
    if data is not None:
        result = json.dumps(data, indent=True)
        click.echo(result)
    else:
        click.echo("No processes could be retrieved")


if __name__ == "__main__":
    cli()
