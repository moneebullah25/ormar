import uuid
from typing import Optional

import pytest

import ormar
from tests.lifespan import init_tests
from tests.settings import create_config

base_ormar_config = create_config()


class NullableUuid(ormar.Model):
    ormar_config = base_ormar_config.copy(tablename="nullable_uuids")

    id: int = ormar.Integer(primary_key=True)
    name: str = ormar.String(max_length=100)
    u_hex: Optional[uuid.UUID] = ormar.UUID(nullable=True)
    u_str: Optional[uuid.UUID] = ormar.UUID(nullable=True, uuid_format="string")


create_test_database = init_tests(base_ormar_config)


@pytest.mark.asyncio
async def test_bulk_update_keeps_none_in_nullable_uuid_fields():
    async with base_ormar_config.database:
        async with base_ormar_config.database.transaction(force_rollback=True):
            first = await NullableUuid.objects.create(name="a")
            first.name = "b"
            await NullableUuid.objects.bulk_update([first], columns=["name"])

            second = await NullableUuid.objects.create(
                name="c", u_hex=uuid.uuid4(), u_str=uuid.uuid4()
            )
            second.u_str = None
            await NullableUuid.objects.bulk_update([second])

            assert (await NullableUuid.objects.get(id=first.id)).name == "b"
            loaded = await NullableUuid.objects.get(id=second.id)
            assert loaded.u_hex == second.u_hex
            assert loaded.u_str is None
