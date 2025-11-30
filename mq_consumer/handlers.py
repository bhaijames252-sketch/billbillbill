import asyncio
import logging
from typing import Optional, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime

from .parsers import ParsedEvent, ResourceType, EventType, parse_message
from .api_client import BillingAPIClient, APIResponse, APIResult, get_api_client
from .config import consumer_config

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    success: bool
    event: ParsedEvent
    api_response: Optional[APIResponse] = None
    error: Optional[str] = None
    processing_time_ms: float = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "event": self.event.to_dict(),
            "error": self.error,
            "processing_time_ms": self.processing_time_ms
        }


@dataclass
class ProcessingStats:
    total_processed: int = 0
    successful: int = 0
    failed: int = 0
    conflicts: int = 0
    not_found: int = 0
    
    by_resource_type: Dict[str, int] = field(default_factory=lambda: {
        "compute": 0, "disk": 0, "floating_ip": 0
    })
    by_event_type: Dict[str, int] = field(default_factory=dict)
    
    total_processing_time_ms: float = 0
    
    @property
    def avg_processing_time_ms(self) -> float:
        if self.total_processed == 0:
            return 0
        return self.total_processing_time_ms / self.total_processed
    
    def record(self, result: ProcessingResult):
        self.total_processed += 1
        self.total_processing_time_ms += result.processing_time_ms
        
        if result.success:
            self.successful += 1
        else:
            self.failed += 1
        
        if result.api_response:
            if result.api_response.result == APIResult.CONFLICT:
                self.conflicts += 1
            elif result.api_response.result == APIResult.NOT_FOUND:
                self.not_found += 1
        
        resource_type = result.event.resource_type.value
        self.by_resource_type[resource_type] = self.by_resource_type.get(resource_type, 0) + 1
        
        event_type = result.event.event_type.value
        self.by_event_type[event_type] = self.by_event_type.get(event_type, 0) + 1


