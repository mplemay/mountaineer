from example.config import AppConfig
from example.controllers.complex import ComplexController
from example.controllers.detail import DetailController
from example.controllers.home import HomeController
from example.controllers.root_layout import RootLayoutController
from example.controllers.stream import StreamController
from mountaineer import LinkAttribute, Metadata, Mountaineer
from mountaineer.client_compiler.postcss import PostCSSBundler

mountaineer = Mountaineer(
    global_metadata=Metadata(
        links=[LinkAttribute(rel="stylesheet", href="/static/app_main.css")]
    ),
    custom_builders=[
        PostCSSBundler(),
    ],
    config=AppConfig(),
)
mountaineer.register(HomeController())
mountaineer.register(DetailController())
mountaineer.register(ComplexController())
mountaineer.register(StreamController())
mountaineer.register(RootLayoutController())
