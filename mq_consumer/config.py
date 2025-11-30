import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class MQConfig:
    host: str = os.getenv("RABBITMQ_HOST", "localhost")
    port: int = int(os.getenv("RABBITMQ_PORT", "5672"))
    user: str = os.getenv("RABBITMQ_USER", "guest")
    password: str = os.getenv("RABBITMQ_PASSWORD", "guest")
    vhost: str = os.getenv("RABBITMQ_VHOST", "/")
    
    queue_name: str = os.getenv("MQ_QUEUE_NAME", "openstack_events")
    exchange_name: str = os.getenv("MQ_EXCHANGE_NAME", "openstack")
    routing_key: str = os.getenv("MQ_ROUTING_KEY", "resource.#")
    
    prefetch_count: int = int(os.getenv("MQ_PREFETCH_COUNT", "100"))
    batch_size: int = int(os.getenv("MQ_BATCH_SIZE", "50"))
    batch_timeout: float = float(os.getenv("MQ_BATCH_TIMEOUT", "1.0"))
    
    reconnect_delay: float = float(os.getenv("MQ_RECONNECT_DELAY", "5.0"))
    max_retries: int = int(os.getenv("MQ_MAX_RETRIES", "3"))
    
    @property
    def url(self) -> str:
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/{self.vhost}"


@dataclass
class APIConfig:
    base_url: str = os.getenv("BILLING_API_URL", "http://localhost:8000")
    api_prefix: str = "/api/v1"
    
    timeout: float = float(os.getenv("API_TIMEOUT", "30.0"))
    max_connections: int = int(os.getenv("API_MAX_CONNECTIONS", "100"))
    max_keepalive: int = int(os.getenv("API_MAX_KEEPALIVE", "20"))
    
    retry_count: int = int(os.getenv("API_RETRY_COUNT", "3"))
    retry_delay: float = float(os.getenv("API_RETRY_DELAY", "1.0"))
    
    @property
    def resources_url(self) -> str:
        return f"{self.base_url}{self.api_prefix}/resources"
    
    @property
    def wallets_url(self) -> str:
        return f"{self.base_url}{self.api_prefix}/wallets"
    
    @property
    def billing_url(self) -> str:
        return f"{self.base_url}{self.api_prefix}/billing"


@dataclass
class ConsumerConfig:
    worker_count: int = int(os.getenv("WORKER_COUNT", "4"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    metrics_port: int = int(os.getenv("METRICS_PORT", "9090"))
    dead_letter_queue: str = os.getenv("DLQ_NAME", "openstack_events_dlq")
    skip_wallet: bool = os.getenv("SKIP_WALLET", "true").lower() == "true"


mq_config = MQConfig()
api_config = APIConfig()
consumer_config = ConsumerConfig()
