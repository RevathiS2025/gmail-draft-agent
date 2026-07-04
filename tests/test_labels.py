import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import labels


def test_get_or_create_label_id_returns_existing_without_creating():
    client = MagicMock()
    client.users.return_value.labels.return_value.list.return_value.execute.return_value = {
        "labels": [{"name": "Agent-Processed", "id": "L1"}]
    }

    label_id = labels.get_or_create_label_id(client, "Agent-Processed")

    assert label_id == "L1"
    client.users.return_value.labels.return_value.create.assert_not_called()


def test_get_or_create_label_id_creates_when_missing():
    client = MagicMock()
    client.users.return_value.labels.return_value.list.return_value.execute.return_value = {"labels": []}
    client.users.return_value.labels.return_value.create.return_value.execute.return_value = {"id": "L2"}

    label_id = labels.get_or_create_label_id(client, "Needs-Human")

    assert label_id == "L2"
    _, kwargs = client.users.return_value.labels.return_value.create.call_args
    assert kwargs["body"]["name"] == "Needs-Human"


def test_apply_label_calls_modify_with_resolved_label_id():
    client = MagicMock()
    client.users.return_value.labels.return_value.list.return_value.execute.return_value = {
        "labels": [{"name": "Agent-Processed", "id": "L1"}]
    }

    labels.apply_label(client, "msg-123", "Agent-Processed")

    _, kwargs = client.users.return_value.messages.return_value.modify.call_args
    assert kwargs["id"] == "msg-123"
    assert kwargs["body"] == {"addLabelIds": ["L1"]}
