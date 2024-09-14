from utils.checks import check_connection

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
        except Exception:
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
    def get_all(self):
        try:
            self.cursor.execute("SELECT * FROM members")
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get all members: {e}")
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
            self.cursor.execute("UPDATE members SET credit_name = %s WHERE discord_id = %s", (credit_name, user_id))
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

    @check_connection
    def get_retired(self, user_id):
        try:
            self.cursor.execute("SELECT * FROM membersretired WHERE discord_id = %s", (user_id,))
            return self.cursor.fetchone()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get retired member '{user_id}': {e}")
        
    @check_connection
    def move_to_retired(self, member_id, roles):
        try:
            self.cursor.execute("SELECT * FROM members WHERE member_id = %s", (member_id,))
            member = self.cursor.fetchone()

            if member:
                self.cursor.execute("""
                    INSERT INTO MembersRetired (member_id, discord_id, credit_name, authority_level, roles, reminder_notifications, jobboard_notifications, stage_notifications, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (member_id) DO NOTHING;
                """, (member.member_id, member.discord_id, member.credit_name, member.authority_level, roles, member.reminder_notifications, member.jobboard_notifications, member.stage_notifications, member.created_at))
                self.cursor.execute("DELETE FROM members WHERE member_id = %s;", (member_id,))
                self.connection.commit()

                print(f"Member with ID {member_id} has been moved to MembersRetired.")
            else:
                print(f"Member with ID {member_id} does not exist in Members.")

        except Exception as e:
            self.connection.rollback()
            print(f"Failed to move member to retired: {e}")

    @check_connection
    def restore_from_retired(self, member_id):
        try:
            # Fetch the member from the MembersRetired table
            self.cursor.execute("SELECT * FROM MembersRetired WHERE member_id = %s", (member_id,))
            retired_member = self.cursor.fetchone()

            if retired_member:
                # Insert back into Members table
                self.cursor.execute("""
                    INSERT INTO members (member_id, discord_id, credit_name, authority_level, reminder_notifications, jobboard_notifications, stage_notifications, created_at, reminded_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (member_id) DO NOTHING;
                """, (retired_member.member_id, retired_member.discord_id, retired_member.credit_name, retired_member.authority_level, retired_member.reminder_notifications, retired_member.jobboard_notifications, retired_member.stage_notifications, retired_member.created_at))
                
                # Remove the member from MembersRetired
                self.cursor.execute("DELETE FROM MembersRetired WHERE member_id = %s;", (member_id,))
                self.connection.commit()

                print(f"Member with ID {member_id} has been restored to Members and removed from MembersRetired.")
            else:
                print(f"Member with ID {member_id} does not exist in MembersRetired.")

        except Exception as e:
            self.connection.rollback()
            print(f"Failed to restore member from retired: {e}")

    @check_connection
    def update_activity(self, user_id):
        try:
            self.cursor.execute("UPDATE members SET reminded_at = NULL WHERE discord_id = %s", (user_id,))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to update activity for '{user_id}': {e}")
            return None