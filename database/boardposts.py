from utils.checks import check_connection

class Boardposts:
    def __init__(self, connection, cursor):
        self.connection = connection
        self.cursor = cursor

    @check_connection
    def new(self, message_id, chapter_id, series_job_id, min_level):
        try:
            self.cursor.execute("INSERT INTO boardposts (message_id, chapter_id, series_job_id, staff_level) VALUES (%s, %s, %s, %s) ON CONFLICT (chapter_id, series_job_id) DO NOTHING RETURNING boardpost_id;", (message_id, chapter_id, series_job_id, min_level))
            self.connection.commit()
            
            boardpost_id = self.cursor.fetchone()
            if boardpost_id:
                return boardpost_id[0]

            return None
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to add new job board post: {e}")
            return None

    @check_connection
    def get_by_chapter(self, chapter_id, series_job_id):
        try:
            self.cursor.execute("SELECT * FROM boardposts WHERE chapter_id = %s AND series_job_id = %s", (chapter_id, series_job_id))
            return self.cursor.fetchone()
        except Exception as e:
            print(f"Failed to get job board post by chapter: {e}")
            return None

    @check_connection
    def get_for_removal(self):
        try:
            query = """
            SELECT bp.*, j.jobboard_channel
            FROM boardposts bp
            JOIN seriesjobs sj ON bp.series_job_id = sj.series_job_id
            JOIN jobs j ON sj.job_id = j.job_id
            WHERE bp.created_at <= NOW() - INTERVAL '7 days';
            """
            self.cursor.execute(query)
            self.connection.commit()
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get board posts for removal: {e}")
            return None

    @check_connection
    def get_by_series_and_job(self, series_id, job_id):
        try:
            query = """
            SELECT bp.* FROM boardposts bp
            JOIN SeriesJobs sj ON bp.series_job_id = sj.series_job_id
            WHERE sj.series_id = %s AND sj.job_id = %s
            """
            self.cursor.execute(query, (series_id, job_id))
            return self.cursor.fetchone()
        except Exception as e:
            print(f"Failed to get job board post by series and job: {e}")
            return None

    @check_connection
    def delete(self, boardpost_id):
        try:
            self.cursor.execute("DELETE FROM boardposts WHERE boardpost_id = %s", (boardpost_id,))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to delete job board post: {e}")
            return None

    @check_connection
    def get_by_message(self, message_id):
        try:
            self.cursor.execute("SELECT * FROM boardposts WHERE message_id = %s", (message_id,))
            return self.cursor.fetchone()
        except Exception as e:
            print(f"Failed to add get job board post: {e}")
            return None 