-- schema.sql
-- New installs: apply this against a fresh database.
-- Existing databases: recreate with:
--   docker-compose down -v && docker-compose up -d
-- (the three new columns — error_class, root_cause, last_similarity — cannot be
--  added with a simple ALTER TABLE on older MySQL without a stored procedure)

CREATE TABLE IF NOT EXISTS memories (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    error_text      TEXT         NOT NULL,
    embedding       JSON         NOT NULL,
    error_class     VARCHAR(100) DEFAULT NULL,     -- short LLM-generated label
    root_cause      TEXT         DEFAULT NULL,     -- one-sentence root cause
    last_similarity FLOAT        DEFAULT 0,        -- cosine score the last time this matched a NEW error
                                                   -- (retrieval only; dedup self-matches are excluded)
    success_count   INT          DEFAULT 0,
    created_at      TIMESTAMP    DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fix_attempts (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    memory_id  INT          NOT NULL,
    fix_text   TEXT         NOT NULL,
    result     VARCHAR(10)  NOT NULL,
    created_at TIMESTAMP    DEFAULT NOW(),
    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS runs (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64)  NOT NULL,
    task       TEXT         NOT NULL,
    iterations JSON,
    status     VARCHAR(20)  DEFAULT 'running',
    created_at TIMESTAMP    DEFAULT NOW(),
    INDEX idx_session (session_id)
);
