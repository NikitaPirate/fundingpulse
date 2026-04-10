from fundingpulse.models.section import Section
from fundingpulse.tracker.db.repositories.base import Repository


class SectionRepository(Repository[Section]):
    """Repository for managing exchange sections."""

    _model = Section
