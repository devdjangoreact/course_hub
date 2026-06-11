from abc import ABC, abstractmethod

from app.domain.entities.order import Order


class OrderRepository(ABC):
    @abstractmethod
    async def add(self, order: Order) -> Order: ...

    @abstractmethod
    async def get(self, order_id: int) -> Order | None: ...

    @abstractmethod
    async def get_by_payment_reference(self, payment_reference: str) -> Order | None: ...

    @abstractmethod
    async def update(self, order: Order) -> Order: ...
