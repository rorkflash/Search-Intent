"""Base interfaces for project plugins.

Plugins are trusted local code placed in the root-level ``plugins/`` directory.
They subclass these interfaces when JSON config is not expressive enough.
Never load plugin paths from user input.
"""

from ..auth.base import InboundAuthenticator as BaseInboundAuth
from ..cache.base import CacheBackend as BaseCache
from ..extractors.base import Extractor as BaseExtractor
from ..resolvers.base import Resolver as BaseResolver

__all__ = ["BaseInboundAuth", "BaseCache", "BaseExtractor", "BaseResolver"]
