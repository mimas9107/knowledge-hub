"""
Knowledge Hub API 模組
"""
from . import documents
from . import index
from . import search
from . import settings

blueprints = [
    documents.bp,
    index.bp,
    search.bp,
    settings.bp,
]
