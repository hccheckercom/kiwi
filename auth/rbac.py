"""Role-Based Access Control for team collaboration."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set


class Role(Enum):
    """User roles with hierarchical permissions."""
    ADMIN = "admin"          # Full access: manage users, approve all fixes, configure settings
    LEAD = "lead"            # Approve fixes, manage team preferences, view all violations
    DEVELOPER = "developer"  # Run scans, apply approved fixes, dismiss violations
    VIEWER = "viewer"        # Read-only: view violations and reports


class Permission(Enum):
    """Granular permissions."""
    # Scan permissions
    SCAN_RUN = "scan:run"
    SCAN_VIEW = "scan:view"

    # Fix permissions
    FIX_APPLY = "fix:apply"
    FIX_APPROVE = "fix:approve"
    FIX_REJECT = "fix:reject"

    # Violation permissions
    VIOLATION_DISMISS = "violation:dismiss"
    VIOLATION_REOPEN = "violation:reopen"

    # Lesson permissions
    LESSON_CREATE = "lesson:create"
    LESSON_EDIT = "lesson:edit"
    LESSON_DELETE = "lesson:delete"

    # Team permissions
    TEAM_MANAGE = "team:manage"
    TEAM_VIEW = "team:view"

    # User permissions
    USER_MANAGE = "user:manage"
    USER_VIEW = "user:view"

    # Settings permissions
    SETTINGS_EDIT = "settings:edit"
    SETTINGS_VIEW = "settings:view"


# Role → Permissions mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        Permission.SCAN_RUN, Permission.SCAN_VIEW,
        Permission.FIX_APPLY, Permission.FIX_APPROVE, Permission.FIX_REJECT,
        Permission.VIOLATION_DISMISS, Permission.VIOLATION_REOPEN,
        Permission.LESSON_CREATE, Permission.LESSON_EDIT, Permission.LESSON_DELETE,
        Permission.TEAM_MANAGE, Permission.TEAM_VIEW,
        Permission.USER_MANAGE, Permission.USER_VIEW,
        Permission.SETTINGS_EDIT, Permission.SETTINGS_VIEW,
    },
    Role.LEAD: {
        Permission.SCAN_RUN, Permission.SCAN_VIEW,
        Permission.FIX_APPLY, Permission.FIX_APPROVE, Permission.FIX_REJECT,
        Permission.VIOLATION_DISMISS, Permission.VIOLATION_REOPEN,
        Permission.LESSON_CREATE, Permission.LESSON_EDIT,
        Permission.TEAM_VIEW,
        Permission.USER_VIEW,
        Permission.SETTINGS_VIEW,
    },
    Role.DEVELOPER: {
        Permission.SCAN_RUN, Permission.SCAN_VIEW,
        Permission.FIX_APPLY,
        Permission.VIOLATION_DISMISS,
        Permission.LESSON_CREATE,
        Permission.TEAM_VIEW,
        Permission.SETTINGS_VIEW,
    },
    Role.VIEWER: {
        Permission.SCAN_VIEW,
        Permission.TEAM_VIEW,
        Permission.SETTINGS_VIEW,
    },
}


@dataclass
class User:
    """User account."""
    id: int
    username: str
    email: str
    role: Role
    team_id: Optional[int] = None
    active: bool = True

    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        return permission in ROLE_PERMISSIONS.get(self.role, set())

    def can_approve_fix(self) -> bool:
        """Check if user can approve fixes."""
        return self.has_permission(Permission.FIX_APPROVE)

    def can_manage_team(self) -> bool:
        """Check if user can manage team settings."""
        return self.has_permission(Permission.TEAM_MANAGE)


@dataclass
class Team:
    """Team with shared preferences."""
    id: int
    name: str
    preferences: Dict[str, any]
    member_ids: List[int]

    def get_preference(self, key: str, default=None):
        """Get team preference value."""
        return self.preferences.get(key, default)

    def set_preference(self, key: str, value):
        """Set team preference value."""
        self.preferences[key] = value


class RBACManager:
    """Manage users, teams, and permissions."""

    def __init__(self, db_path: str = ".kiwi_sessions/rbac.db"):
        """Initialize RBAC manager with database."""
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL,
                team_id INTEGER,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Teams table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                preferences TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Audit log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT,
                details TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        conn.commit()
        conn.close()

    def create_user(
        self, username: str, email: str, role: Role, team_id: Optional[int] = None
    ) -> User:
        """Create new user."""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO users (username, email, role, team_id) VALUES (?, ?, ?, ?)",
            (username, email, role.value, team_id)
        )

        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return User(
            id=user_id,
            username=username,
            email=email,
            role=role,
            team_id=team_id
        )

    def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, username, email, role, team_id, active FROM users WHERE id = ?",
            (user_id,)
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return User(
            id=row[0],
            username=row[1],
            email=row[2],
            role=Role(row[3]),
            team_id=row[4],
            active=bool(row[5])
        )

    def create_team(self, name: str, preferences: Optional[Dict] = None) -> Team:
        """Create new team."""
        import sqlite3
        import json

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        prefs_json = json.dumps(preferences or {})
        cursor.execute(
            "INSERT INTO teams (name, preferences) VALUES (?, ?)",
            (name, prefs_json)
        )

        team_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return Team(
            id=team_id,
            name=name,
            preferences=preferences or {},
            member_ids=[]
        )

    def log_action(
        self,
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[str] = None
    ):
        """Log user action to audit trail."""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO audit_log (user_id, action, resource_type, resource_id, details) VALUES (?, ?, ?, ?, ?)",
            (user_id, action, resource_type, resource_id, details)
        )

        conn.commit()
        conn.close()