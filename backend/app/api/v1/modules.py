"""Module registry endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db_session
from app.models import Module
from app.schemas import ModuleResponse, ModuleUpdate, ModuleListResponse

router = APIRouter(prefix="/modules", tags=["modules"])


@router.get(
    "",
    response_model=ModuleListResponse,
    summary="List all registered modules",
)
async def list_modules(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    module_type: str | None = None,
    enabled_only: bool = False,
) -> ModuleListResponse:
    """
    Return registered modules, optionally filtered by module type or enabled state.
    
    Parameters:
        module_type (str | None): If provided, only modules with this `module_type` are included.
        enabled_only (bool): If True, include only modules whose `enabled` attribute is True.
    
    Returns:
        ModuleListResponse: Response containing `items` (list of validated ModuleResponse objects ordered by id) and `total` (integer count of matching modules).
    """
    query = select(Module)
    if module_type:
        query = query.where(Module.module_type == module_type)
    if enabled_only:
        query = query.where(Module.enabled == True)  # noqa: E712
    query = query.order_by(Module.id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar()

    result = await session.execute(query)
    modules = result.scalars().all()

    return ModuleListResponse(
        items=[ModuleResponse.model_validate(m) for m in modules],
        total=total,
    )


@router.get(
    "/{module_id}",
    response_model=ModuleResponse,
    summary="Get a module by ID",
)
async def get_module(
    module_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ModuleResponse:
    """
    Retrieve a module record by its ID.
    
    Raises:
        HTTPException: If no module exists with the given ID (404).
    
    Returns:
        ModuleResponse: The requested module serialized as a ModuleResponse.
    """
    query = select(Module).where(Module.id == module_id)
    result = await session.execute(query)
    module = result.scalar_one_or_none()

    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module with ID {module_id} not found",
        )

    return ModuleResponse.model_validate(module)


@router.patch(
    "/{module_id}",
    response_model=ModuleResponse,
    summary="Update a module (enable/disable, config)",
)
async def update_module(
    module_id: int,
    update: ModuleUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ModuleResponse:
    """
    Update fields of an existing module, persist the changes, and return the updated representation.
    
    Applies the values present in `update` to the module with the given `module_id`, commits the transaction, and returns the refreshed module as a `ModuleResponse`.
    
    Parameters:
        module_id (int): ID of the module to update.
        update (ModuleUpdate): Partial update payload containing fields to change.
    
    Returns:
        ModuleResponse: The updated module representation.
    
    Raises:
        HTTPException: 404 if a module with `module_id` does not exist.
    """
    query = select(Module).where(Module.id == module_id)
    result = await session.execute(query)
    module = result.scalar_one_or_none()

    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module with ID {module_id} not found",
        )

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(module, field, value)

    await session.commit()
    await session.refresh(module)
    return ModuleResponse.model_validate(module)
