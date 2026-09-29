from uuid import UUID
from contextlib import contextmanager
from threading import RLock


class AzureQueue:
    def __init__(
        self,
        connection_string: str | None,
        queue_name: str,
        *,
        namespace: str | None = None,
        socket_timeout: float = 5.0,
        retry_total: int = 5,
    ):
        self.connection_string = connection_string
        self.queue_name = queue_name
        self.namespace = namespace
        if not connection_string and not namespace:
            raise ValueError("Service Bus namespace or connection string required")
        self.socket_timeout = socket_timeout
        self.retry_total = retry_total
        self._lock = RLock()
        self.client = self._new_client()

    def _new_client(self):
        from azure.servicebus import ServiceBusClient

        options = dict(retry_total=self.retry_total, retry_backoff_factor=1, retry_backoff_max=10)
        if self.connection_string:
            return ServiceBusClient.from_connection_string(self.connection_string, **options)
        from azure.identity import DefaultAzureCredential

        return ServiceBusClient(
            fully_qualified_namespace=f"{self.namespace}.servicebus.windows.net",
            credential=DefaultAzureCredential(),
            **options,
        )

    def reconnect(self) -> None:
        with self._lock:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = self._new_client()

    def publish(self, analysis_id: UUID) -> None:
        from azure.servicebus import ServiceBusMessage

        with self._lock:
            try:
                with self.client.get_queue_sender(
                    self.queue_name, socket_timeout=self.socket_timeout
                ) as sender:
                    sender.send_messages(
                        ServiceBusMessage(str(analysis_id), message_id=str(analysis_id))
                    )
            except Exception:
                # A failed AMQP session can remain unusable after DNS or socket recovery.
                # Rebuild it now so the next submission starts with a clean connection.
                self.reconnect()
                raise

    def receive(self):
        # Service Bus receivers use PEEK_LOCK by default; name it explicitly so
        # completion remains tied to successful persistence.
        from azure.servicebus import ServiceBusReceiveMode

        receiver = self.client.get_queue_receiver(
            self.queue_name,
            receive_mode=ServiceBusReceiveMode.PEEK_LOCK,
            max_wait_time=5,
            socket_timeout=self.socket_timeout,
        )
        return receiver

    @contextmanager
    def renew_lock(self, receiver, message, max_seconds: int):
        """Renew one Peek-Lock while application work is in progress."""
        from azure.servicebus import AutoLockRenewer

        with AutoLockRenewer() as renewer:
            renewer.register(
                receiver,
                message,
                max_lock_renewal_duration=max_seconds,
            )
            yield
