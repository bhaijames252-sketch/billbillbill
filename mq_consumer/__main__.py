import argparse
import asyncio
import logging
import signal
import sys
from typing import Optional

from .config import mq_config, api_config, consumer_config
from .consumer import MQConsumer
from .handlers import EventHandler
from .api_client import get_api_client, close_api_client


logging.basicConfig(
    level=getattr(logging, consumer_config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class GracefulShutdown:
    def __init__(self):
        self.shutdown_event = asyncio.Event()
        self._consumer: Optional[MQConsumer] = None
    
    def set_consumer(self, consumer: MQConsumer):
        self._consumer = consumer
    
    async def shutdown(self, sig=None):
        if sig:
            logger.info(f"Received signal {sig.name}")
        
        logger.info("Initiating graceful shutdown...")
        
        if self._consumer:
            await self._consumer.stop()
            await self._consumer.disconnect()
        
        await close_api_client()
        self.shutdown_event.set()


async def run_consumer():
    shutdown_handler = GracefulShutdown()
    
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown_handler.shutdown(s))
        )
    
    api_client = get_api_client()
    
    logger.info("Checking API health...")
    if not await api_client.health_check():
        logger.error(f"API not reachable at {api_config.base_url}")
        logger.info("Starting anyway, will retry connections...")
    else:
        logger.info("API is healthy")
    
    handler = EventHandler(api_client)
    consumer = MQConsumer(
        config=mq_config,
        handler=handler,
        use_batching=True
    )
    shutdown_handler.set_consumer(consumer)
    
    try:
        await consumer.connect()
        metrics_task = asyncio.create_task(log_metrics_periodically(consumer))
        await consumer.start()
    except Exception as e:
        logger.error(f"Consumer error: {e}")
        raise
    finally:
        await shutdown_handler.shutdown()


async def log_metrics_periodically(consumer: MQConsumer, interval: int = 60):
    while True:
        await asyncio.sleep(interval)
        metrics = consumer.get_metrics()
        logger.info(
            f"Metrics - Processed: {metrics['messages_processed']}, "
            f"Failed: {metrics['messages_failed']}, "
            f"Rate: {metrics['messages_per_second']}/s, "
            f"Avg Time: {metrics['handler_stats']['avg_processing_time_ms']}ms"
        )


async def check_health():
    client = get_api_client()
    healthy = await client.health_check()
    await close_api_client()
    return healthy


def main():
    parser = argparse.ArgumentParser(
        description="OpenStack to BillingCloud MQ Consumer"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    subparsers.add_parser("start", help="Start the MQ consumer")
    subparsers.add_parser("health", help="Check API health")
    
    args = parser.parse_args()
    
    if args.command == "start":
        logger.info("Starting MQ Consumer...")
        logger.info(f"RabbitMQ: {mq_config.host}:{mq_config.port}")
        logger.info(f"API: {api_config.base_url}")
        asyncio.run(run_consumer())
        
    elif args.command == "health":
        healthy = asyncio.run(check_health())
        if healthy:
            print(f"✓ API at {api_config.base_url} is healthy")
        else:
            print(f"✗ API at {api_config.base_url} is not reachable")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
