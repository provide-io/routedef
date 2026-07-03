# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

import pytest

from routedef import CompiledPath, RouteConfigError, compile_path_template, match_path


def test_static_path_matches_exactly() -> None:
    compiled = compile_path_template("/v1/status")

    assert isinstance(compiled, CompiledPath)
    assert compiled.path_template == "/v1/status"
    assert compiled.param_names == ()
    assert match_path(compiled, "/v1/status") == {}
    assert match_path(compiled, "/v1/status/") is None
    assert match_path(compiled, "/v1/other") is None


def test_static_path_treats_regex_characters_literally() -> None:
    compiled = compile_path_template("/v1/files/archive.tar.gz")

    assert match_path(compiled, "/v1/files/archive.tar.gz") == {}
    assert match_path(compiled, "/v1/files/archiveXtarXgz") is None


def test_placeholder_path_returns_params() -> None:
    compiled = compile_path_template("/v1/items/{item_id}")

    assert compiled.path_template == "/v1/items/{item_id}"
    assert compiled.param_names == ("item_id",)
    assert match_path(compiled, "/v1/items/abc123") == {"item_id": "abc123"}
    assert match_path(compiled, "/v1/items") is None


def test_multiple_placeholders_match_in_order() -> None:
    compiled = compile_path_template("/v1/{org}/items/{id}/details")

    assert compiled.param_names == ("org", "id")
    assert match_path(compiled, "/v1/acme/items/123/details") == {"org": "acme", "id": "123"}
    assert match_path(compiled, "/v1/acme/items/123") is None


def test_adjacent_placeholders_are_preserved() -> None:
    compiled = compile_path_template("/{first}{second}")

    assert compiled.param_names == ("first", "second")
    assert match_path(compiled, "/ab") == {"first": "a", "second": "b"}


def test_single_character_placeholder_name_is_valid() -> None:
    compiled = compile_path_template("/v1/{x}/details")

    assert match_path(compiled, "/v1/a/details") == {"x": "a"}


def test_path_params_are_url_decoded_without_crossing_slashes() -> None:
    compiled = compile_path_template("/v1/files/{name}")
    assert match_path(compiled, "/v1/files/a%20b.txt") == {"name": "a b.txt"}
    assert match_path(compiled, "/v1/files/a/b") is None


def test_matching_is_method_independent() -> None:
    compiled = compile_path_template("/v1/users/{user_id}")

    assert match_path(compiled, "/v1/users/42") == {"user_id": "42"}
    assert match_path(compiled, "/v1/users/42/settings") is None


@pytest.mark.parametrize(
    "path_template",
    [
        "/v1/items/{1id}",
        "/v1/items/{item-id}",
        "/v1/items/{}",
        "/v1/items/{name",
        "/v1/items/name}",
        "/v1/items/{name{id}}",
    ],
)
def test_invalid_placeholder_names_are_rejected(path_template: str) -> None:
    with pytest.raises(RouteConfigError) as exc_info:
        compile_path_template(path_template)

    assert str(exc_info.value) == "route path placeholder name is invalid"


def test_duplicate_placeholder_names_are_rejected() -> None:
    with pytest.raises(RouteConfigError) as exc_info:
        compile_path_template("/v1/{id}/items/{id}")

    assert str(exc_info.value) == "route path placeholder 'id' is duplicated"


@pytest.mark.parametrize("path_template", ["", "   "])
def test_path_template_rejects_empty_paths(path_template: str) -> None:
    with pytest.raises(RouteConfigError) as exc_info:
        compile_path_template(path_template)

    assert str(exc_info.value) == "route path must not be empty"


def test_path_template_rejects_paths_without_leading_slash() -> None:
    with pytest.raises(RouteConfigError) as exc_info:
        compile_path_template("v1/items/{id}")

    assert str(exc_info.value) == "route path must start with '/'"
