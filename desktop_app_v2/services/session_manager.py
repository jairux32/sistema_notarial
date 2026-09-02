"""Session persistence manager"""
import json
import os

SESSION_FILE = 'session.json'


class SessionManager:
    def __init__(self, session_dir=None):
        if session_dir is None:
            session_dir = os.path.dirname(os.path.abspath(__file__))
        self.session_path = os.path.join(os.path.dirname(session_dir), SESSION_FILE)

    def save(self, token, user_data):
        data = {'token': token, 'user': user_data}
        with open(self.session_path, 'w') as f:
            json.dump(data, f, indent=2)

    def load(self):
        if not os.path.exists(self.session_path):
            return None, None
        try:
            with open(self.session_path, 'r') as f:
                data = json.load(f)
            return data.get('token'), data.get('user')
        except (json.JSONDecodeError, KeyError):
            return None, None

    def clear(self):
        if os.path.exists(self.session_path):
            os.remove(self.session_path)

    def exists(self):
        return os.path.exists(self.session_path)
