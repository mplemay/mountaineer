from json import dumps as json_dumps

from mountaineer import _core as mountaineer_rs


def _escape_script_content(content: str) -> str:
    return content.replace("</", "<\\/")


def build_page_html(
    *,
    server_js: str,
    client_js: str,
    initial_data: dict,
    ssr_timeout: int,
) -> str:
    ssr_markup = mountaineer_rs.render_ssr(server_js, hard_timeout=ssr_timeout)
    data_payload = json_dumps(initial_data)
    data_script = _escape_script_content(f"window.__DATA__ = {data_payload};")
    client_script = _escape_script_content(client_js)

    return (
        "<!DOCTYPE html>"
        "<html>"
        "<head>"
        '<meta charset="utf-8">'
        "</head>"
        "<body>"
        f'<div id="root">{ssr_markup}</div>'
        f"<script>{data_script}</script>"
        f'<script type="module">{client_script}</script>'
        "</body>"
        "</html>"
    )
