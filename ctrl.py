#!/usr/bin/env python

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parent / "munggoggo"))

from behaviour import Behaviour
from core import Core
from messages import ListBehav, ManageBehav, ListTraceStore
from twpy import coro
from utils import setup_logging

_log = logging.getLogger()
setup_logging(level=logging.WARNING)

logging.getLogger("aio_pika").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.INFO)

LOGGING_LEVEL = logging.WARNING


class Ctrl(Core):
    @property
    def behaviour(self) -> Behaviour:
        return Behaviour(self, binding_keys=["system"], configure_rpc=True)

    async def setup(self) -> None:
        await self.add_runtime_dependency(self.behaviour)


@click.group()
@click.option("--debug", "-d", is_flag=True)
@click.pass_context
def cli(ctx, debug):
    ctx.ensure_object(dict)
    global LOGGING_LEVEL
    if debug:
        LOGGING_LEVEL = logging.DEBUG


@cli.command()
@click.argument("msg")
@click.argument("msg_type")
@click.argument("target")
@click.pass_context
@coro
async def send_message(ctx, msg, msg_type, target):
    async with Ctrl(identity="Ctrl") as a:
        a.logger.setLevel(LOGGING_LEVEL)
        click.echo(f"Sending type: '{msg_type}' msg: {msg} to {target}")
        await a.direct_send(msg=msg, msg_type=msg_type, target=target)
        await asyncio.sleep(0.1)  # required for context cleanup
        # print(f"Duration: {datetime.now() - start}")


@cli.command()
@click.argument("msg")
@click.argument("msg_type")
@coro
async def broadcast(msg, msg_type):
    async with Ctrl(identity="Ctrl") as a:
        a.logger.setLevel(LOGGING_LEVEL)
        click.echo(f"Broadcasting type: '{msg_type}' msg: {msg}")
        await a.fanout_send(msg=msg, msg_type=msg_type)
        await asyncio.sleep(0.1)  # required for context cleanup
        # print(f"Duration: {datetime.now() - start}")


@cli.command()
@click.argument("agent")
@click.pass_context
@coro
async def list_behaviour(ctx, agent):
    async with Ctrl(identity="Ctrl") as a:
        a.logger.setLevel(LOGGING_LEVEL)

        if not await target_exists(a, agent):
            return False

        click.echo(f"Listing behaviours of {agent}:")
        obj = ListBehav()
        result = await a.call(obj.to_rpc(), agent)
        for behav in result.to_dict().get("behavs", list()):
            click.secho(behav, fg="cyan")
        await asyncio.sleep(0.1)  # required for context cleanup
        # print(f"Duration: {datetime.now() - start}")


@cli.command()
@click.pass_context
@coro
async def list_peers(ctx):
    async with Ctrl(identity="Ctrl") as a:
        a.logger.setLevel(LOGGING_LEVEL)
        click.echo(f"Listing peers.")
        peers = await a.list_peers()
        for peer in peers:
            click.secho(f"{peer.get('name')}", fg="cyan")
        await asyncio.sleep(0.1)  # required for context cleanup
        # print(f"Duration: {datetime.now() - start}")


async def target_exists(core: Core, target: str) -> bool:
    peers = [peer.get("name") for peer in await core.list_peers()]
    if target not in peers:
        click.secho(f"Invalid target: {target}. Choose one of: {peers}.", fg="red")
        return False
    return True


@cli.command()
@click.argument("command")
@click.argument("target")
@click.argument("behav")
@click.pass_context
@coro
async def call(ctx, command, target, behav):
    async with Ctrl(identity="Ctrl") as a:
        a.logger.setLevel(LOGGING_LEVEL)

        if not await target_exists(a, target):
            return False

        # peers = [peer.get("name") for peer in await a.list_peers()]
        # if target not in peers:
        #     click.echo(f"Invalid target: {target}. Choose one of: {peers}.")
        #     return False
        click.echo(f"Sending command: '{command}' to {target}:{behav}")
        obj = ManageBehav(behav=behav, command=None,)
        if command in ["Stop", "stop"]:
            obj.command = "stop"
        elif command in ["Start", "start"]:
            obj.command = "start"
        else:
            click.secho(f"Invalid command.", fg="red")
            click.secho(f"Expected one of [start, stop]", fg="red")
            return False

        result = await a.call(obj.to_rpc(), target=target)
        click.secho(f"rpc result: {result}", fg="cyan")

        await asyncio.sleep(0.1)  # required for context cleanup
        # print(f"Duration: {datetime.now() - start}")


@cli.command()
@click.argument("target")
@click.option("--limit", "-d")
@click.option("--sender", "-s")
@click.pass_context
@coro
async def list_traces(ctx, target, limit, sender):
    # assert isinstance(limit, int), f"limit must be integer"
    async with Ctrl(identity="Ctrl") as a:
        a.logger.setLevel(LOGGING_LEVEL)

        if not await target_exists(a, target):
            return False

        if limit is not None:
            limit = int(limit)
        obj = ListTraceStore(app_id=sender, limit=limit,)

        result = await a.call(obj.to_rpc(), target=target)
        for entry in result.traces:
            click.echo(entry[1])

        click.echo(f"Total number of records: {len(result.traces)}.")

        await asyncio.sleep(0.1)  # required for context cleanup
        # print(f"Duration: {datetime.now() - start}")


if __name__ == "__main__":
    """
    Examples:
    
    python ctrl.py broadcast '{"c_type": "DemoData", "c_data": "{\"message\": \"Hallo\", \"date\": 1546300800.0}"}' "CUSTOM"
    python ctrl.py list-behaviour SqlAgent
    python ctrl.py send-message '{"c_type": "DemoData", "c_data": "{\"message\": \"Hallo2\", \"date\": 1546300800.0}"}' "CUSTOM" SqlAgent
    python ctrl.py call start SqlAgent SqlAgent.SqlBehav
    python ctrl.py call start SqlAgent SqlBehav
    python ctrl.py list-traces SqlAgent --sender Ctrl
    """
    start = datetime.now()

    # cli(['-d', 'list-peers'], obj=dict(start=start))
    # list_peers([])

    # list_behaviour(['SqlAgenttt'])

    # broadcast([r'{"c_type": "DemoData", "c_data": "{\"message\": \"Hallo\", \"date\": 1546300800.0}"}', "CUSTOM"])
    # broadcast(['wrong format', "CUSTOM"])

    # send_message([r'{"c_type": "DemoData", "c_data": "{\"message\": \"Hallo\", \"date\": 1546300800.0}"}', "CUSTOM", "SqlAgent"])

    # call(['Stop', 'SqlAgent', "SqlAgent.SqlBehav"])
    # call(['Stop', 'SqlAgent', "SqlBehav"])
    # call(['start', 'SqlAgent', "SqlBehav"])

    # list_traces(["SqlAgent"])
    # list_traces(["SqlAgent", "--limit", 1])
    # list_traces(["SqlAgent", "--sender", "Ctrl"])

    ################################################################################
    # activate CLI
    ################################################################################
    cli(obj=dict(start=start))
    print(f"Duration: {datetime.now() - start}")
