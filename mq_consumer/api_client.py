import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

import httpx

from .config import api_config, APIConfig

logger = logging.getLogger(__name__)


class APIError(Exception):
    def __init__(self, status_code: int, message: str, response: Optional[Dict] = None):
        self.status_code = status_code
        self.message = message
        self.response = response
        super().__init__(f"API Error {status_code}: {message}")


class APIResult(Enum):
    SUCCESS = "success"
    CONFLICT = "conflict"
    NOT_FOUND = "not_found"
    ERROR = "error"


@dataclass
class APIResponse:
    result: APIResult
    status_code: int
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BillingAPIClient:
    def __init__(self, config: APIConfig = None):
        self.config = config or api_config
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            async with self._lock:
                if self._client is None or self._client.is_closed:
                    limits = httpx.Limits(
                        max_connections=self.config.max_connections,
                        max_keepalive_connections=self.config.max_keepalive
                    )
                    self._client = httpx.AsyncClient(
                        base_url=self.config.base_url,
                        timeout=httpx.Timeout(self.config.timeout),
                        limits=limits,
                        http2=True
                    )
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _request(
        self,
        method: str,
        url: str,
        json: Optional[Dict] = None,
        retry_count: int = None
    ) -> APIResponse:
        retry_count = retry_count or self.config.retry_count
        client = await self._get_client()
        
        for attempt in range(retry_count):
            try:
                response = await client.request(method, url, json=json)
                
                if response.status_code == 409:
                    return APIResponse(
                        result=APIResult.CONFLICT,
                        status_code=409,
                        data=response.json() if response.content else None
                    )
                
                if response.status_code == 404:
                    return APIResponse(
                        result=APIResult.NOT_FOUND,
                        status_code=404,
                        error="Resource not found"
                    )
                
                if response.status_code >= 400:
                    try:
                        error_data = response.json() if response.content else {}
                    except Exception:
                        error_data = {"detail": response.text or "Unknown error"}
                    return APIResponse(
                        result=APIResult.ERROR,
                        status_code=response.status_code,
                        error=error_data.get("detail", str(error_data))
                    )
                
                return APIResponse(
                    result=APIResult.SUCCESS,
                    status_code=response.status_code,
                    data=response.json() if response.content else None
                )
                
            except httpx.TimeoutException as e:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{retry_count}): {url}")
                if attempt == retry_count - 1:
                    return APIResponse(
                        result=APIResult.ERROR,
                        status_code=0,
                        error=f"Request timeout: {str(e)}"
                    )
                await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                
            except httpx.ConnectError as e:
                logger.warning(f"Connection error (attempt {attempt + 1}/{retry_count}): {url}")
                if attempt == retry_count - 1:
                    return APIResponse(
                        result=APIResult.ERROR,
                        status_code=0,
                        error=f"Connection error: {str(e)}"
                    )
                await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                return APIResponse(
                    result=APIResult.ERROR,
                    status_code=0,
                    error=str(e)
                )
        
        return APIResponse(
            result=APIResult.ERROR,
            status_code=0,
            error="Max retries exceeded"
        )
    
    async def create_compute(
        self,
        resource_id: str,
        user_id: str,
        flavor: str = "small"
    ) -> APIResponse:
        return await self._request(
            "POST",
            f"{self.config.api_prefix}/resources/computes",
            json={
                "resource_id": resource_id,
                "user_id": user_id,
                "flavor": flavor
            }
        )
    
    async def update_compute(
        self,
        resource_id: str,
        state: Optional[str] = None,
        flavor: Optional[str] = None
    ) -> APIResponse:
        payload = {}
        if state:
            payload["state"] = state
        if flavor:
            payload["flavor"] = flavor
        
        if not payload:
            return APIResponse(result=APIResult.SUCCESS, status_code=200)
        
        return await self._request(
            "PATCH",
            f"{self.config.api_prefix}/resources/computes/{resource_id}",
            json=payload
        )
    
    async def delete_compute(self, resource_id: str) -> APIResponse:
        return await self._request(
            "DELETE",
            f"{self.config.api_prefix}/resources/computes/{resource_id}"
        )
    
    async def get_compute(self, resource_id: str) -> APIResponse:
        return await self._request(
            "GET",
            f"{self.config.api_prefix}/resources/computes/{resource_id}"
        )
    
    async def create_disk(
        self,
        resource_id: str,
        user_id: str,
        size_gb: int
    ) -> APIResponse:
        payload = {
            "resource_id": resource_id,
            "user_id": user_id,
            "size_gb": size_gb
        }
        
        return await self._request(
            "POST",
            f"{self.config.api_prefix}/resources/disks",
            json=payload
        )
    
    async def update_disk(
        self,
        resource_id: str,
        state: Optional[str] = None,
        size_gb: Optional[int] = None
    ) -> APIResponse:
        payload = {}
        if state:
            payload["state"] = state
        if size_gb:
            payload["size_gb"] = size_gb
        
        if not payload:
            return APIResponse(result=APIResult.SUCCESS, status_code=200)
        
        return await self._request(
            "PATCH",
            f"{self.config.api_prefix}/resources/disks/{resource_id}",
            json=payload
        )
    
    async def delete_disk(self, resource_id: str) -> APIResponse:
        return await self._request(
            "DELETE",
            f"{self.config.api_prefix}/resources/disks/{resource_id}"
        )
    
    async def get_disk(self, resource_id: str) -> APIResponse:
        return await self._request(
            "GET",
            f"{self.config.api_prefix}/resources/disks/{resource_id}"
        )
    
    async def create_floating_ip(
        self,
        resource_id: str,
        user_id: str,
        ip_address: str
    ) -> APIResponse:
        payload = {
            "resource_id": resource_id,
            "user_id": user_id,
            "ip_address": ip_address
        }
        
        return await self._request(
            "POST",
            f"{self.config.api_prefix}/resources/floating-ips",
            json=payload
        )
    
    async def release_floating_ip(self, resource_id: str) -> APIResponse:
        return await self._request(
            "DELETE",
            f"{self.config.api_prefix}/resources/floating-ips/{resource_id}"
        )
    
    async def get_floating_ip(self, resource_id: str) -> APIResponse:
        return await self._request(
            "GET",
            f"{self.config.api_prefix}/resources/floating-ips/{resource_id}"
        )
    
    async def create_wallet(
        self,
        user_id: str,
        balance: float = 0,
        currency: str = "USD"
    ) -> APIResponse:
        return await self._request(
            "POST",
            f"{self.config.api_prefix}/wallets",
            json={
                "user_id": user_id,
                "balance": balance,
                "currency": currency,
                "auto_recharge": False
            }
        )
    
    async def get_wallet(self, user_id: str) -> APIResponse:
        return await self._request(
            "GET",
            f"{self.config.api_prefix}/wallets/{user_id}"
        )
    
    async def ensure_wallet_exists(
        self,
        user_id: str,
        default_balance: float = 0
    ) -> APIResponse:
        response = await self.get_wallet(user_id)
        if response.result == APIResult.NOT_FOUND:
            return await self.create_wallet(user_id, default_balance)
        return response
    
    async def compute_bill(
        self,
        user_id: str
    ) -> APIResponse:
        return await self._request(
            "POST",
            f"{self.config.api_prefix}/billing/compute",
            json={"user_id": user_id}
        )
    
    async def health_check(self) -> bool:
        try:
            response = await self._request("GET", "/health", retry_count=1)
            return response.result == APIResult.SUCCESS
        except Exception:
            return False


_client_instance: Optional[BillingAPIClient] = None


def get_api_client() -> BillingAPIClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = BillingAPIClient()
    return _client_instance


async def close_api_client():
    global _client_instance
    if _client_instance:
        await _client_instance.close()
        _client_instance = None
