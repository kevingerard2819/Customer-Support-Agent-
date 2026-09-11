"""Validated, atomic local storage for human labels; no inference or prefilled labels."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile

INTENTS = ('billing_subscription', 'account_access_security', 'playback_app',
           'library_playlists', 'catalog_availability', 'feedback_feature_request',
           'social_acknowledgement', 'other_unclear')
ROUTES = ('auto_handle', 'escalate')
REASONS = ('account_action', 'security_privacy', 'sensitive_safety', 'insufficient_context',
           'unsupported_language_scope', 'unverified_policy', 'repeated_failure',
           'safe_clarification', 'safe_acknowledgement', 'supported_general_help')


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            shutil.copy2(path, str(path)+'.bak')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class Store:
    def __init__(self, packet_path, progress_path):
        self.packet = json.loads(Path(packet_path).read_text(encoding='utf-8'))
        self.examples = {x['tweet_id']: x for x in self.packet['examples']}
        if len(self.examples) != len(self.packet['examples']):
            raise ValueError('Duplicate example IDs in packet')
        self.path = Path(progress_path)
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding='utf-8'))
            self.validate(self.data)
        else:
            self.data = {'packet_id': self.packet['packet_id'], 'guide_version': self.packet['guide_version'],
                         'source': 'human_entries_in_local_annotation_tool', 'labels': {}}

    def validate(self, data):
        if data.get('packet_id') != self.packet['packet_id'] or data.get('guide_version') != self.packet['guide_version']:
            raise ValueError('Progress belongs to a different packet or guide')
        labels = data.get('labels')
        if not isinstance(labels, dict) or not set(labels) <= set(self.examples):
            raise ValueError('Progress contains unknown IDs or invalid labels')
        for label in labels.values():
            if label.get('intent', '') not in ('', *INTENTS) or label.get('route', '') not in ('', *ROUTES):
                raise ValueError('Invalid intent or route')
            if label.get('reason', '') not in ('', *REASONS) or label.get('flag', '') not in ('', 'Unsure', 'Discuss'):
                raise ValueError('Invalid reason or review flag')
            if not isinstance(label.get('notes', ''), str):
                raise ValueError('Notes must be text')

    def update(self, tweet_id, **fields):
        if tweet_id not in self.examples:
            raise ValueError('Unknown tweet ID')
        next_data = json.loads(json.dumps(self.data))
        label = dict(next_data['labels'].get(tweet_id, {}))
        label.update(fields)
        label['updated_at'] = datetime.now(timezone.utc).isoformat()
        next_data['labels'][tweet_id] = label
        self.validate(next_data)
        atomic_json(self.path, next_data)
        self.data = next_data  # Only acknowledge success after the durable write.

    def complete(self):
        return sum(bool(x.get('intent') and x.get('route')) for x in self.data['labels'].values())

    def export(self, destination):
        self.validate(self.data)
        atomic_json(destination, self.data)

    def restore(self, source):
        candidate = json.loads(Path(source).read_text(encoding='utf-8'))
        self.validate(candidate)
        atomic_json(self.path, candidate)
        self.data = candidate
