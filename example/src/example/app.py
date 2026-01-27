from example.config import AppConfig
from example.controllers.complex import page as complex_page
from example.controllers.detail import page as detail_page
from example.controllers.home import page as home_page
from example.controllers.root_layout import page as root_layout_page
from example.controllers.stream import page as stream_page
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
mountaineer.include_page(root_layout_page)
mountaineer.include_page(home_page)
mountaineer.include_page(detail_page)
mountaineer.include_page(complex_page)
mountaineer.include_page(stream_page)
