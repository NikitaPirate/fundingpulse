from fundingpulse.models.quote import Quote
from fundingpulse.tracker.db.repositories.base import Repository


class QuoteRepository(Repository[Quote]):
    """Repository for managing quote currencies."""

    _model = Quote
