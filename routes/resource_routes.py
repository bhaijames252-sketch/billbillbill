from fastapi import APIRouter, Depends, HTTPException, status, Query

from models.schemas import (
    ComputeCreateRequest,
    ComputeUpdateRequest,
    ComputeResponse,
    DiskCreateRequest,
    DiskUpdateRequest,
    DiskResponse,
    FloatingIPCreateRequest,
    FloatingIPUpdateRequest,
    FloatingIPResponse,
)
from services.resource_service import ResourceService

router = APIRouter(prefix="/resources", tags=["Resources"])


def get_resource_service() -> ResourceService:
    return ResourceService()


@router.post(
    "/computes",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create compute resource",
    description="Creates a new compute instance"
)
def create_compute(
    request: ComputeCreateRequest,
    service: ResourceService = Depends(get_resource_service)
):
    existing = service.get_compute(request.resource_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Compute resource already exists"
        )

    return service.create_compute(
        resource_id=request.resource_id,
        user_id=request.user_id,
        flavor=request.flavor
    )


@router.get(
    "/computes/{resource_id}",
    response_model=dict,
    summary="Get compute resource",
    description="Retrieves a compute instance by ID"
)
def get_compute(
    resource_id: str,
    service: ResourceService = Depends(get_resource_service)
):
    result = service.get_compute(resource_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compute resource not found"
        )
    return result


@router.get(
    "/computes/user/{user_id}",
    response_model=list,
    summary="Get user computes",
    description="Retrieves all compute instances for a user"
)
def get_user_computes(
    user_id: str,
    include_deleted: bool = Query(False, description="Include deleted compute instances"),
    service: ResourceService = Depends(get_resource_service)
):
    return service.get_user_computes(user_id, include_deleted=include_deleted)


@router.patch(
    "/computes/{resource_id}",
    response_model=dict,
    summary="Update compute resource",
    description="Updates compute state or flavor"
)
def update_compute(
    resource_id: str,
    request: ComputeUpdateRequest,
    service: ResourceService = Depends(get_resource_service)
):
    result = service.update_compute(
        resource_id=resource_id,
        state=request.state.value if request.state else None,
        flavor=request.flavor
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compute resource not found"
        )
    return result


@router.delete(
    "/computes/{resource_id}",
    response_model=dict,
    summary="Delete compute resource",
    description="Marks compute instance as deleted"
)
def delete_compute(
    resource_id: str,
    service: ResourceService = Depends(get_resource_service)
):
    result = service.delete_compute(resource_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compute resource not found"
        )
    return result


@router.post(
    "/disks",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create disk resource",
    description="Creates a new disk volume"
)
def create_disk(
    request: DiskCreateRequest,
    service: ResourceService = Depends(get_resource_service)
):
    existing = service.get_disk(request.resource_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Disk resource already exists"
        )

    return service.create_disk(
        resource_id=request.resource_id,
        user_id=request.user_id,
        size_gb=request.size_gb
    )


@router.get(
    "/disks/{resource_id}",
    response_model=dict,
    summary="Get disk resource",
    description="Retrieves a disk volume by ID"
)
def get_disk(
    resource_id: str,
    service: ResourceService = Depends(get_resource_service)
):
    result = service.get_disk(resource_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Disk resource not found"
        )
    return result


@router.get(
    "/disks/user/{user_id}",
    response_model=list,
    summary="Get user disks",
    description="Retrieves all disk volumes for a user"
)
def get_user_disks(
    user_id: str,
    include_deleted: bool = Query(False, description="Include deleted disk volumes"),
    service: ResourceService = Depends(get_resource_service)
):
    return service.get_user_disks(user_id, include_deleted=include_deleted)


@router.patch(
    "/disks/{resource_id}",
    response_model=dict,
    summary="Update disk resource",
    description="Updates disk state or size"
)
def update_disk(
    resource_id: str,
    request: DiskUpdateRequest,
    service: ResourceService = Depends(get_resource_service)
):
    result = service.update_disk(
        resource_id=resource_id,
        state=request.state.value if request.state else None,
        size_gb=request.size_gb
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Disk resource not found"
        )
    return result


@router.delete(
    "/disks/{resource_id}",
    response_model=dict,
    summary="Delete disk resource",
    description="Marks disk as deleted"
)
def delete_disk(
    resource_id: str,
    service: ResourceService = Depends(get_resource_service)
):
    result = service.delete_disk(resource_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Disk resource not found"
        )
    return result


@router.post(
    "/floating-ips",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create floating IP",
    description="Allocates a new floating IP"
)
def create_floating_ip(
    request: FloatingIPCreateRequest,
    service: ResourceService = Depends(get_resource_service)
):
    existing = service.get_floating_ip(request.resource_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Floating IP already exists"
        )

    return service.create_floating_ip(
        resource_id=request.resource_id,
        user_id=request.user_id,
        ip_address=request.ip_address
    )


@router.get(
    "/floating-ips/{resource_id}",
    response_model=dict,
    summary="Get floating IP",
    description="Retrieves a floating IP by ID"
)
def get_floating_ip(
    resource_id: str,
    service: ResourceService = Depends(get_resource_service)
):
    result = service.get_floating_ip(resource_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Floating IP not found"
        )
    return result


@router.get(
    "/floating-ips/user/{user_id}",
    response_model=list,
    summary="Get user floating IPs",
    description="Retrieves all floating IPs for a user"
)
def get_user_floating_ips(
    user_id: str,
    include_released: bool = Query(False, description="Include released floating IPs"),
    service: ResourceService = Depends(get_resource_service)
):
    return service.get_user_floating_ips(user_id, include_released=include_released)


@router.patch(
    "/floating-ips/{resource_id}",
    response_model=dict,
    summary="Update floating IP",
    description="Updates floating IP (release only)"
)
def update_floating_ip(
    resource_id: str,
    request: FloatingIPUpdateRequest,
    service: ResourceService = Depends(get_resource_service)
):
    result = service.update_floating_ip(
        resource_id=resource_id,
        release=request.release or False
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Floating IP not found"
        )
    return result


@router.delete(
    "/floating-ips/{resource_id}",
    response_model=dict,
    summary="Release floating IP",
    description="Releases a floating IP"
)
def release_floating_ip(
    resource_id: str,
    service: ResourceService = Depends(get_resource_service)
):
    result = service.release_floating_ip(resource_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Floating IP not found"
        )
    return result
