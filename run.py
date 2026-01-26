#!/usr/bin/env python3
"""Claude Headspace - Run the application.

This is the recommended entry point for running Claude Headspace.
It uses the new src/ architecture with Pydantic models, proper
service injection, and the 5-state task model.

Usage:
    python run.py
    # Or: python -m src.app

The dashboard will be available at http://localhost:5050

For legacy mode (deprecated), use:
    python monitor.py
"""

from src.app import main

if __name__ == "__main__":
    main()
