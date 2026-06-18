from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    awaiting_payment_email = State()


class SearchStates(StatesGroup):
    awaiting_query = State()
    viewing_suggestions = State()
