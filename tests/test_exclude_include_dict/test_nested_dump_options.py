import datetime
import json
from typing import Optional

import ormar
from tests.lifespan import init_tests
from tests.settings import create_config

base_ormar_config = create_config()


class Cat(ormar.Model):
    ormar_config = base_ormar_config.copy(tablename="cats")

    id: int = ormar.Integer(primary_key=True)
    created: Optional[datetime.datetime] = ormar.DateTime(nullable=True)
    note: Optional[str] = ormar.String(max_length=5, nullable=True)


class Pet(ormar.Model):
    ormar_config = base_ormar_config.copy(tablename="pets")

    id: int = ormar.Integer(primary_key=True)
    name: Optional[str] = ormar.String(max_length=5, nullable=True)
    cat: Optional[Cat] = ormar.ForeignKey(Cat, nullable=True)


create_test_database = init_tests(base_ormar_config)


def test_nested_model_respects_json_mode():
    pet = Pet(id=1, cat=Cat(id=2, created=datetime.datetime(2020, 1, 1)))
    dumped = pet.model_dump(mode="json")
    assert dumped["cat"]["created"] == "2020-01-01T00:00:00"
    json.dumps(dumped)


def test_nested_model_respects_exclude_none():
    pet = Pet(id=1, cat=Cat(id=2))
    assert pet.model_dump(exclude_none=True) == {"id": 1, "cat": {"id": 2}}
    assert Pet(id=1).model_dump(exclude_none=True) == {"id": 1}
    assert Pet(id=1).model_dump() == {"id": 1, "name": None, "cat": None}


def test_nested_list_respects_exclude_none():
    cat = Cat(id=2, pets=[Pet(id=1)])
    assert cat.model_dump(exclude_none=True) == {"id": 2, "pets": [{"id": 1}]}


def test_nested_model_respects_exclude_unset():
    pet = Pet(id=1, cat=Cat(id=2, note="x"))
    assert pet.model_dump(exclude_unset=True)["cat"] == {"id": 2, "note": "x"}
    pet = Pet(id=1, cat=Cat(id=2))
    assert pet.model_dump(exclude_unset=True)["cat"] == {"id": 2}


def test_flattened_relation_respects_json_mode_and_exclude_none():
    pet = Pet(id=1, cat=Cat(id=2))
    assert pet.model_dump(mode="json", flatten_all=True) == {
        "id": 1,
        "name": None,
        "cat": 2,
    }
    assert Pet(id=1).model_dump(exclude_none=True, flatten_all=True) == {"id": 1}


def test_nested_model_respects_exclude_defaults():
    pet = Pet(id=1, cat=Cat(id=2, note="x"))
    assert pet.model_dump(exclude_defaults=True)["cat"] == {"id": 2, "note": "x"}
