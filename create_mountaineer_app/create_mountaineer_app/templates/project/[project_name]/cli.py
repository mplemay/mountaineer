from click import command, option
from mountaineer.cli import handle_runserver, handle_watch, handle_build


@command()
@option("--host", default="127.0.0.1", help="Host to run the server on")
@option("--port", default=5006, help="Port to run the server on")
def runserver(host: str, port: int):
    handle_runserver(
        package="{{project_name}}",
        webservice="{{project_name}}.main:app",
        webcontroller="{{project_name}}.app:mountaineer",
        host=host,
        port=port,
    )


@command()
def watch():
    handle_watch(
        package="{{project_name}}",
        webcontroller="{{project_name}}.app:mountaineer",
    )


@command()
def build():
    handle_build(
        webcontroller="{{project_name}}.app:mountaineer",
    )
