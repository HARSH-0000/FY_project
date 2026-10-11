"""Run database migrations."""
import psycopg2
from app.core.config import settings

def run_migration():
    """Run the authentication and chat history migration."""
    
    # Read the migration SQL
    with open('migrations/add_auth_and_chat.sql', 'r') as f:
        migration_sql = f.read()
    
    # Connect to database
    conn = psycopg2.connect(settings.DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        # Execute migration
        cursor.execute(migration_sql)
        conn.commit()
        print("✅ Migration completed successfully!")
        print("Created tables: users, chat_sessions, chat_messages")
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    run_migration()
