from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime


class ResourceType(str, Enum):
    COMPUTE = "compute"
    DISK = "disk"
    FLOATING_IP = "floating_ip"


class EventType(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    START = "start"
    STOP = "stop"
    RESIZE = "resize"
    ATTACH = "attach"
    DETACH = "detach"
    ALLOCATE = "allocate"
    RELEASE = "release"


class ComputeState(str, Enum):
    ACTIVE = "active"
    STOPPED = "stopped"
    PAUSED = "paused"
    SUSPENDED = "suspended"
    SHUTOFF = "shutoff"
    DELETED = "deleted"
    ERROR = "error"
    BUILD = "build"


class DiskState(str, Enum):
    AVAILABLE = "available"
    IN_USE = "in-use"
    CREATING = "creating"
    DELETING = "deleting"
    DELETED = "deleted"
    ERROR = "error"


@dataclass
class ParsedEvent:
    resource_type: ResourceType
    event_type: EventType
    resource_id: str
    user_id: str
    timestamp: datetime
    payload: Dict[str, Any]
    raw_message: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_type": self.resource_type.value,
            "event_type": self.event_type.value,
            "resource_id": self.resource_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload
        }


OPENSTACK_STATE_MAP = {
    "active": "running",
    "stopped": "stopped",
    "paused": "stopped",
    "suspended": "stopped",
    "shutoff": "stopped",
    "deleted": "deleted",
    "error": "stopped",
    "build": "running",
}


class MessageParser:
    @staticmethod
    def parse_timestamp(ts: Any) -> datetime:
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, (int, float)):
            return datetime.utcfromtimestamp(ts)
        if isinstance(ts, str):
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
            ]:
                try:
                    return datetime.strptime(ts, fmt)
                except ValueError:
                    continue
        return datetime.utcnow()
    
    @staticmethod
    def extract_user_id(message: Dict[str, Any]) -> Optional[str]:
        payload = message.get("payload", {})
        
        if "floatingip" in payload:
            fip = payload["floatingip"]
            for key in ["tenant_id", "project_id", "user_id"]:
                if key in fip:
                    return str(fip[key])
        
        for key in ["user_id", "tenant_id", "project_id", "owner_id", "owner"]:
            if key in message:
                return str(message[key])
            if key in payload:
                return str(payload[key])
        return None
    
    @staticmethod
    def extract_resource_id(message: Dict[str, Any]) -> Optional[str]:
        payload = message.get("payload", {})
        
        if "floatingip" in payload:
            fip = payload["floatingip"]
            if "id" in fip:
                return str(fip["id"])
        
        for key in ["resource_id", "instance_id", "volume_id", "floatingip_id", "id"]:
            if key in message:
                return str(message[key])
            if key in payload:
                return str(payload[key])
        return None
    
    @staticmethod
    def detect_resource_type(message: Dict[str, Any]) -> Optional[ResourceType]:
        event_type = message.get("event_type", "").lower()
        routing_key = message.get("_routing_key", "").lower()
        oslo_type = message.get("oslo.message_type", "").lower()
        
        if any(x in event_type for x in ["instance", "compute", "server"]):
            return ResourceType.COMPUTE
        if any(x in event_type for x in ["volume", "disk"]):
            return ResourceType.DISK
        if any(x in event_type for x in ["floatingip", "floating_ip", "fip"]):
            return ResourceType.FLOATING_IP
        
        if "compute" in routing_key or "nova" in routing_key:
            return ResourceType.COMPUTE
        if "volume" in routing_key or "cinder" in routing_key:
            return ResourceType.DISK
        if "floatingip" in routing_key or "neutron" in routing_key:
            if "floatingip" in str(message).lower():
                return ResourceType.FLOATING_IP
        
        payload = message.get("payload", {})
        if "instance_id" in payload or "flavor" in payload:
            return ResourceType.COMPUTE
        if "volume_id" in payload or "size" in payload and "instance_id" not in payload:
            return ResourceType.DISK
        if "floating_ip_address" in payload or "floatingip" in payload:
            return ResourceType.FLOATING_IP
        
        return None
    
    @staticmethod
    def detect_event_type(message: Dict[str, Any]) -> EventType:
        event_str = message.get("event_type", "").lower()
        
        if any(x in event_str for x in ["create", "build", "spawn"]):
            return EventType.CREATE
        if any(x in event_str for x in ["delete", "destroy", "terminate"]):
            return EventType.DELETE
        if any(x in event_str for x in ["start", "power_on", "resume", "unpause"]):
            return EventType.START
        if any(x in event_str for x in ["stop", "power_off", "pause", "suspend", "shutdown"]):
            return EventType.STOP
        if "resize" in event_str:
            return EventType.RESIZE
        if "attach" in event_str:
            return EventType.ATTACH
        if "detach" in event_str:
            return EventType.DETACH
        if "allocate" in event_str:
            return EventType.ALLOCATE
        if any(x in event_str for x in ["release", "deallocate"]):
            return EventType.RELEASE
        if "update" in event_str:
            return EventType.UPDATE
        
        return EventType.UPDATE


