import asyncio
import json
import logging
from typing import Optional, Callable, Awaitable, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass

import aio_pika
from aio_pika import Message, DeliveryMode
from aio_pika.abc import AbstractIncomingMessage

from .config import mq_config, MQConfig
from .handlers import EventHandler, ProcessingResult
from .parsers import parse_message

logger = logging.getLogger(__name__)


@dataclass
class ConsumerMetrics:
    messages_received: int = 0
    messages_processed: int = 0
    messages_failed: int = 0
    messages_requeued: int = 0
    batches_processed: int = 0
    last_message_time: Optional[datetime] = None
    start_time: Optional[datetime] = None
    
    @property
    def uptime_seconds(self) -> float:
        if not self.start_time:
            return 0
        return (datetime.utcnow() - self.start_time).total_seconds()
    
    @property
    def messages_per_second(self) -> float:
        uptime = self.uptime_seconds
        if uptime == 0:
            return 0
        return self.messages_processed / uptime


class MessageBatcher:
    def __init__(
        self,
        batch_size: int = 50,
        batch_timeout: float = 1.0,
        process_callback: Callable[[List[Dict]], Awaitable[List[ProcessingResult]]] = None
    ):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.process_callback = process_callback
        self._batch: List[tuple] = []
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
    
    async def stop(self):
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self._flush()
    
    async def add(self, message: AbstractIncomingMessage, parsed: Dict):
        async with self._lock:
            self._batch.append((message, parsed))
            
            if len(self._batch) >= self.batch_size:
                batch = self._batch
                self._batch = []
                asyncio.create_task(self._process_batch(batch))
    
    async def _flush_loop(self):
        while self._running:
            await asyncio.sleep(self.batch_timeout)
            await self._flush()
    
    async def _flush(self):
        async with self._lock:
            if self._batch:
                batch = self._batch
                self._batch = []
                await self._process_batch(batch)
    
    async def _process_batch(self, batch: List[tuple]):
        if not batch or not self.process_callback:
            return
        
        messages = [parsed for _, parsed in batch]
        raw_messages = [msg for msg, _ in batch]
        
        try:
            results = await self.process_callback(messages)
            
            for i, (raw_msg, result) in enumerate(zip(raw_messages, results)):
                try:
                    if result and result.success:
                        await raw_msg.ack()
                    else:
                        await raw_msg.nack(requeue=True)
                except Exception as e:
                    logger.error(f"Error acking message: {e}")
                    
        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            for msg in raw_messages:
                try:
                    await msg.nack(requeue=True)
                except Exception:
                    pass


class MQConsumer:
    def __init__(
        self,
        config: MQConfig = None,
        handler: EventHandler = None,
        use_batching: bool = True
    ):
        self.config = config or mq_config
        self.handler = handler or EventHandler()
        self.use_batching = use_batching
        
        self._connection: Optional[aio_pika.RobustConnection] = None
        self._channel: Optional[aio_pika.RobustChannel] = None
        self._queue: Optional[aio_pika.Queue] = None
        self._running = False
        self._batcher: Optional[MessageBatcher] = None
        self.metrics = ConsumerMetrics()
    
    async def connect(self):
        logger.info(f"Connecting to RabbitMQ at {self.config.host}:{self.config.port}")
        
        self._connection = await aio_pika.connect_robust(
            self.config.url,
            reconnect_interval=self.config.reconnect_delay
        )
        
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self.config.prefetch_count)
        
        exchange = await self._channel.declare_exchange(
            self.config.exchange_name,
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        
        self._queue = await self._channel.declare_queue(
            self.config.queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": f"{self.config.queue_name}_dlq"
            }
        )
        
        await self._queue.bind(exchange, routing_key=self.config.routing_key)
        
        await self._channel.declare_queue(
            f"{self.config.queue_name}_dlq",
            durable=True
        )
        
        logger.info(f"Connected to RabbitMQ, queue: {self.config.queue_name}")
    
    async def disconnect(self):
        if self._batcher:
            await self._batcher.stop()
        
        if self._channel:
            await self._channel.close()
        
        if self._connection:
            await self._connection.close()
        
        logger.info("Disconnected from RabbitMQ")
    
    async def _process_message(self, message: AbstractIncomingMessage):
        self.metrics.messages_received += 1
        self.metrics.last_message_time = datetime.utcnow()
        
        try:
            body = json.loads(message.body.decode())
            body["_routing_key"] = message.routing_key
            
            if self.use_batching and self._batcher:
                await self._batcher.add(message, body)
            else:
                result = await self.handler.process_message(body)
                
                if result and result.success:
                    await message.ack()
                    self.metrics.messages_processed += 1
                else:
                    await message.nack(requeue=True)
                    self.metrics.messages_requeued += 1
                    
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message: {e}")
            await message.reject(requeue=False)
            self.metrics.messages_failed += 1
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await message.nack(requeue=True)
            self.metrics.messages_requeued += 1
    
    async def _batch_process_callback(self, messages: List[Dict]) -> List[ProcessingResult]:
        results = await self.handler.process_batch(messages)
        self.metrics.batches_processed += 1
        self.metrics.messages_processed += len([r for r in results if r and r.success])
        self.metrics.messages_failed += len([r for r in results if r and not r.success])
        return results
    
    async def start(self):
        if not self._connection:
            await self.connect()
        
        self._running = True
        self.metrics.start_time = datetime.utcnow()
        
        if self.use_batching:
            self._batcher = MessageBatcher(
                batch_size=self.config.batch_size,
                batch_timeout=self.config.batch_timeout,
                process_callback=self._batch_process_callback
            )
            await self._batcher.start()
        
        await self._queue.consume(self._process_message)
        logger.info("Started consuming messages")
        
        while self._running:
            await asyncio.sleep(1)
    
    async def stop(self):
        self._running = False
        logger.info("Stopping consumer...")
    
    def get_metrics(self) -> Dict[str, Any]:
        return {
            "messages_received": self.metrics.messages_received,
            "messages_processed": self.metrics.messages_processed,
            "messages_failed": self.metrics.messages_failed,
            "messages_requeued": self.metrics.messages_requeued,
            "batches_processed": self.metrics.batches_processed,
            "messages_per_second": round(self.metrics.messages_per_second, 2),
            "uptime_seconds": round(self.metrics.uptime_seconds, 2),
            "last_message_time": self.metrics.last_message_time.isoformat() if self.metrics.last_message_time else None,
            "handler_stats": self.handler.get_stats()
        }


async def run_consumer():
    consumer = MQConsumer()
    
    try:
        await consumer.start()
    except KeyboardInterrupt:
        pass
    finally:
        await consumer.stop()
        await consumer.disconnect()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(run_consumer())
