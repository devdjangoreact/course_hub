from sqladmin import ModelView
from wtforms import PasswordField, SelectField

from app.infrastructure.db.models.admin_user import AdminUserModel
from app.infrastructure.db.models.bot_settings import BotSettingsModel
from app.infrastructure.db.models.bot_user import BotUserModel
from app.infrastructure.db.models.category import CategoryModel
from app.infrastructure.db.models.category_translation import CategoryTranslationModel
from app.infrastructure.db.models.course import CourseModel
from app.infrastructure.db.models.course_translation import CourseTranslationModel
from app.infrastructure.db.models.imported_catalog_item import ImportedCatalogItemModel
from app.infrastructure.db.models.order import OrderModel
from app.infrastructure.db.models.parser_job import ParserJobModel
from app.infrastructure.db.models.parser_source import ParserSourceModel
from app.infrastructure.db.models.payment_settings import PaymentSettingsModel
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
    form_columns = [AdminUserModel.username, AdminUserModel.is_active]
    form_extra_fields = {"password": PasswordField("Password")}
    form_create_rules = ("username", "password", "is_active")
    form_edit_rules = ("username", "password", "is_active")
    name = "Admin User"
    name_plural = "Admin Users"
    icon = "fa-solid fa-user-shield"

    async def on_model_change(self, data: dict, model: AdminUserModel, is_created: bool, request) -> None:  # noqa: ANN001
        password = data.pop("password", None)
        if password:
            model.password_hash = hash_password(str(password))
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
        BotSettingsModel.extra: "Extra (languages, search, parser)",
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
            "description": "Telegram bot token. Restart the app after changing.",
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
                'JSON options, e.g. {"supported_languages": "uk,en", "default_language": "uk", '
                '"search_rate_limit": 5, "search_suggestion_limit": 5}.'
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
        PaymentSettingsModel.api_key: lambda model, _: _mask_secret(model, "api_key", model.api_key),
        PaymentSettingsModel.secret_key: lambda model, _: _mask_secret(
            model, "secret_key", model.secret_key
        ),
    }
    column_labels = {
        PaymentSettingsModel.api_key: "API key (lava Public API)",
        PaymentSettingsModel.secret_key: "Webhook secret (X-Api-Key)",
        PaymentSettingsModel.extra: "Extra (lava_env, checkout_mode)",
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
                ("lava", "lava.top"),
            ],
            "description": "Active payment provider for new orders.",
        },
        "api_key": {
            "description": "lava.top Public API key. Leave empty for simulated provider.",
        },
        "secret_key": {
            "description": "lava.top Webhook API key sent as X-Api-Key. Also used for simulated HMAC.",
        },
        "currency": {
            "choices": [("USD", "USD"), ("EUR", "EUR"), ("RUB", "RUB")],
            "description": "Checkout currency (lava.top rules apply per method).",
        },
        "extra": {
            "description": (
                'JSON options, e.g. {"lava_env": "production", "checkout_mode": "direct"} '
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


class ParserSourceAdmin(ModelView, model=ParserSourceModel):
    column_list = [
        ParserSourceModel.id,
        ParserSourceModel.name,
        ParserSourceModel.source_type,
        ParserSourceModel.is_active,
        ParserSourceModel.last_status,
    ]
    column_searchable_list = [ParserSourceModel.name, ParserSourceModel.url]
    name = "Parser Source"
    icon = "fa-solid fa-download"


class ParserJobAdmin(ModelView, model=ParserJobModel):
    column_list = [
        ParserJobModel.id,
        ParserJobModel.source_id,
        ParserJobModel.status,
        ParserJobModel.imported_count,
        ParserJobModel.skipped_count,
    ]
    can_create = False
    name = "Parser Job"
    icon = "fa-solid fa-list-check"


class ImportedCatalogItemAdmin(ModelView, model=ImportedCatalogItemModel):
    column_list = [
        ImportedCatalogItemModel.id,
        ImportedCatalogItemModel.parser_job_id,
        ImportedCatalogItemModel.item_type,
        ImportedCatalogItemModel.language_code,
        ImportedCatalogItemModel.status,
    ]
    can_create = False
    name = "Imported Catalog Item"
    icon = "fa-solid fa-inbox"


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
    ParserSourceAdmin,
    ParserJobAdmin,
    ImportedCatalogItemAdmin,
]
