CREATE TABLE IF NOT EXISTS memories (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    error_text    TEXT NOT NULL,
    embedding     JSON NOT NULL,
    success_count INT DEFAULT 0,
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fix_attempts (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    memory_id  INT NOT NULL,
    fix_text   TEXT NOT NULL,
    result     VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS runs (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    task       TEXT NOT NULL,
    iterations JSON,
    status     VARCHAR(20) DEFAULT 'running',
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_session (session_id)
);
