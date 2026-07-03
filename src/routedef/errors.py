# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0


class RouteConfigError(ValueError):
    """Raised when a route definition is invalid."""


class BadRequestBody(ValueError):
    """Raised when a request body cannot be decoded."""
