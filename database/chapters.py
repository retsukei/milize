from utils.checks import check_connection

class Chapters:
    def __init__(self, connection, cursor):
        self.connection = connection
        self.cursor = cursor

    @check_connection
    def new(self, series_name, chapter_name, drive_link = None):
        try:
            query = """
            WITH series_cte AS (
                SELECT series_id FROM series WHERE series_name = %s
            )
            INSERT INTO chapters (series_id, chapter_name, drive_link)
            SELECT series_id, %s, %s FROM series_cte
            ON CONFLICT (series_id, chapter_name) DO NOTHING
            RETURNING chapter_id;
            """
            self.cursor.execute(query, (series_name, chapter_name, drive_link))
            self.connection.commit()

            chapter_id = self.cursor.fetchone()

            if chapter_id:
                return chapter_id[0]
            else:
                return None
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to add chapter '{chapter_name}' for series '{series_name}': {e}")
            return None
        
    @check_connection
    def new_upload_schedule(
        self,
        volume_number: int,
        chapter_number: int,
        language: str,
        chapter_name: str,
        group_ids: list[str],
        series_id: str,
        folder_name: str,
        upload_time, 
        discord_id: str,
        series_name: str,
        group_name: str,
        github_link: str,
        upload_websites: list[str],
        chapter_id: int
    ):
        try:
            query = """
            INSERT INTO UploadSchedules (
                volume_number,
                chapter_number,
                language,
                chapter_name,
                group_ids,
                series_id,
                folder_name,
                upload_time,
                discord_id,
                series_name,
                group_name,
                github_link,
                upload_websites,
                chapter_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING upload_id;
            """
            self.cursor.execute(query, (
                volume_number,
                chapter_number,
                language,
                chapter_name,
                group_ids,
                series_id,
                folder_name,
                upload_time,
                discord_id,
                series_name,
                group_name,
                github_link,
                upload_websites,
                chapter_id
            ))
            self.connection.commit()

            result = self.cursor.fetchone()
            if result:
                return result[0]
            else:
                return None
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to create upload schedule for chapter '{chapter_name}': {e}")
            return None
        
    @check_connection
    def get_active_scheduled_upload(self):
        try:
            query = """
            SELECT *
            FROM uploadschedules
            WHERE upload_time <= NOW()
            ORDER BY upload_time ASC
            LIMIT 1;
            """
            self.cursor.execute(query)
            result = self.cursor.fetchone()
            return result
        except Exception as e:
            print(f"Failed to fetch scheduled upload: {e}")
            return None
        
    @check_connection
    def get_scheduled_upload_by_chapter(self, chapter_id):
        try:
            query = """
            SELECT * FROM uploadschedules WHERE chapter_id = %s;
            """
            
            self.cursor.execute(query, (chapter_id,))
            return self.cursor.fetchone()
        except Exception as e:
            print(f"Failed to fetch scheduled upload: {e}")
            return None
        
    @check_connection
    def get_scheduled_upload(self, upload_id):
        try:
            query = """
            SELECT * FROM uploadschedules WHERE upload_id = %s;
            """
            
            self.cursor.execute(query, (upload_id,))
            return self.cursor.fetchone()
        except Exception as e:
            print(f"Failed to fetch scheduled upload: {e}")
            return None
        
    @check_connection
    def delete_upload_schedule(self, upload_id: int):
        try:
            query = "DELETE FROM uploadschedules WHERE upload_id = %s;"
            self.cursor.execute(query, (upload_id,))
            self.connection.commit()

            if self.cursor.rowcount > 0:
                return True
            else:
                return False
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to delete upload schedule with ID {upload_id}: {e}")
            return False

    @check_connection
    def delete(self, series_name, chapter_name):
        try:
            query = """
            DELETE FROM chapters
            WHERE chapter_id = (
                SELECT c.chapter_id
                FROM chapters c
                JOIN series s ON c.series_id = s.series_id
                WHERE s.series_name = %s AND c.chapter_name = %s
            );
            """
            
            self.cursor.execute(query, (series_name, chapter_name))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to delete chapter '{chapter_name}' for series '{series_name}': {e}")
            return None

    @check_connection
    def update(self, series_name, chapter_name, new_name=None, new_drive_link=None):
        updates = []
        params = []

        if new_name:
            updates.append("chapter_name = %s")
            params.append(new_name)
        if new_drive_link:
            updates.append("drive_link = %s")
            params.append(new_drive_link)

        if updates:
            params.extend([series_name, chapter_name])
            
            try:
                query = f"""
                UPDATE chapters
                SET {', '.join(updates)}
                WHERE chapter_id = (
                    SELECT c.chapter_id
                    FROM chapters c
                    JOIN series s ON c.series_id = s.series_id
                    WHERE s.series_name = %s AND c.chapter_name = %s
                );
                """
                self.cursor.execute(query, tuple(params))
                self.connection.commit()
                return self.cursor.rowcount
            except Exception as e:
                self.connection.rollback()
                print(f"Failed to update chapter '{chapter_name}' for series '{series_name}': {e}")
                return None
            
        return 0

    @check_connection
    def get(self, series_name, chapter_name):
        try:
            query = """
            SELECT c.chapter_id, c.chapter_name, c.drive_link, c.series_id, c.is_archived
            FROM chapters c
            JOIN series s ON c.series_id = s.series_id
            WHERE s.series_name = %s AND c.chapter_name = %s;
            """
            self.cursor.execute(query, (series_name, chapter_name))
            self.connection.commit()
            return self.cursor.fetchone()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get chapter '{chapter_name}' for series '{series_name}': {e}")
            return None

    @check_connection
    def get_by_id(self, chapter_id):
        try:
            self.cursor.execute("SELECT * FROM chapters WHERE chapter_id = %s", (chapter_id,))
            self.connection.commit()
            return self.cursor.fetchone()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get chapter with ID '{chapter_id}': {e}")
            return None

    @check_connection
    def get_by_series_name(self, series_name):
        try:
            query = """
            SELECT c.chapter_id, c.chapter_name, c.drive_link, c.is_archived
            FROM Chapters c
            JOIN Series s ON c.series_id = s.series_id
            WHERE s.series_name = %s AND c.is_archived = FALSE;
            """
            self.cursor.execute(query, (series_name,))
            self.connection.commit()
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to list chapters for series '{series_name}': {e}")
            return []

    @check_connection
    def archive(self, chapter_id):
        try:
            self.cursor.execute("UPDATE chapters SET is_archived = TRUE WHERE chapter_id = %s;", (chapter_id,))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to archive chapter with ID '{chapter_id}': {e}")
            return None

    @check_connection
    def unarchive(self, chapter_id):
        try:
            self.cursor.execute("UPDATE chapters SET is_archived = FALSE WHERE chapter_id = %s;", (chapter_id,))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to unarchive chapter with ID '{chapter_id}': {e}")
            return None

    @check_connection
    def archive_all(self, series_id):
        try:
            self.cursor.execute("UPDATE chapters SET is_archived = TRUE WHERE series_id = %s;", (series_id,))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to archive all chapters for series with ID `{series_id}`: {e}")
            return None