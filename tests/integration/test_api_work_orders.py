"""Integration tests for the work-orders router."""

from __future__ import annotations

from httpx import AsyncClient


async def test_list_work_orders(client: AsyncClient, expected_seed_counts: dict[str, int]) -> None:
    response = await client.get("/api/work-orders")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == expected_seed_counts["work_orders"]
    # PascalCase wire keys + ordered newest-first by requested date.
    assert "WorkOrderNumber" in body[0]
    assert "Priority" in body[0]
    dates = [wo["RequestedDate"] for wo in body]
    assert dates == sorted(dates, reverse=True)


async def test_list_work_orders_status_filter(client: AsyncClient) -> None:
    response = await client.get("/api/work-orders?status=Open")
    assert response.status_code == 200
    body = response.json()
    assert all(wo["Status"] == "Open" for wo in body)


async def test_get_work_order_by_id(client: AsyncClient) -> None:
    response = await client.get("/api/work-orders/1")
    assert response.status_code == 200
    body = response.json()
    assert body["Id"] == 1
    assert "WorkOrderNumber" in body


async def test_get_work_order_404_for_unknown(client: AsyncClient) -> None:
    response = await client.get("/api/work-orders/99999")
    assert response.status_code == 404
