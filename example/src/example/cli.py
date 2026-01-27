import uvicorn
from click import command, option


@command()
@option("--host", default="127.0.0.1")
@option("--port", default=5006)
def runserver(host: str, port: int) -> None:
    uvicorn.run("example.main:app", host=host, port=port, reload=True)
