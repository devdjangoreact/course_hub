import asyncio

from loguru import logger
from sqladmin import ModelView
from wtforms import PasswordField, SelectField

from app.infrastructure.db.models.admin_user import AdminUserModel
from app.infrastructure.db.models.bot_settings import BotSettingsModel
from app.infrastructure.db.models.bot_user import BotUserModel
from app.infrastructure.db.models.category import CategoryModel
from app.infrastructure.db.models.category_translation import CategoryTranslationModel
from app.infrastructure.db.models.channel_course import ChannelCourseModel
from app.infrastructure.db.models.course import CourseModel
from app.infrastructure.db.models.course_translation import CourseTranslationModel
from app.infrastructure.db.models.order import OrderModel
from app.infrastructure.db.models.payment_settings import PaymentSettingsModel
from app.infrastructure.db.models.telegram_bot import TelegramBotModel
from app.infrastructure.db.models.telegram_channel import TelegramChannelModel
from app.infrastructure.security.password import hash_password


class CategoryAdmin(ModelView, model=CategoryModel):
    column_list = [CategoryModel.id, CategoryModel.name]
    column_searchable_list = [CategoryModel.name]
    name = "Category"
    name_plural = "Categories"
    icon = "fa-solid fa-layer-group"


class CourseAdmin(ModelView, model=CourseModel):
    column_list = [
        CourseModel.id,
        CourseModel.name,
        CourseModel.category_id,
        CourseModel.price,
        CourseModel.is_active,
    ]
    column_searchable_list = [CourseModel.name, CourseModel.description]
    name = "Course"
    icon = "fa-solid fa-book"


class CategoryTranslationAdmin(ModelView, model=CategoryTranslationModel):
    column_list = [
        CategoryTranslationModel.id,
        CategoryTranslationModel.category_id,
        CategoryTranslationModel.language_code,
        CategoryTranslationModel.name,
    ]
    column_searchable_list = [CategoryTranslationModel.name]
    name = "Category Translation"
    icon = "fa-solid fa-language"


class CourseTranslationAdmin(ModelView, model=CourseTranslationModel):
    column_list = [
        CourseTranslationModel.id,
        CourseTranslationModel.course_id,
        CourseTranslationModel.language_code,
        CourseTranslationModel.name,
    ]
    column_searchable_list = [
        CourseTranslationModel.name,
        CourseTranslationModel.description,
    ]
    name = "Course Translation"
    icon = "fa-solid fa-language"


class OrderAdmin(ModelView, model=OrderModel):
    column_list = [
        OrderModel.id,
        OrderModel.bot_user_id,
        OrderModel.course_id,
        OrderModel.bot_id,
        OrderModel.channel_id,
        OrderModel.amount,
        OrderModel.status,
    ]
    can_create = False
    name = "Order"
    icon = "fa-solid fa-cart-shopping"


class BotUserAdmin(ModelView, model=BotUserModel):
    column_list = [BotUserModel.id, BotUserModel.telegram_id, BotUserModel.username]
    can_create = False
    name = "Bot User"
    icon = "fa-solid fa-user"


class AdminUserAdmin(ModelView, model=AdminUserModel):
    category = "Settings"
    column_list = [AdminUserModel.id, AdminUserModel.username, AdminUserModel.is_active]
    form_columns = [AdminUserModel.username, AdminUserModel.password_hash, AdminUserModel.is_active]
    form_overrides = {"password_hash": PasswordField}
    column_labels = {
        AdminUserModel.password_hash: "Password",
    }
    form_args = {
        "password_hash": {
            "description": "Required for new users. Leave empty when editing to keep the current password.",
        },
    }
    name = "Admin User"
    name_plural = "Admin Users"
    icon = "fa-solid fa-user-shield"

    async def on_model_change(self, data: dict, model: AdminUserModel, is_created: bool, request) -> None:  # noqa: ANN001
        raw_password = data.pop("password_hash", None)
        if raw_password:
            model.password_hash = hash_password(str(raw_password))
        elif is_created:
            model.password_hash = hash_password("admin")


