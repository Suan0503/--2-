# -*- coding: utf-8 -*-
"""
Compatibility shim: expose get_menu_carousel() for legacy imports.
Actual implementation lives in utils/menu_helpers.py
"""
from .menu_helpers import get_menu_carousel

__all__ = ["get_menu_carousel"]
