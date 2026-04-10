from fundingpulse.models.asset import Asset
from fundingpulse.tracker.db.repositories.base import Repository


class AssetRepository(Repository[Asset]):
    _model = Asset
