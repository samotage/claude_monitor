"""Help documentation routes for Claude Headspace.

Provides REST API endpoints for help documentation:
- Get index of help pages
- Get specific help page
- Search help documentation
"""

import logging

from flask import Blueprint, jsonify, request

from src.services.help_service import (
    get_help_page_content,
    load_help_index,
    load_help_page,
    search_help,
)

logger = logging.getLogger(__name__)

help_bp = Blueprint("help", __name__)


@help_bp.route("/help", methods=["GET"])
def get_help_index():
    """Get index of all help documentation pages.

    Returns:
        JSON object with:
        - success: Boolean status
        - pages: List of page objects with slug, title, order, keywords
    """
    pages = load_help_index()

    return jsonify(
        {
            "success": True,
            "pages": pages,
        }
    )


@help_bp.route("/help/<slug>", methods=["GET"])
def get_help_page(slug: str):
    """Get a specific help page by slug.

    Args:
        slug: The page slug (filename without .md extension)

    Returns:
        JSON object with page data including content,
        or error if not found.
    """
    page = load_help_page(slug)

    if page is None:
        return jsonify(
            {
                "success": False,
                "error": f"Help page '{slug}' not found",
            }
        ), 404

    return jsonify(
        {
            "success": True,
            "page": page,
        }
    )


@help_bp.route("/help/<slug>/content", methods=["GET"])
def get_help_page_raw_content(slug: str):
    """Get raw markdown content for a help page.

    Args:
        slug: The page slug

    Returns:
        JSON object with content string.
    """
    content = get_help_page_content(slug)

    if content is None:
        return jsonify(
            {
                "success": False,
                "error": f"Help page '{slug}' not found",
            }
        ), 404

    return jsonify(
        {
            "success": True,
            "content": content,
        }
    )


@help_bp.route("/help/search", methods=["GET"])
def search_help_pages():
    """Search help documentation.

    Query params:
        q: Search query string

    Returns:
        JSON object with:
        - success: Boolean status
        - query: The search query
        - results: List of matching pages with scores and snippets
    """
    query = request.args.get("q", "")

    if not query.strip():
        return jsonify(
            {
                "success": True,
                "query": "",
                "results": [],
            }
        )

    results = search_help(query)

    return jsonify(
        {
            "success": True,
            "query": query,
            "results": results,
        }
    )
