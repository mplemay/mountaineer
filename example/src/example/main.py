from fastapi import FastAPI

from example.app import mountaineer

# Expose for ASGI
app = FastAPI()
app.mount(path="/", app=mountaineer, name="website")
