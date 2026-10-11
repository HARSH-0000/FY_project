-- Migration: Add authentication and chat history tables
-- Run this after the initial database setup

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);

-- Chat sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_updated_at ON chat_sessions(updated_at DESC);

-- Chat messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content JSONB NOT NULL,
    route VARCHAR(50),
    sources JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_created_at ON chat_messages(created_at);

-- Comments
COMMENT ON TABLE users IS 'User accounts for authentication';
COMMENT ON TABLE chat_sessions IS 'Chat conversation sessions';
COMMENT ON TABLE chat_messages IS 'Individual messages in chat sessions';

COMMENT ON COLUMN users.hashed_password IS 'Bcrypt hashed password';
COMMENT ON COLUMN chat_messages.content IS 'Structured message content (JSON)';
COMMENT ON COLUMN chat_messages.role IS 'Message sender: user or assistant';
COMMENT ON COLUMN chat_messages.route IS 'Research tier: SIMPLE, VERIFICATION, or COMPLEX';
COMMENT ON COLUMN chat_messages.sources IS 'Source citations (JSON array)';
