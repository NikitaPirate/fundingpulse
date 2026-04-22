from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from fundingpulse.models.asset import Asset
from fundingpulse.models.contract import Contract
from fundingpulse.models.contract_history_state import ContractHistoryState
from fundingpulse.models.section import Section


async def get_or_create_asset(session: AsyncSession, name: str) -> Asset:
    result = await session.execute(select(Asset).where(col(Asset.name) == name))
    asset = result.scalar_one_or_none()
    if asset:
        return asset

    asset = Asset(name=name)
    session.add(asset)
    await session.commit()
    await session.refresh(asset)
    return asset


async def get_or_create_section(session: AsyncSession, name: str) -> Section:
    result = await session.execute(select(Section).where(col(Section.name) == name))
    section = result.scalar_one_or_none()
    if section:
        return section

    section = Section(name=name)
    session.add(section)
    await session.commit()
    await session.refresh(section)
    return section


async def create_contract(
    session: AsyncSession,
    asset_name: str = "BTC",
    section_name: str = "CEX",
    quote_name: str = "USDT",
    funding_interval: int = 8,
) -> Contract:
    asset = await get_or_create_asset(session, asset_name)
    section = await get_or_create_section(session, section_name)

    contract = Contract(
        asset_name=asset.name,
        section_name=section.name,
        funding_interval=funding_interval,
        quote_name=quote_name,
    )
    contract.history_state = ContractHistoryState(contract_id=contract.id)
    session.add(contract)
    await session.commit()
    await session.refresh(contract)
    return contract
