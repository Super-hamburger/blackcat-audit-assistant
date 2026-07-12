"""Compatibility wrapper for the label_compress module."""

from modules.label_compress.processor import DuplicateLabelError, LabelProcessor

__all__ = ["DuplicateLabelError", "LabelProcessor"]
