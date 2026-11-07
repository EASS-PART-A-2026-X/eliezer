"""The UI may import Streamlit, api.py, i18n.py, style.py and string: nothing
that does I/O."""

import ast
from pathlib import Path

UI = Path(__file__).parent.parent / "streamlit_app.py"
I18N = Path(__file__).parent.parent / "i18n.py"
STYLE = Path(__file__).parent.parent / "style.py"


def imported_modules(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_ui_reaches_the_backend_only_through_api_py():
    assert imported_modules(UI) <= {"api", "i18n", "streamlit", "string", "style"}


def test_i18n_does_no_io():
    assert imported_modules(I18N) <= {"datetime"}


def test_style_is_only_strings():
    assert imported_modules(STYLE) == set()