class EventHandler:
    def __init__(self, api_client: BillingAPIClient = None):
        self.api_client = api_client or get_api_client()
        self.stats = ProcessingStats()
    
    async def process_event(self, event: ParsedEvent, skip_wallet: bool = False) -> ProcessingResult:
        start_time = datetime.utcnow()
        
        try:
            if not skip_wallet:
                try:
                    await self.api_client.ensure_wallet_exists(event.user_id)
                except Exception as e:
                    logger.debug(f"Wallet check skipped: {e}")
            
            if event.resource_type == ResourceType.COMPUTE:
                response = await self._handle_compute(event)
            elif event.resource_type == ResourceType.DISK:
                response = await self._handle_disk(event)
            elif event.resource_type == ResourceType.FLOATING_IP:
                response = await self._handle_floating_ip(event)
            else:
                response = APIResponse(
                    result=APIResult.ERROR,
                    status_code=0,
                    error=f"Unknown resource type: {event.resource_type}"
                )
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            success = response.result in (APIResult.SUCCESS, APIResult.CONFLICT)
            
            result = ProcessingResult(
                success=success,
                event=event,
                api_response=response,
                error=response.error if not success else None,
                processing_time_ms=processing_time
            )
            
            self.stats.record(result)
            
            if success:
                logger.debug(
                    f"Processed {event.resource_type.value}/{event.event_type.value} "
                    f"for {event.resource_id} in {processing_time:.2f}ms"
                )
            else:
                logger.warning(
                    f"Failed to process {event.resource_type.value}/{event.event_type.value} "
                    f"for {event.resource_id}: {response.error}"
                )
            
            return result
            
        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            result = ProcessingResult(
                success=False,
                event=event,
                error=str(e),
                processing_time_ms=processing_time
            )
            self.stats.record(result)
            logger.error(f"Exception processing event: {e}")
            return result
    
    async def _handle_compute(self, event: ParsedEvent) -> APIResponse:
        payload = event.payload
        
        if event.event_type == EventType.CREATE:
            return await self.api_client.create_compute(
                resource_id=event.resource_id,
                user_id=event.user_id,
                flavor=payload.get("flavor", "small")
            )
        
        elif event.event_type == EventType.DELETE:
            return await self.api_client.delete_compute(event.resource_id)
        
        elif event.event_type in (EventType.START, EventType.STOP, EventType.UPDATE):
            return await self.api_client.update_compute(
                resource_id=event.resource_id,
                state=payload.get("state")
            )
        
        elif event.event_type == EventType.RESIZE:
            return await self.api_client.update_compute(
                resource_id=event.resource_id,
                flavor=payload.get("flavor")
            )
        
        else:
            return await self.api_client.update_compute(
                resource_id=event.resource_id,
                state=payload.get("state"),
                flavor=payload.get("flavor")
            )
    
    async def _handle_disk(self, event: ParsedEvent) -> APIResponse:
        payload = event.payload
        
        if event.event_type == EventType.CREATE:
            return await self.api_client.create_disk(
                resource_id=event.resource_id,
                user_id=event.user_id,
                size_gb=payload.get("size_gb", 10)
            )
        
        elif event.event_type == EventType.DELETE:
            return await self.api_client.delete_disk(event.resource_id)
        
        elif event.event_type == EventType.RESIZE:
            return await self.api_client.update_disk(
                resource_id=event.resource_id,
                size_gb=payload.get("size_gb")
            )
        
        elif event.event_type in (EventType.ATTACH, EventType.DETACH):
            return APIResponse(result=APIResult.SUCCESS, status_code=200)
        
        else:
            return await self.api_client.update_disk(
                resource_id=event.resource_id,
                size_gb=payload.get("size_gb")
            )
    
    async def _handle_floating_ip(self, event: ParsedEvent) -> APIResponse:
        payload = event.payload
        
        if event.event_type in (EventType.CREATE, EventType.ALLOCATE):
            return await self.api_client.create_floating_ip(
                resource_id=event.resource_id,
                user_id=event.user_id,
                ip_address=payload.get("ip_address", "0.0.0.0")
            )
        
        elif event.event_type in (EventType.DELETE, EventType.RELEASE):
            return await self.api_client.release_floating_ip(event.resource_id)
        
        elif event.event_type in (EventType.ATTACH, EventType.DETACH, EventType.UPDATE):
            return APIResponse(result=APIResult.SUCCESS, status_code=200)
        
        else:
            return APIResponse(result=APIResult.SUCCESS, status_code=200)
    
    async def process_message(self, message: Dict[str, Any], skip_wallet: bool = None) -> Optional[ProcessingResult]:
        if skip_wallet is None:
            skip_wallet = consumer_config.skip_wallet
        event = parse_message(message)
        if event is None:
            logger.warning(f"Could not parse message: {message.get('event_type', 'unknown')}")
            return None
        return await self.process_event(event, skip_wallet=skip_wallet)
    
    async def process_batch(
        self,
        messages: list,
        max_concurrent: int = 10,
        skip_wallet: bool = None
    ) -> list:
        if skip_wallet is None:
            skip_wallet = consumer_config.skip_wallet
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_limit(msg):
            async with semaphore:
                return await self.process_message(msg, skip_wallet=skip_wallet)
        
        tasks = [process_with_limit(msg) for msg in messages]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch processing exception: {result}")
            elif result is not None:
                processed_results.append(result)
        
        return processed_results
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_processed": self.stats.total_processed,
            "successful": self.stats.successful,
            "failed": self.stats.failed,
            "conflicts": self.stats.conflicts,
            "not_found": self.stats.not_found,
            "by_resource_type": self.stats.by_resource_type,
            "by_event_type": self.stats.by_event_type,
            "avg_processing_time_ms": round(self.stats.avg_processing_time_ms, 2)
        }
    
    def reset_stats(self):
        self.stats = ProcessingStats()
