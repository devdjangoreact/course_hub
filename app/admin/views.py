from sqladmin import ModelView

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
    column_list = [AdminUserModel.id, AdminUserModel.username, AdminUserModel.is_active]
    can_create = False
    can_edit = False
    can_delete = False
    name = "Admin User"
    icon = "fa-solid fa-user-shield"


class BotSettingsAdmin(ModelView, model=BotSettingsModel):
    column_list = [BotSettingsModel.id, BotSettingsModel.backend_url, BotSettingsModel.is_active]
    can_delete = False
    name = "Bot Settings"
    name_plural = "Bot Settings"
    icon = "fa-solid fa-gear"


class PaymentSettingsAdmin(ModelView, model=PaymentSettingsModel):
    column_list = [
        PaymentSettingsModel.id,
        PaymentSettingsModel.provider,
        PaymentSettingsModel.currency,
        PaymentSettingsModel.is_active,
    ]
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
    BotSettingsAdmin,
    PaymentSettingsAdmin,
    ParserSourceAdmin,
    ParserJobAdmin,
    ImportedCatalogItemAdmin,
]