class ComputeParser:
    @staticmethod
    def parse(message: Dict[str, Any], event_type: EventType) -> Dict[str, Any]:
        payload = message.get("payload", message)
        
        flavor_name = None
        if "flavor" in payload:
            flavor = payload["flavor"]
            if isinstance(flavor, dict):
                flavor_name = flavor.get("name", flavor.get("id"))
            else:
                flavor_name = str(flavor)
        elif "instance_type" in payload:
            flavor_name = payload["instance_type"]
        
        state = None
        if "state" in payload:
            os_state = payload["state"].lower()
            state = OPENSTACK_STATE_MAP.get(os_state, os_state)
        elif event_type == EventType.CREATE:
            state = "running"
        elif event_type == EventType.DELETE:
            state = "deleted"
        elif event_type == EventType.START:
            state = "running"
        elif event_type == EventType.STOP:
            state = "stopped"
        
        result = {}
        if flavor_name:
            result["flavor"] = flavor_name
        if state:
            result["state"] = state
            
        return result


class DiskParser:
    @staticmethod
    def parse(message: Dict[str, Any], event_type: EventType) -> Dict[str, Any]:
        payload = message.get("payload", message)
        
        result = {}
        
        if "size" in payload:
            result["size_gb"] = int(payload["size"])
        
        if "attachments" in payload and payload["attachments"]:
            attachment = payload["attachments"][0] if isinstance(payload["attachments"], list) else payload["attachments"]
            result["attached_to"] = attachment.get("server_id", attachment.get("instance_id"))
        elif "instance_uuid" in payload:
            result["attached_to"] = payload["instance_uuid"]
        
        state = None
        if "status" in payload:
            status = payload["status"].lower()
            if status == "in-use":
                state = "attached"
            elif status == "available":
                state = "detached"
            elif status == "deleted":
                state = "deleted"
        elif event_type == EventType.DELETE:
            state = "deleted"
        elif event_type == EventType.ATTACH:
            state = "attached"
        elif event_type == EventType.DETACH:
            state = "detached"
        
        if state:
            result["state"] = state
            
        return result


class FloatingIPParser:
    @staticmethod
    def parse(message: Dict[str, Any], event_type: EventType) -> Dict[str, Any]:
        payload = message.get("payload", message)
        
        if "floatingip" in payload:
            payload = payload["floatingip"]
        
        result = {}
        
        for key in ["floating_ip_address", "ip_address", "floating_ip", "address"]:
            if key in payload:
                result["ip_address"] = payload[key]
                break
        
        if "port_id" in payload:
            result["port_id"] = payload["port_id"]
        
        for key in ["fixed_ip_address", "instance_id", "server_id"]:
            if key in payload:
                result["attached_to"] = payload.get("instance_id") or payload.get("server_id")
                break
        
        return result


def parse_message(message: Dict[str, Any]) -> Optional[ParsedEvent]:
    resource_type = MessageParser.detect_resource_type(message)
    if not resource_type:
        return None
    
    event_type = MessageParser.detect_event_type(message)
    resource_id = MessageParser.extract_resource_id(message)
    user_id = MessageParser.extract_user_id(message)
    
    if not resource_id or not user_id:
        return None
    
    timestamp = MessageParser.parse_timestamp(
        message.get("timestamp") or message.get("generated") or message.get("created_at")
    )
    
    if resource_type == ResourceType.COMPUTE:
        payload = ComputeParser.parse(message, event_type)
    elif resource_type == ResourceType.DISK:
        payload = DiskParser.parse(message, event_type)
    elif resource_type == ResourceType.FLOATING_IP:
        payload = FloatingIPParser.parse(message, event_type)
    else:
        payload = {}
    
    return ParsedEvent(
        resource_type=resource_type,
        event_type=event_type,
        resource_id=resource_id,
        user_id=user_id,
        timestamp=timestamp,
        payload=payload,
        raw_message=message
    )
