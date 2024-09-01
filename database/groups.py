from utils.checks import check_connection

class Groups:
    def __init__(self, connection, cursor):
        self.connection = connection
        self.cursor = cursor

    @check_connection
    def new(self, name, discord, website, creator_id):
        try:
            self.cursor.execute("INSERT INTO groups (group_name, discord, website, creator_id) VALUES (%s, %s, %s, %s) ON CONFLICT (group_name) DO NOTHING RETURNING group_id;", (name, discord, website, creator_id))
            self.connection.commit()

            group_id = self.cursor.fetchone()

            if group_id:
                print(f"New group {name} added with ID {group_id[0]}.")
                return group_id[0]
            else:
                print(f"Group {name} already exists.")
                return None
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to add new group: {e}")
            return None

    @check_connection
    def delete(self, group_name):
        try:
            self.cursor.execute("DELETE FROM groups WHERE group_name = %s", (group_name,))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to delete group '{group_name}': {e}")
            return None

    @check_connection
    def get_all(self):
        try:
            self.cursor.execute("SELECT group_id, group_name, discord, website, creator_id, created_at FROM groups")
            self.connection.commit()
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to select all groups: {e}")
            return []

    @check_connection
    def get_by_name(self, group_name):
        try:
            self.cursor.execute(f"SELECT group_id, group_name, discord, website, creator_id, created_at FROM groups WHERE group_name = %s", (group_name,))
            self.connection.commit()
            return self.cursor.fetchone()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to select group '{group_name}': {e}")
            return None

    @check_connection
    def update(self, group_name, new_name = None, new_discord = None, new_website = None):
        updates = []
        params = []

        if new_name:
            updates.append("group_name = %s")
            params.append(new_name)
        if new_discord:
            updates.append("discord = %s")
            params.append(new_discord)
        if new_website:
            updates.append("website = %s")
            params.append(new_website)
        
        if updates:
            params.append(group_name)

            try:
                self.cursor.execute(f"UPDATE groups SET {', '.join(updates)} WHERE group_name = %s", tuple(params))
                self.connection.commit()
                return self.cursor.rowcount
            except Exception as e:
                self.connection.rollback()
                print(f"Failed to update group {group_name}: {e}")
                return None
        return 0