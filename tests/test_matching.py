# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

import pytest

from routedef import CompiledPath, RouteConfigError, compile_path_template, expand_path_template, match_path


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


def test_decoded_params_may_span_segments_even_though_the_pattern_may_not() -> None:
    """The gap this test's neighbour above does not cover.

    That test asserts a LITERAL slash does not match, and its name reads as though
    decoded params cannot cross a segment either. They can: the pattern runs on
    the encoded path, and unquote runs after it, so %2F arrives as a slash the
    route never matched. Pinning it because it is load-bearing, not incidental --
    an id may legitimately contain a slash, so this must keep working.
    """
    compiled = compile_path_template("/v1/files/{name}")
    assert match_path(compiled, "/v1/files/a%2Fb") == {"name": "a/b"}
    assert match_path(compiled, "/v1/files/x%3Fy") == {"name": "x?y"}
    assert match_path(compiled, "/v1/files/x%23z") == {"name": "x#z"}


def test_strict_segments_refuses_a_param_that_decodes_across_segments() -> None:
    """For proxy routes, where a decoded slash walks the upstream path."""
    compiled = compile_path_template("/v1/definitions/{definition_id}")
    traversal = "/v1/definitions/..%2F..%2Fadmin%2Fkeys"

    assert match_path(compiled, traversal) == {"definition_id": "../../admin/keys"}
    assert match_path(compiled, traversal, strict_segments=True) is None

    # Only the segment rule tightens: ordinary decoding is untouched, including
    # reserved characters that stay within one segment.
    assert match_path(compiled, "/v1/definitions/a%20b", strict_segments=True) == {"definition_id": "a b"}
    assert match_path(compiled, "/v1/definitions/x%3Fy", strict_segments=True) == {"definition_id": "x?y"}


def test_strict_segments_checks_every_param_not_only_the_first() -> None:
    compiled = compile_path_template("/v1/{account_id}/items/{item_id}")
    assert match_path(compiled, "/v1/acct/items/a%2Fb", strict_segments=True) is None
    assert match_path(compiled, "/v1/acct/items/ok", strict_segments=True) == {
        "account_id": "acct",
        "item_id": "ok",
    }


def test_path_expansion_can_skip_encoding_without_slash() -> None:
    assert expand_path_template("/v1/files/{name}", {"name": "a b.txt"}, encode=False) == "/v1/files/a b.txt"


def test_path_expansion_encodes_reserved_characters_by_default() -> None:
    assert expand_path_template("/v1/files/{name}", {"name": "a/b?c"}) == "/v1/files/a%2Fb%3Fc"


def test_path_expansion_reports_sorted_missing_and_unknown_params() -> None:
    with pytest.raises(RouteConfigError) as missing:
        expand_path_template("/v1/{account_id}/items/{item_id}", {})
    with pytest.raises(RouteConfigError) as unknown:
        expand_path_template("/v1/{item_id}", {"account_id": "a", "extra": "x", "item_id": "i"})

    assert str(missing.value) == "missing path params: account_id, item_id"
    assert str(unknown.value) == "unknown path params: account_id, extra"


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
