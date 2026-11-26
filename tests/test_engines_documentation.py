"""The engine page has to keep naming what the code actually looks for.

A documentation page that lists the wrong variable name is worse than no
page: the reader follows it, nothing happens, and the page is what they
trust. These are cheap checks that catch the drift when an engine is added,
renamed, or given a new companion.
"""

from pathlib import Path

import pytest

from modfilegen import engines

PAGE = Path(__file__).parent.parent / "docs" / "source" / "engines.rst"


@pytest.fixture(scope="module")
def page():
    if not PAGE.is_file():
        pytest.skip("the documentation sources are not part of this checkout")
    return PAGE.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", sorted(engines.ENGINES))
def test_the_page_names_every_engine_and_how_to_point_at_it(name, page):
    engine = engines.ENGINES[name]

    assert engine.config_key in page
    assert engine.env_var in page


@pytest.mark.parametrize("name", sorted(engines.ENGINES))
def test_the_page_gives_the_portable_path(name, page):
    """The no-admin route is the reason the page exists."""
    portable = next(
        location
        for location in engines.ENGINES[name].locations
        if not Path(location).is_absolute()
    )

    assert portable in page


@pytest.mark.parametrize("name", sorted(engines.ENGINES))
def test_the_page_says_what_must_sit_beside_the_executable(name, page):
    """An engine with companions must have them documented, or the reader
    meets `incomplete` with nothing to act on."""
    for pattern in engines.ENGINES[name].companions:
        assert pattern in page


def test_the_page_warns_that_stics_is_not_on_the_path(page):
    """Silently running v9 as v11 is the worst failure in the whole cascade."""
    assert not engines.ENGINES["stics_v11"].commands
    assert "never taken from ``PATH``" in page


def test_the_page_is_in_the_table_of_contents():
    index = PAGE.parent / "index.rst"
    if not index.is_file():
        pytest.skip("the documentation sources are not part of this checkout")

    assert "\n   engines\n" in index.read_text(encoding="utf-8")


COMMAND_PAGE = PAGE.parent / "command_line.rst"


@pytest.fixture(scope="module")
def command_page():
    if not COMMAND_PAGE.is_file():
        pytest.skip("the documentation sources are not part of this checkout")
    return COMMAND_PAGE.read_text(encoding="utf-8")


def test_the_command_page_names_every_option(command_page):
    """An option renamed in the parser and not on the page sends the reader
    to a command that argparse rejects."""
    from modfilegen import cli

    run = cli.build_parser()._subparsers._group_actions[0].choices["run"]
    documented = [
        option
        for action in run._actions
        for option in action.option_strings
        if option.startswith("--") and option != "--help"
    ]

    missing = [option for option in documented if option not in command_page]

    assert not missing, f"undocumented options: {missing}"


def test_the_command_page_covers_every_model(command_page):
    from modfilegen import run_command

    for name, model in run_command.MODELS.items():
        assert f"``{name}``" in command_page
        for version in model.versions:
            if version != "ng":  # APSIM NG has a single, unnamed version
                assert f"``{version}``" in command_page


def test_the_command_page_is_in_the_table_of_contents():
    index = PAGE.parent / "index.rst"
    if not index.is_file():
        pytest.skip("the documentation sources are not part of this checkout")

    assert "\n   command_line\n" in index.read_text(encoding="utf-8")
