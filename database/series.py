from utils.checks import check_connection

class Series:
    def __init__(self, connection, cursor):
        self.connection = connection
        self.cursor = cursor

    @check_connection
    def new(self, group_id, name, drive_link, style_guide, mangadex, github_link, thumbnail):
        try:
            self.cursor.execute("INSERT INTO series (series_name, series_drive_link, style_guide, group_id, mangadex, github_link, thumbnail) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (series_name) DO NOTHING RETURNING series_id;", (name, drive_link, style_guide, group_id, mangadex, github_link, thumbnail))
            self.connection.commit()

            series_id = self.cursor.fetchone()

            if series_id:
                print(f"New series '{name}' added with ID {series_id[0]}.")
                return series_id[0]
            else:
                print(f"Series '{name}' already exists.")
                return None

        except Exception as e:
            self.connection.rollback()
            print(f"Failed to add new series: {e}")
            return None

    @check_connection
    def get_all(self):
        try:
            query = """
                SELECT s.series_id, s.series_name, s.series_drive_link, s.style_guide, s.mangadex,
                    g.group_id, g.group_name, s.thumbnail, s.is_archived,
                    s.github_link, s.blocked_websites
                FROM series s
                JOIN groups g ON s.group_id = g.group_id;
            """

            self.cursor.execute(query)
            self.connection.commit()
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to select all series: {e}")
            return []
        
    @check_connection
    def get_by_name(self, name: str):
        try:
            query = """
                SELECT s.series_id, s.series_name, s.series_drive_link, s.style_guide, s.mangadex,
                    g.group_id, g.group_name, s.thumbnail, s.is_archived,
                    s.github_link, s.blocked_websites
                FROM series s
                JOIN groups g ON s.group_id = g.group_id
                WHERE LOWER(s.series_name) = LOWER(%s)
                LIMIT 1;
            """
            self.cursor.execute(query, (name,))
            return self.cursor.fetchone()
        except Exception as e:
            print(f"Failed to get series by name '{name}': {e}")
            return None

    @check_connection
    def delete(self, group_name, series_name):
        try:
            query = """
                DELETE FROM series
                USING groups
                WHERE series.group_id = groups.group_id
                AND groups.group_name = %s
                AND series.series_name = %s;
            """
            self.cursor.execute(query, (group_name, series_name))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to delete series '{series_name}' from group '{group_name}': {e}")
            return None

    @check_connection
    def get_by_id(self, series_id):
        try:
            self.cursor.execute("SELECT * FROM series WHERE series_id = %s", (series_id,))
            self.connection.commit()
            return self.cursor.fetchone()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to select series '{series_id}': {e}")
            return []

    @check_connection
    def move(self, series_id, group_from_id, group_to_id):
        try:
            self.cursor.execute("UPDATE series SET group_id = %s WHERE group_id = %s", (group_to_id, group_from_id))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to move series with ID '{series_id}' from group '{group_from_id}' to group '{group_to_id}': {e}")
            return None

    @check_connection
    def get_by_group_id(self, group_id):
        try:
            self.cursor.execute("SELECT series_id, series_name, series_drive_link, style_guide, mangadex, group_id FROM series WHERE group_id = %s", (group_id,))
            self.connection.commit()
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to select all series from group: {e}")
            return []

    @check_connection
    def get_by_group_name(self, group_name):
        try:
            query = """
                SELECT s.series_id, s.series_name, s.series_drive_link, s.style_guide, s.mangadex, g.group_id
                FROM series s
                JOIN groups g ON s.group_id = g.group_id
                WHERE g.group_name = %s AND s.is_archived = FALSE;
            """
            self.cursor.execute(query, (group_name,))
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to select all series from group: {e}")
            return []
        
    @check_connection
    def update_blocked_websites(self, series_name, blocked_websites):
        try:
            query = """
                UPDATE series
                SET blocked_websites = %s
                WHERE series_name = %s;
            """
            self.cursor.execute(query, (blocked_websites, series_name))
            self.connection.commit()
            return True
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to update blocked websites for series '{series_name}': {e}")
            return False


    @check_connection
    def update(self, series_name, new_name = None, new_drive_link = None, new_style_guide = None, new_mangadex = None, new_github_link = None, new_thumbnail = None):
        updates = []
        params = []

        if new_name:
            updates.append("series_name = %s")
            params.append(new_name)
        if new_drive_link:
            updates.append("series_drive_link = %s")
            if new_drive_link.lower() == 'none':
                params.append(None)
            else:
                params.append(new_drive_link)
        if new_style_guide:
            updates.append("style_guide = %s")
            if new_style_guide.lower() == 'none':
                params.append(None)
            else:
                params.append(new_style_guide)
        if new_mangadex:
            updates.append("mangadex = %s")
            if new_mangadex == 'none':
                params.append(None)
            else:
                params.append(new_mangadex)
        if new_github_link:
            updates.append("github_link = %s")
            if new_github_link == 'none':
                params.append(None)
            else:
                params.append(new_github_link)

        if new_thumbnail:
            updates.append("thumbnail = %s")
            if new_thumbnail == 'none':
                params.append(None)
            else:
                params.append(new_thumbnail)
        
        if updates:
            params.append(series_name)

            try:
                self.cursor.execute(f"UPDATE series SET {', '.join(updates)} WHERE series_name = %s", tuple(params))
                self.connection.commit()
                return self.cursor.rowcount
            except Exception as e:
                self.connection.rollback()
                print(f"Failed to update series {series_name}: {e}")
                return None
        return 0

    @check_connection
    def count_chapters(self, series_name, count_archived = False):
        try:
            query = """
            SELECT COUNT(*) AS chapter_count
            FROM chapters c
            JOIN series s ON c.series_id = s.series_id
            WHERE s.series_name = %s
            """

            if not count_archived:
                query += " AND c.is_archived = FALSE"

            self.cursor.execute(query, (series_name,))
            return self.cursor.fetchone().chapter_count
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to count chapters for series '{series_name}': {e}")
            return None

    @check_connection
    def get_assignment(self, series_id, series_job_id):
        try:
            self.cursor.execute("SELECT * FROM seriesassignments WHERE series_id = %s AND series_job_id = %s", (series_id, series_job_id))
            return self.cursor.fetchone()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get assignment for series '{series_id}': {e}")
            return None

    @check_connection
    def get_assignments(self, series_id):
        try:
            self.cursor.execute("SELECT * FROM seriesassignments WHERE series_id = %s", (series_id,))
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get assignment for series '{series_id}': {e}")
            return None

    @check_connection
    def add_assignment(self, series_id, series_job_id, user_id):
        try:
            self.cursor.execute("INSERT INTO seriesassignments (series_id, series_job_id, assigned_to) VALUES (%s, %s, %s) ON CONFLICT(series_id, series_job_id) DO NOTHING RETURNING series_assignment_id;", (series_id, series_job_id, user_id))
            self.connection.commit()
            assignment_id = self.cursor.fetchone()

            if assignment_id:
                return assignment_id[0]

            return None
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to add assignment for series '{series_id}': {e}")
            return None

    @check_connection
    def remove_assignment(self, series_id, series_job_id):
        try:
            self.cursor.execute("DELETE FROM seriesassignments WHERE series_id = %s AND series_job_id = %s", (series_id, series_job_id))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to remove assignment for series '{series_id}': {e}")
            return None

    @check_connection
    def archive(self, series_id):
        try:
            self.cursor.execute("UPDATE series SET is_archived = TRUE WHERE series_id = %s", (series_id,))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to archive series with ID '{series_id}': {e}")
            return None

    @check_connection
    def unarchive(self, series_id):
        try:
            self.cursor.execute("UPDATE series SET is_archived = FALSE WHERE series_id = %s", (series_id,))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to unarchive series with ID '{series_id}': {e}")
            return None