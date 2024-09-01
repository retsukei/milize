from utils.checks import check_connection
from utils.constants import AuthorityLevel

class Members:
    def __init__(self, connection, cursor):
        self.connection = connection
        self.cursor = cursor

    @check_connection
    def add(self, user_id, authority):
        try:
            self.cursor.execute("INSERT INTO members (discord_id, authority_level) VALUES (%s, %s) ON CONFLICT (discord_id) DO NOTHING RETURNING member_id;", (user_id, authority))
            self.connection.commit()
            member_id = self.cursor.fetchone()
        
            if member_id:
                return member_id[0]
            
            return None
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to add user '{user_id}' to the database.")
            return None

    @check_connection
    def get(self, user_id):
        try:
            self.cursor.execute("SELECT * FROM members WHERE discord_id = %s", (user_id,))
            self.connection.commit()
            return self.cursor.fetchone()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get member '{user_id}': {e}")
            return None

    @check_connection
    def delete(self, user_id):
        try:
            self.cursor.execute("DELETE FROM members WHERE discord_id = %s", (user_id,))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to remove member '{user_id}': {e}")
            return None

    @check_connection
    def get_with_reminder_notif(self):
        try:
            self.cursor.execute("SELECT * FROM members WHERE reminder_notifications > 0")
            self.connection.commit()
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get members with reminder notifications: {e}")
            return None

    @check_connection
    def update_notifications(self, user_id, reminder, jobboard, stage):
        updates = []
        params = []

        if reminder is not None:
            updates.append("reminder_notifications = %s")
            params.append(reminder)
        if jobboard is not None:
            updates.append("jobboard_notifications = %s")
            params.append(jobboard)
        if stage is not None:
            updates.append("stage_notifications = %s")
            params.append(stage)
        
        if updates:
            params.append(user_id)

            try:
                self.cursor.execute(f"UPDATE members SET {', '.join(updates)} WHERE discord_id = %s", tuple(params))
                self.connection.commit()
                return self.cursor.rowcount
            except Exception as e:
                self.connection.rollback()
                print(f"Failed to update notifications for '{user_id}': {e}")
                return None
        return 0

    @check_connection
    def set_credit_name(self, user_id, credit_name):
        try:
            self.cursor.execute(f"UPDATE members SET credit_name = %s WHERE discord_id = %s", (credit_name, user_id))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to set credit name for '{user_id}': {e}")
            return None

    @check_connection
    def set_authority(self, user_id, authority):
        try:
            self.cursor.execute("UPDATE members SET authority_level = %s WHERE discord_id = %s", (authority, user_id))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to set authority for user '{user_id}': {e}")
            return None

    @check_connection
    def get_authority(self, user_id):
        try:
            self.cursor.execute("SELECT authority_level FROM members WHERE discord_id = %s", (user_id,))
            self.connection.commit()
            result = self.cursor.fetchone()

            if result:
                return result[0]

            return None
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get authority level for '{user_id}': {e}")
            return None
        