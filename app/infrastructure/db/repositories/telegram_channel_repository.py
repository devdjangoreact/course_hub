from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.telegram_channel import TelegramChannel
from app.domain.repositories.telegram_channel_repository import TelegramChannelRepository
from app.infrastructure.db.models.channel_course import ChannelCourseModel
from app.infrastructure.db.models.telegram_channel import TelegramChannelModel


def _to_entity(model: TelegramChannelModel) -> TelegramChannel:
    return TelegramChannel(
        id=model.id,
        bot_id=model.bot_id,
        telegram_chat_id=model.telegram_chat_id,
        discussion_group_id=model.discussion_group_id,
        is_public=model.is_public,
        discussion_is_public=model.discussion_is_public,
        invite_link=model.invite_link,
        discussion_invite_link=model.discussion_invite_link,
        title=model.title,
        slug=model.slug,
        is_active=model.is_active,
        extra=dict(model.extra),
    )


class SqlTelegramChannelRepository(TelegramChannelRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_bot(self, bot_id: int) -> list[TelegramChannel]:
        stmt = select(TelegramChannelModel).where(TelegramChannelModel.bot_id == bot_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entity(row) for row in rows]

    async def get(self, channel_id: int) -> TelegramChannel | None:
        model = await self._session.get(TelegramChannelModel, channel_id)
        return _to_entity(model) if model is not None else None

    async def save(self, channel: TelegramChannel) -> TelegramChannel:
        if channel.id is not None:
            model = await self._session.get(TelegramChannelModel, channel.id)
            if model is None:
                model = TelegramChannelModel(id=channel.id)
                self._session.add(model)
        else:
            model = TelegramChannelModel()
            self._session.add(model)
        model.bot_id = channel.bot_id
        model.telegram_chat_id = channel.telegram_chat_id
        model.discussion_group_id = channel.discussion_group_id
        model.is_public = channel.is_public
        model.discussion_is_public = channel.discussion_is_public
        model.invite_link = channel.invite_link
        model.discussion_invite_link = channel.discussion_invite_link
        model.title = channel.title
        model.slug = channel.slug
        model.is_active = channel.is_active
        model.extra = channel.extra
        await self._session.flush()
        return _to_entity(model)

    async def list_course_ids(self, channel_id: int) -> list[int]:
        stmt = select(ChannelCourseModel.course_id).where(
            ChannelCourseModel.channel_id == channel_id
        )
        return list((await self._session.execute(stmt)).scalars().all())
