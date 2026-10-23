PRAGMA foreign_keys = ON;

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE commands (
    command_id TEXT PRIMARY KEY,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    risk TEXT NOT NULL DEFAULT 'unknown',
    read_only INTEGER NOT NULL DEFAULT 0 CHECK (read_only IN (0, 1)),
    requires_sudo INTEGER NOT NULL DEFAULT 1 CHECK (requires_sudo IN (0, 1)),
    requires_confirmation INTEGER NOT NULL DEFAULT 1 CHECK (requires_confirmation IN (0, 1)),
    definition_json TEXT NOT NULL
);

CREATE TABLE command_options (
    command_id TEXT NOT NULL,
    option_name TEXT NOT NULL,
    option_json TEXT NOT NULL,
    PRIMARY KEY (command_id, option_name),
    FOREIGN KEY (command_id) REFERENCES commands(command_id) ON DELETE CASCADE
);

CREATE TABLE workflows (
    workflow_id TEXT PRIMARY KEY,
    description TEXT NOT NULL DEFAULT '',
    triggers_json TEXT NOT NULL DEFAULT '[]',
    candidate_commands_json TEXT NOT NULL DEFAULT '[]',
    definition_json TEXT NOT NULL
);

CREATE TABLE workflow_commands (
    workflow_id TEXT NOT NULL,
    command_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (workflow_id, command_id),
    FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id) ON DELETE CASCADE,
    FOREIGN KEY (command_id) REFERENCES commands(command_id) ON DELETE RESTRICT
);

CREATE TABLE decision_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    rule_json TEXT NOT NULL,
    FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id) ON DELETE CASCADE
);

CREATE INDEX idx_commands_category ON commands(category);
CREATE INDEX idx_workflow_commands_workflow ON workflow_commands(workflow_id, position);
CREATE INDEX idx_decision_rules_workflow ON decision_rules(workflow_id, position);
