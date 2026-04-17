"""
Unit tests for the Drone model (picture_path column / picture_url property)
and the DroneResponse schema (picture_url field).

These tests are pure Python — no database or network required.
"""

import pytest
from datetime import datetime
from typing import Optional

from app.models.drone import Drone
from app.schemas.drone import DroneResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_drone(
    drone_id: int = 1,
    name: str = "Test Quad",
    picture_path: Optional[str] = None,
) -> Drone:
    """Return an in-memory Drone ORM object (not persisted)."""
    return Drone(
        id=drone_id,
        name=name,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        picture_path=picture_path,
    )


# ---------------------------------------------------------------------------
# Drone.picture_url property
# ---------------------------------------------------------------------------

class TestDronePictureUrlProperty:
    def test_returns_none_when_picture_path_is_none(self):
        drone = _make_drone(picture_path=None)
        assert drone.picture_url is None

    def test_returns_none_when_picture_path_is_empty_string(self):
        """Empty string is falsy and must produce None, not an endpoint URL."""
        drone = _make_drone(picture_path="")
        assert drone.picture_url is None

    def test_returns_api_path_when_picture_path_is_set(self):
        drone = _make_drone(drone_id=7, picture_path="drone-pictures/7/some-uuid.jpg")
        assert drone.picture_url == "/api/v1/drones/7/picture"

    def test_url_contains_correct_drone_id(self):
        drone = _make_drone(drone_id=42, picture_path="drone-pictures/42/abc.png")
        assert "/42/" in drone.picture_url

    def test_url_does_not_depend_on_picture_path_value(self):
        """The URL is derived from the drone id, not the actual path stored."""
        drone = _make_drone(drone_id=3, picture_path="some/completely/different/path.webp")
        assert drone.picture_url == "/api/v1/drones/3/picture"

    def test_url_format_for_different_ids(self):
        for drone_id in (1, 100, 9999):
            drone = _make_drone(drone_id=drone_id, picture_path="x")
            assert drone.picture_url == f"/api/v1/drones/{drone_id}/picture"

    def test_picture_path_attribute_accepts_none(self):
        """Verify that picture_path=None is stored and retrievable."""
        drone = _make_drone(picture_path=None)
        assert drone.picture_path is None

    def test_picture_path_attribute_stores_value(self):
        path = "drone-pictures/1/uuid.jpg"
        drone = _make_drone(picture_path=path)
        assert drone.picture_path == path

    def test_picture_path_max_length_boundary(self):
        """picture_path should accept a string of up to 512 characters."""
        long_path = "a" * 512
        drone = _make_drone(picture_path=long_path)
        assert drone.picture_path == long_path


# ---------------------------------------------------------------------------
# DroneResponse schema — picture_url field
# ---------------------------------------------------------------------------

class TestDroneResponsePictureUrl:
    def test_picture_url_defaults_to_none(self):
        """When created without picture_url, the field defaults to None."""
        data = {
            "id": 1,
            "name": "My Drone",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        response = DroneResponse(**data)
        assert response.picture_url is None

    def test_picture_url_accepts_string_value(self):
        data = {
            "id": 1,
            "name": "My Drone",
            "picture_url": "/api/v1/drones/1/picture",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        response = DroneResponse(**data)
        assert response.picture_url == "/api/v1/drones/1/picture"

    def test_picture_url_accepts_none_explicitly(self):
        data = {
            "id": 2,
            "name": "Drone",
            "picture_url": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        response = DroneResponse(**data)
        assert response.picture_url is None

    def test_model_validate_from_drone_without_picture(self):
        """model_validate must map the ORM picture_url property (None) correctly."""
        drone = _make_drone(drone_id=10, picture_path=None)
        response = DroneResponse.model_validate(drone)
        assert response.picture_url is None

    def test_model_validate_from_drone_with_picture(self):
        """model_validate must map the ORM picture_url property to the schema field."""
        drone = _make_drone(drone_id=10, picture_path="drone-pictures/10/uuid.jpg")
        response = DroneResponse.model_validate(drone)
        assert response.picture_url == "/api/v1/drones/10/picture"

    def test_model_validate_preserves_drone_id(self):
        drone = _make_drone(drone_id=99, picture_path="drone-pictures/99/x.png")
        response = DroneResponse.model_validate(drone)
        assert response.id == 99

    def test_model_validate_preserves_drone_name(self):
        drone = _make_drone(name="Racing Quad", picture_path=None)
        response = DroneResponse.model_validate(drone)
        assert response.name == "Racing Quad"

    def test_picture_url_field_is_optional_in_schema(self):
        """picture_url must be Optional – the field annotation must allow None."""
        import inspect
        hints = DroneResponse.model_fields
        assert "picture_url" in hints
        field = hints["picture_url"]
        # Pydantic v2: is_required() returns False for Optional fields with a default
        assert not field.is_required()

    def test_model_json_serializes_picture_url_as_null_when_none(self):
        drone = _make_drone(drone_id=5, picture_path=None)
        response = DroneResponse.model_validate(drone)
        json_data = response.model_dump()
        assert "picture_url" in json_data
        assert json_data["picture_url"] is None

    def test_model_json_serializes_picture_url_string_when_set(self):
        drone = _make_drone(drone_id=5, picture_path="drone-pictures/5/img.png")
        response = DroneResponse.model_validate(drone)
        json_data = response.model_dump()
        assert json_data["picture_url"] == "/api/v1/drones/5/picture"


# ---------------------------------------------------------------------------
# Drone model __repr__
# ---------------------------------------------------------------------------

class TestDroneRepr:
    def test_repr_includes_id_and_name(self):
        drone = _make_drone(drone_id=3, name="Speedy")
        r = repr(drone)
        assert "3" in r
        assert "Speedy" in r