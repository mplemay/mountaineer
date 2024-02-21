from pathlib import Path

from create_filzl_app.generation import ProjectMetadata, format_template


def test_path_url_replacement():
    metadata = ProjectMetadata(
        project_name="TEST_PROJECT_NAME",
        author_name="TEST_AUTHOR",
        author_email="TEST_EMAIL",
        use_tailwind=True,
        use_poetry=True,
        project_path=Path("fake-path"),
        filzl_dev_path=None,
    )
    bundle = format_template("[project_name]/app.py", metadata)
    assert bundle.path == "TEST_PROJECT_NAME/app.py"