from datetime import datetime
from typing import Optional, List
import uuid

from db.config import get_mongo_db


class ResourceService:
    COMPUTE_COLLECTION = "compute_resources"
    DISK_COLLECTION = "disk_resources"
    FLOATING_IP_COLLECTION = "floating_ip_resources"

    def __init__(self):
        self.mongo_db = get_mongo_db()
        self.compute_col = self.mongo_db[self.COMPUTE_COLLECTION]
        self.disk_col = self.mongo_db[self.DISK_COLLECTION]
        self.floating_ip_col = self.mongo_db[self.FLOATING_IP_COLLECTION]

    def _generate_event_id(self, prefix: str = "evt") -> str:
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    def create_compute(
        self,
        resource_id: str,
        user_id: str,
        flavor: str = "small"
    ) -> dict:
        now = datetime.utcnow()
        resource = {
            "resource_id": resource_id,
            "user_id": user_id,
            "state": "running",
            "current_flavor": flavor,
            "created_at": now.isoformat() + "Z",
            "deleted_at": None,
            "last_billed_until": now.isoformat() + "Z",
            "events": [
                {
                    "event_id": self._generate_event_id(),
                    "time": now.isoformat() + "Z",
                    "type": "create",
                    "meta": {"flavor": flavor}
                }
            ]
        }
        self.compute_col.insert_one(resource)
        resource.pop("_id", None)
        return resource

    def get_compute(self, resource_id: str) -> Optional[dict]:
        resource = self.compute_col.find_one({"resource_id": resource_id})
        if resource:
            resource.pop("_id", None)
        return resource

    def get_user_computes(self, user_id: str) -> List[dict]:
        resources = list(self.compute_col.find({"user_id": user_id, "deleted_at": None}))
        for r in resources:
            r.pop("_id", None)
        return resources

    def update_compute(
        self,
        resource_id: str,
        state: Optional[str] = None,
        flavor: Optional[str] = None
    ) -> Optional[dict]:
        resource = self.compute_col.find_one({"resource_id": resource_id})
        if not resource:
            return None

        now = datetime.utcnow()
        updates = {}
        event = {"event_id": self._generate_event_id(), "time": now.isoformat() + "Z"}

        if state:
            updates["state"] = state
            event["type"] = state
            if state == "deleted":
                updates["deleted_at"] = now.isoformat() + "Z"

        if flavor:
            updates["current_flavor"] = flavor
            event["type"] = "resize"
            event["meta"] = {"flavor": flavor}

        if updates:
            self.compute_col.update_one(
                {"resource_id": resource_id},
                {"$set": updates, "$push": {"events": event}}
            )

        updated = self.compute_col.find_one({"resource_id": resource_id})
        updated.pop("_id", None)
        return updated

    def delete_compute(self, resource_id: str) -> Optional[dict]:
        return self.update_compute(resource_id, state="deleted")

    def create_disk(
        self,
        resource_id: str,
        user_id: str,
        size_gb: int,
        attached_to: Optional[str] = None
    ) -> dict:
        now = datetime.utcnow()
        resource = {
            "resource_id": resource_id,
            "user_id": user_id,
            "size_gb": size_gb,
            "state": "attached" if attached_to else "detached",
            "attached_to": attached_to,
            "created_at": now.isoformat() + "Z",
            "deleted_at": None,
            "last_billed_until": now.isoformat() + "Z",
            "events": [
                {
                    "event_id": self._generate_event_id("evt_d"),
                    "time": now.isoformat() + "Z",
                    "type": "create",
                    "meta": {"size_gb": size_gb}
                }
            ]
        }
        self.disk_col.insert_one(resource)
        resource.pop("_id", None)
        return resource

    def get_disk(self, resource_id: str) -> Optional[dict]:
        resource = self.disk_col.find_one({"resource_id": resource_id})
        if resource:
            resource.pop("_id", None)
        return resource

    def get_user_disks(self, user_id: str) -> List[dict]:
        resources = list(self.disk_col.find({"user_id": user_id, "deleted_at": None}))
        for r in resources:
            r.pop("_id", None)
        return resources

    def update_disk(
        self,
        resource_id: str,
        state: Optional[str] = None,
        size_gb: Optional[int] = None,
        attached_to: Optional[str] = None
    ) -> Optional[dict]:
        resource = self.disk_col.find_one({"resource_id": resource_id})
        if not resource:
            return None

        now = datetime.utcnow()
        updates = {}
        event = {"event_id": self._generate_event_id("evt_d"), "time": now.isoformat() + "Z"}

        if state:
            updates["state"] = state
            event["type"] = state
            if state == "deleted":
                updates["deleted_at"] = now.isoformat() + "Z"

        if size_gb:
            updates["size_gb"] = size_gb
            event["type"] = "resize"
            event["meta"] = {"size_gb": size_gb}

        if attached_to is not None:
            updates["attached_to"] = attached_to if attached_to else None
            updates["state"] = "attached" if attached_to else "detached"
            event["type"] = "attach" if attached_to else "detach"

        if updates:
            self.disk_col.update_one(
                {"resource_id": resource_id},
                {"$set": updates, "$push": {"events": event}}
            )

        updated = self.disk_col.find_one({"resource_id": resource_id})
        updated.pop("_id", None)
        return updated

    def delete_disk(self, resource_id: str) -> Optional[dict]:
        return self.update_disk(resource_id, state="deleted")

    def create_floating_ip(
        self,
        resource_id: str,
        user_id: str,
        ip_address: str,
        port_id: Optional[str] = None,
        attached_to: Optional[str] = None
    ) -> dict:
        now = datetime.utcnow()
        resource = {
            "resource_id": resource_id,
            "user_id": user_id,
            "ip_address": ip_address,
            "port_id": port_id,
            "attached_to": attached_to,
            "created_at": now.isoformat() + "Z",
            "released_at": None,
            "last_billed_until": now.isoformat() + "Z",
            "events": [
                {
                    "event_id": self._generate_event_id("evt_ip"),
                    "time": now.isoformat() + "Z",
                    "type": "allocate"
                }
            ]
        }
        self.floating_ip_col.insert_one(resource)
        resource.pop("_id", None)
        return resource

    def get_floating_ip(self, resource_id: str) -> Optional[dict]:
        resource = self.floating_ip_col.find_one({"resource_id": resource_id})
        if resource:
            resource.pop("_id", None)
        return resource

    def get_user_floating_ips(self, user_id: str) -> List[dict]:
        resources = list(self.floating_ip_col.find({"user_id": user_id, "released_at": None}))
        for r in resources:
            r.pop("_id", None)
        return resources

    def update_floating_ip(
        self,
        resource_id: str,
        port_id: Optional[str] = None,
        attached_to: Optional[str] = None,
        release: bool = False
    ) -> Optional[dict]:
        resource = self.floating_ip_col.find_one({"resource_id": resource_id})
        if not resource:
            return None

        now = datetime.utcnow()
        updates = {}
        event = {"event_id": self._generate_event_id("evt_ip"), "time": now.isoformat() + "Z"}

        if release:
            updates["released_at"] = now.isoformat() + "Z"
            event["type"] = "release"
        else:
            if port_id is not None:
                updates["port_id"] = port_id
            if attached_to is not None:
                updates["attached_to"] = attached_to
                event["type"] = "attach" if attached_to else "detach"

        if updates:
            self.floating_ip_col.update_one(
                {"resource_id": resource_id},
                {"$set": updates, "$push": {"events": event}}
            )

        updated = self.floating_ip_col.find_one({"resource_id": resource_id})
        updated.pop("_id", None)
        return updated

    def release_floating_ip(self, resource_id: str) -> Optional[dict]:
        return self.update_floating_ip(resource_id, release=True)

    def update_last_billed(self, collection_name: str, resource_id: str, billed_until: datetime):
        collection = getattr(self, f"{collection_name}_col")
        collection.update_one(
            {"resource_id": resource_id},
            {"$set": {"last_billed_until": billed_until.isoformat() + "Z"}}
        )
