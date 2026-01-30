import pytest
from fastapi.testclient import TestClient


# Use the example_path fixture to ensure sys.path is set up
@pytest.mark.usefixtures("example_path", "mock_bundler", "mock_ssr")
def test_example_app_home():
    """
    Integration test using the actual example project.
    We import the app from the example source and test it against a client.
    """
    # Import inside the test function to ensure sys.path is ready and mocks are active
    try:
        # We need to reload example.main if it was already imported,
        # but since pytest runs in a process, it likely wasn't.
        # However, to be safe against side effects if other tests imported it (unlikely here),
        # we just import.
        from importlib import reload  # noqa: PLC0415

        import example.main  # noqa: PLC0415

        reload(example.main)
        from example.main import app  # noqa: PLC0415
    except ImportError as e:
        pytest.fail(f"Could not import example.main: {e}")

    client = TestClient(app)

    # The example app mounts Mountaineer at root
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    # Verify basic SSR structure is present
    # Note: Since we are running in an environment where we might not have
    # the actual compiled JS bundles for the example (unless we ran a build step),
    # the Rust core might fail or return empty strings if not handled.
    # HOWEVER, Mountaineer V2 'compile' step happens at startup (include_page).
    # If the Rust extension is present, it will try to compile 'home/page.tsx'.
    # If the file exists in example/src/example/views/home/page.tsx, it should work.

    assert '<div id="root">' in response.text

    # Check for the detail page as well
    response_detail = client.get("/detail/123")
    assert response_detail.status_code == 200
    assert '<div id="root">' in response_detail.text
