from json import dumps as json_dumps

from mountaineer import _core as mountaineer_rs


def _escape_script_content(content: str) -> str:
    return content.replace("</", "<\\/")


# Polyfill for TextEncoder/TextDecoder in V8 environment
POLYFILLS = """
if (typeof TextEncoder === "undefined") {
    class TextEncoder {
        encode(string) {
            if (typeof string !== 'string') {
                string = String(string);
            }
            const len = string.length;
            const res = new Uint8Array(len * 3);
            let pos = 0;
            for (let i = 0; i < len; i++) {
                const point = string.charCodeAt(i);
                if (point <= 0x007f) {
                    res[pos++] = point;
                } else if (point <= 0x07ff) {
                    res[pos++] = 0xc0 | (point >> 6);
                    res[pos++] = 0x80 | (point & 0x3f);
                } else {
                    res[pos++] = 0xe0 | (point >> 12);
                    res[pos++] = 0x80 | ((point >> 6) & 0x3f);
                    res[pos++] = 0x80 | (point & 0x3f);
                }
            }
            return res.subarray(0, pos);
        }
    }
    globalThis.TextEncoder = TextEncoder;
}

if (typeof TextDecoder === "undefined") {
    class TextDecoder {
        decode(arr) {
            return String.fromCharCode.apply(null, arr);
        }
    }
    globalThis.TextDecoder = TextDecoder;
}
"""


def build_page_html(
    *,
    server_js: str,
    client_js: str,
    initial_data: dict,
    ssr_timeout: int,
) -> str:
    full_server_js = POLYFILLS + server_js
    ssr_markup = mountaineer_rs.render_ssr(full_server_js, hard_timeout=ssr_timeout)
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
