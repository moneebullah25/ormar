from typing import Optional

import pytest

import ormar
from ormar.exceptions import QueryDefinitionError
from tests.lifespan import init_tests
from tests.settings import create_config

base_ormar_config = create_config()


class Item(ormar.Model):
    ormar_config = base_ormar_config.copy(tablename="items")

    id: int = ormar.Integer(primary_key=True)
    name: str = ormar.String(max_length=50)
    kind: str = ormar.String(max_length=50)


class City(ormar.Model):
    ormar_config = base_ormar_config.copy(tablename="cities")

    id: int = ormar.Integer(primary_key=True)
    name: str = ormar.String(max_length=50)


class Person(ormar.Model):
    ormar_config = base_ormar_config.copy(tablename="people")

    id: int = ormar.Integer(primary_key=True)
    city: Optional[City] = ormar.ForeignKey(City)


class Order(ormar.Model):
    ormar_config = base_ormar_config.copy(tablename="orders")

    id: int = ormar.Integer(primary_key=True)
    zbuyer: Optional[Person] = ormar.ForeignKey(Person, related_name="bought")
    aseller: Optional[Person] = ormar.ForeignKey(Person, related_name="sold")


create_test_database = init_tests(base_ormar_config)


async def create_items():
    for name, kind in [("a", "x"), ("b", "y"), ("c", "z"), ("d", "x")]:
        await Item.objects.create(name=name, kind=kind)


@pytest.mark.asyncio
async def test_chained_excludes_all_apply():
    async with base_ormar_config.database:
        async with base_ormar_config.database.transaction(force_rollback=True):
            await create_items()

            qs = Item.objects.exclude(kind="x").exclude(name="b")
            items = await qs.order_by("id").all()
            assert [item.name for item in items] == ["c"]

            items = await Item.objects.filter(kind="x").exclude(name="a").all()
            assert [item.name for item in items] == ["d"]

            items = await Item.objects.exclude(kind="x", name="a").order_by("id").all()
            assert [item.name for item in items] == ["b", "c", "d"]


@pytest.mark.asyncio
async def test_chained_excludes_update_and_delete():
    async with base_ormar_config.database:
        async with base_ormar_config.database.transaction(force_rollback=True):
            await create_items()

            qs = Item.objects.exclude(kind="x").exclude(name="b")
            assert await qs.update(kind="ZZ") == 1
            assert await Item.objects.filter(kind="ZZ").count() == 1

            assert await Item.objects.exclude(kind="ZZ").exclude(name="b").delete() == 2
            assert await Item.objects.count() == 2


@pytest.mark.asyncio
async def test_empty_exclude_is_noop():
    async with base_ormar_config.database:
        async with base_ormar_config.database.transaction(force_rollback=True):
            await create_items()

            assert await Item.objects.exclude().count() == 4
            assert await Item.objects.exclude(**{}).count() == 4
            with pytest.raises(QueryDefinitionError):
                await Item.objects.exclude().delete()


@pytest.mark.asyncio
async def test_chained_exclude_with_groups_and_limit():
    async with base_ormar_config.database:
        async with base_ormar_config.database.transaction(force_rollback=True):
            await create_items()

            items = (
                await Item.objects.exclude(ormar.or_(kind="x", name="b"))
                .exclude(name="z")
                .order_by("id")
                .all()
            )
            assert [item.name for item in items] == ["c"]

            items = (
                await Item.objects.exclude(name="a")
                .exclude(name="b")
                .order_by("id")
                .limit(1)
                .offset(1)
                .all()
            )
            assert [item.name for item in items] == ["d"]


@pytest.mark.asyncio
async def test_exclude_after_filter_keeps_the_filter():
    async with base_ormar_config.database:
        async with base_ormar_config.database.transaction(force_rollback=True):
            await create_items()

            items = await Item.objects.filter(kind="x").exclude().all()
            assert sorted(item.name for item in items) == ["a", "d"]


async def create_orders():
    x = await City.objects.create(name="X")
    y = await City.objects.create(name="Y")
    person_x = await Person.objects.create(city=x)
    person_y = await Person.objects.create(city=y)
    for order_id, buyer, seller in [
        (1, person_x, person_x),
        (2, person_x, person_y),
        (3, person_y, person_x),
        (4, person_y, person_y),
    ]:
        await Order.objects.create(id=order_id, zbuyer=buyer, aseller=seller)


async def order_ids(queryset):
    return sorted(order.id for order in await queryset.all())


@pytest.mark.asyncio
async def test_chained_clauses_on_paths_ending_at_the_same_tables():
    async with base_ormar_config.database:
        async with base_ormar_config.database.transaction(force_rollback=True):
            await create_orders()

            buyer_not_x = Order.objects.exclude(zbuyer__city__name="X")
            seller_not_y = Order.objects.exclude(aseller__city__name="Y")
            assert await order_ids(buyer_not_x.exclude(aseller__city__name="Y")) == [3]
            assert await order_ids(seller_not_y.exclude(zbuyer__city__name="X")) == [3]
            assert await order_ids(buyer_not_x.filter(aseller__city__name="X")) == [3]
            assert await order_ids(
                Order.objects.filter(zbuyer__city__name="Y").exclude(
                    aseller__city__name="Y"
                )
            ) == [3]


@pytest.mark.asyncio
async def test_derived_queryset_does_not_change_its_source():
    async with base_ormar_config.database:
        async with base_ormar_config.database.transaction(force_rollback=True):
            await create_orders()

            buyer_x = Order.objects.filter(zbuyer__city__name="X")
            buyer_not_x = Order.objects.exclude(zbuyer__city__name="X")
            assert await order_ids(buyer_x.filter(aseller__city__name="Y")) == [2]
            assert await order_ids(buyer_not_x.exclude(aseller__city__name="Y")) == [3]
            assert await order_ids(buyer_x) == [1, 2]
            assert await order_ids(buyer_not_x) == [3, 4]
