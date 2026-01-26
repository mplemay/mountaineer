from click import command, option

from mountaineer.cli import handle_build, handle_runserver, handle_watch


@command()
@option("--host", default="127.0.0.1")
@option("--port", default=5006)
def runserver(host: str, port: int):
    handle_runserver(
        package="example",
        webservice="example.main:app",
        webcontroller="example.app:mountaineer",
        host=host,
        port=port,
        subscribe_to_mountaineer=True,
    )


@command()
def watch():
    handle_watch(
        package="example",
        webcontroller="example.app:mountaineer",
        subscribe_to_mountaineer=True,
    )


@command()
def build():
    handle_build(
        webcontroller="example.app:mountaineer",
    )