class AppSettingsAdmin(ModelView, model=BotSettingsModel):
    category = "Settings"
    column_list = [
        BotSettingsModel.app_env,
        BotSettingsModel.backend_url,
        BotSettingsModel.log_level,
        BotSettingsModel.is_active,
        BotSettingsModel.updated_at,
    ]
    column_details_list = [
        BotSettingsModel.id,
        BotSettingsModel.app_env,
        BotSettingsModel.backend_url,
        BotSettingsModel.bot_token,
        BotSettingsModel.admin_session_secret,
        BotSettingsModel.log_level,
        BotSettingsModel.extra,
        BotSettingsModel.is_active,
        BotSettingsModel.updated_at,
    ]
    column_formatters = {
        BotSettingsModel.bot_token: lambda model, _: _mask_secret(model, "bot_token", model.bot_token),
        BotSettingsModel.admin_session_secret: lambda model, _: _mask_secret(
            model, "admin_session_secret", model.admin_session_secret
        ),
    }
    column_labels = {
        BotSettingsModel.app_env: "Environment",
        BotSettingsModel.backend_url: "Backend URL",
        BotSettingsModel.bot_token: "Telegram bot token",
        BotSettingsModel.admin_session_secret: "Admin session secret",
        BotSettingsModel.log_level: "Log level",
        BotSettingsModel.extra: "Extra (languages, search)",
    }
    form_columns = [
        BotSettingsModel.app_env,
        BotSettingsModel.backend_url,
        BotSettingsModel.bot_token,
        BotSettingsModel.admin_session_secret,
        BotSettingsModel.log_level,
        BotSettingsModel.extra,
        BotSettingsModel.is_active,
    ]
    form_overrides = {
        "app_env": SelectField,
        "log_level": SelectField,
    }
    form_args = {
        "app_env": {
            "choices": [("development", "Development"), ("production", "Production")],
            "description": "Runtime environment label (shown on /health).",
        },
        "backend_url": {
            "description": "Public base URL for checkout pages and payment webhooks.",
        },
        "bot_token": {
            "description": (
                "Deprecated for multi-bot runtime — manage tokens under Telegram → Bots. "
                "Still used only to seed the first bot when the bots table is empty."
            ),
        },
        "admin_session_secret": {
            "description": "Signs admin login cookies. Restart required after change.",
        },
        "log_level": {
            "choices": [
                ("DEBUG", "DEBUG"),
                ("INFO", "INFO"),
                ("WARNING", "WARNING"),
                ("ERROR", "ERROR"),
            ],
        },
        "extra": {
            "description": (
                'JSON options, e.g. {"base_domain": "example.com", "supported_languages": "ru,uk,en", '
                '"default_language": "ru", "search_rate_limit": 5, "search_suggestion_limit": 5}. '
                "extra.base_domain overrides BASE_DOMAIN / backend_url host for bot subdomains."
            ),
        },
    }
    can_create = False
    can_delete = False
    name = "App Settings"
    name_plural = "App Settings"
    icon = "fa-solid fa-gear"


def _mask_secret(_model: object, _name: str, value: str | None) -> str:
    return "••••••••" if value else ""


class PaymentSettingsAdmin(ModelView, model=PaymentSettingsModel):
    category = "Settings"
    column_list = [
        PaymentSettingsModel.provider,
        PaymentSettingsModel.currency,
        PaymentSettingsModel.is_active,
        PaymentSettingsModel.updated_at,
    ]
    column_details_list = [
        PaymentSettingsModel.id,
        PaymentSettingsModel.provider,
        PaymentSettingsModel.api_key,
        PaymentSettingsModel.secret_key,
        PaymentSettingsModel.currency,
        PaymentSettingsModel.extra,
        PaymentSettingsModel.is_active,
        PaymentSettingsModel.updated_at,
    ]
    column_formatters = {
        PaymentSettingsModel.api_key: lambda model, _: _mask_secret(
            model, "api_key", model.api_key
        ),
        PaymentSettingsModel.secret_key: lambda model, _: _mask_secret(
            model, "secret_key", model.secret_key
        ),
    }
    column_labels = {
        PaymentSettingsModel.api_key: "API key / Merchant ID",
        PaymentSettingsModel.secret_key: "Webhook secret / API secret",
        PaymentSettingsModel.extra: "Extra (checkout_mode)",
    }
    form_columns = [
        PaymentSettingsModel.provider,
        PaymentSettingsModel.api_key,
        PaymentSettingsModel.secret_key,
        PaymentSettingsModel.currency,
        PaymentSettingsModel.extra,
        PaymentSettingsModel.is_active,
    ]
    form_overrides = {
        "provider": SelectField,
        "currency": SelectField,
    }
    form_args = {
        "provider": {
            "choices": [
                ("simulated", "Simulated (local dev)"),
                ("atlos", "ATLOS"),
            ],
            "description": "Active payment provider for new orders.",
        },
        "api_key": {
            "description": "ATLOS Merchant ID.",
        },
        "secret_key": {
            "description": "ATLOS API secret, or simulated HMAC secret.",
        },
        "currency": {
            "choices": [("USD", "USD"), ("EUR", "EUR"), ("RUB", "RUB")],
            "description": "Checkout currency.",
        },
        "extra": {
            "description": (
                'JSON options, e.g. {"checkout_mode": "direct"} '
                'or {"checkout_mode": "checkout"}. '
                "direct = payment URL in bot; checkout = short link to order summary page."
            ),
        },
    }
    can_create = False
    can_delete = False
    name = "Payment Settings"
    name_plural = "Payment Settings"
    icon = "fa-solid fa-credit-card"


