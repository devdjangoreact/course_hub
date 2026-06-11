from sqladmin import ModelView

from app.infrastructure.db.models.admin_user import AdminUserModel
from app.infrastructure.db.models.bot_settings import BotSettingsModel
from app.infrastructure.db.models.bot_user import BotUserModel
from app.infrastructure.db.models.category import CategoryModel
from app.infrastructure.db.models.course import CourseModel
from app.infrastructure.db.models.order import OrderModel
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


ALL_VIEWS = [
    CategoryAdmin,
    CourseAdmin,
    OrderAdmin,
    BotUserAdmin,
    AdminUserAdmin,
    BotSettingsAdmin,
    PaymentSettingsAdmin,
]
