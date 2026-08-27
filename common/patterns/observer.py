from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class DomainEvent:
    name: str
    payload: dict


class Observer(ABC):
    @abstractmethod
    def update(self, event: DomainEvent) -> None:
        ...


class EventPublisher:
    """Publishes domain events to subscribed observers."""

    def __init__(self):
        self._observers = []

    def subscribe(self, observer):
        if observer not in self._observers:
            self._observers.append(observer)

    def publish(self, event):
        for observer in tuple(self._observers):
            try:
                observer.update(event)
            except Exception:
                # Notification failure must not roll back the business transaction.
                pass


class HttpNotificationObserver(Observer):
    def __init__(self, http_client, notification_service_url: str):
        self.http_client = http_client
        self.notification_service_url = notification_service_url

    def update(self, event: DomainEvent) -> None:
        self.http_client.post(
            f"{self.notification_service_url}/events",
            json={"name": event.name, "payload": event.payload},
            timeout=2,
        )