class TelegramBotAdmin(ModelView, model=TelegramBotModel):
    category = "Telegram"
    column_list = [
        TelegramBotModel.id,
        TelegramBotModel.username,
        TelegramBotModel.is_active,
        TelegramBotModel.updated_at,
    ]
    column_details_list = [
        TelegramBotModel.id,
        TelegramBotModel.username,
        TelegramBotModel.token,
        TelegramBotModel.webhook_secret,
        TelegramBotModel.title,
        TelegramBotModel.notes,
        TelegramBotModel.extra,
        TelegramBotModel.is_active,
        TelegramBotModel.updated_at,
    ]
    column_formatters = {
        TelegramBotModel.token: lambda model, _: _mask_secret(model, "token", model.token),
        TelegramBotModel.webhook_secret: lambda model, _: _mask_secret(
            model, "webhook_secret", model.webhook_secret
        ),
    }
    form_columns = [
        TelegramBotModel.token,
        TelegramBotModel.webhook_secret,
        TelegramBotModel.title,
        TelegramBotModel.notes,
        TelegramBotModel.extra,
        TelegramBotModel.is_active,
    ]
    form_args = {
        "token": {
            "description": (
                "Bot API token. Username/subdomain is filled from Telegram getMe on save. "
                "Restart the app after create/update."
            ),
        },
        "webhook_secret": {
            "description": "Optional per-bot webhook secret. Restart after change.",
        },
    }
    name = "Bot"
    name_plural = "Bots"
    icon = "fa-solid fa-robot"

    async def on_model_change(
        self, data: dict, model: TelegramBotModel, is_created: bool, request  # noqa: ANN001
    ) -> None:
        from app.bot.telegram_identity import fetch_bot_username

        token = str(data.get("token") or model.token or "").strip()
        if not token:
            raise ValueError("Bot token is required")
        model.username = await fetch_bot_username(token)
        if not model.title:
            model.title = model.username

    async def after_model_change(
        self, data: dict, model: TelegramBotModel, is_created: bool, request  # noqa: ANN001
    ) -> None:
        """Configure the webhook here too, so a bot added by hand needs no deploy to work."""
        if not model.is_active:
            return
        from app.bot.webhook_setup import ensure_webhook

        settings = request.app.state.settings
        runtime = getattr(request.app.state, "runtime_settings", None)
        failure = await asyncio.to_thread(
            ensure_webhook,
            username=model.username,
            token=model.token,
            base_domain=runtime.base_domain if runtime is not None else settings.base_domain,
            secret=model.webhook_secret or "",
            webhook_path=settings.telegram_webhook_path,
        )
        if failure:
            logger.error("Telegram webhook not live after admin save: {}", failure)
            raise ValueError(f"Bot saved, but its webhook is not live: {failure}")
        logger.info("Telegram webhook verified for @{} after admin save", model.username)


class TelegramChannelAdmin(ModelView, model=TelegramChannelModel):
    category = "Telegram"
    column_list = [
        TelegramChannelModel.id,
        TelegramChannelModel.bot_id,
        TelegramChannelModel.telegram_chat_id,
        TelegramChannelModel.is_public,
        TelegramChannelModel.is_active,
        TelegramChannelModel.title,
    ]
    form_columns = [
        TelegramChannelModel.bot_id,
        TelegramChannelModel.telegram_chat_id,
        TelegramChannelModel.discussion_group_id,
        TelegramChannelModel.is_public,
        TelegramChannelModel.discussion_is_public,
        TelegramChannelModel.invite_link,
        TelegramChannelModel.discussion_invite_link,
        TelegramChannelModel.title,
        TelegramChannelModel.slug,
        TelegramChannelModel.extra,
        TelegramChannelModel.is_active,
    ]
    name = "Channel"
    name_plural = "Channels"
    icon = "fa-solid fa-bullhorn"


class ChannelCourseAdmin(ModelView, model=ChannelCourseModel):
    category = "Telegram"
    column_list = [
        ChannelCourseModel.id,
        ChannelCourseModel.channel_id,
        ChannelCourseModel.course_id,
    ]
    form_columns = [
        ChannelCourseModel.channel_id,
        ChannelCourseModel.course_id,
        ChannelCourseModel.extra,
    ]
    name = "Channel Course"
    name_plural = "Channel Courses"
    icon = "fa-solid fa-link"


ALL_VIEWS = [
    CategoryAdmin,
    CourseAdmin,
    CategoryTranslationAdmin,
    CourseTranslationAdmin,
    OrderAdmin,
    BotUserAdmin,
    AdminUserAdmin,
    AppSettingsAdmin,
    PaymentSettingsAdmin,
    TelegramBotAdmin,
    TelegramChannelAdmin,
    ChannelCourseAdmin,
]
