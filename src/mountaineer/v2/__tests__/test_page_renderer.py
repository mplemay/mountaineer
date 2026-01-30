from unittest.mock import ANY

from mountaineer.v2.page_renderer import build_page_html


def test_build_page_html_structure(mock_ssr):
    """
    Test that the HTML is assembled correctly with SSR content and scripts.
    """
    html = build_page_html(
        server_js="server_code",
        client_js="console.log('client')",
        initial_data={"foo": "bar"},
        ssr_timeout=10,
    )

    # Check for critical parts
    assert "<!DOCTYPE html>" in html
    assert "<html>" in html
    assert "<body>" in html

    # Check SSR content injection (from mock)
    # The build_page_html function uses double quotes for id="root"
    assert "<div id=\"root\"><div id='ssr-content'>Hello World</div></div>" in html

    # Check client script injection
    assert '<script type="module">' in html
    assert "console.log('client')" in html

    # Check data injection
    assert 'window.__DATA__ = {"foo": "bar"}' in html

    # Verify mock call
    mock_ssr.render_ssr.assert_called_once_with(
        ANY,  # full_server_js includes polyfills
        hard_timeout=10,
    )
