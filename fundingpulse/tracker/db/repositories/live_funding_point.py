from fundingpulse.models.live_funding_point import LiveFundingPoint
from fundingpulse.tracker.db.repositories.base import Repository


class LiveFundingPointRepository(Repository[LiveFundingPoint]):
    _model = LiveFundingPoint
