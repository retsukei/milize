from utils.checks import check_connection

class Jobs:
    def __init__(self, connection, cursor):
        self.connection = connection
        self.cursor = cursor

    @check_connection
    def new(self, job_name, role_id, job_type, creator_id):
        try:
            self.cursor.execute("INSERT INTO jobs (job_name, role_id, job_type, creator_id) VALUES (%s, %s, %s, %s) ON CONFLICT (job_name) DO NOTHING RETURNING job_id;", (job_name, role_id, job_type, creator_id))
            self.connection.commit()

            job_id = self.cursor.fetchone()

            if job_id:
                print(f"New job {job_name} added with ID {job_id[0]}.")
                return job_id[0]
            else:
                print(f"Job {job_name} already exists.")
                return None

        except Exception as e:
            self.connection.rollback()
            print(f"Failed to add new job: {e}")
            return None

    @check_connection
    def update(self, job_name, role_id, job_type, updated_job_name):
        try:
            self.cursor.execute("UPDATE jobs SET role_id = %s, job_type = %s, job_name = %s WHERE job_name = %s", (role_id, job_type, updated_job_name, job_name))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to update job '{job_name}': {e}")
            return None

    @check_connection
    def delete(self, job_name):
        try:
            self.cursor.execute("DELETE FROM jobs WHERE job_name = %s", (job_name,))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to delete job: {e}")
            return None

    @check_connection
    def get_all(self):
        try:
            self.cursor.execute("SELECT job_id, job_name, role_id, creator_id, job_type FROM jobs")
            self.connection.commit()
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to select all jobs: {e}")
            return []

    @check_connection
    def get(self, job_name):
        try:
            self.cursor.execute("SELECT job_id, job_name, role_id, creator_id, job_type, jobboard_channel FROM jobs WHERE job_name = %s", (job_name,))
            self.connection.commit()
            return self.cursor.fetchone()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to select job '{job_name}': {e}")
            return []
            
    @check_connection
    def add_to_series(self, series_id, job_name):
        try:
            query = """
            INSERT INTO seriesjobs (series_id, job_id)
            SELECT %s, j.job_id
            FROM Jobs j
            WHERE j.job_name = %s
            ON CONFLICT DO NOTHING
            RETURNING series_job_id;
            """

            self.cursor.execute(query, (series_id, job_name))
            self.connection.commit()

            series_jobs_id = self.cursor.fetchone()

            if series_jobs_id:
                return series_jobs_id[0]
            else:
                return None
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to attach job '{job_name}' to series ID '{series_id}': {e}")
            return None

    @check_connection
    def remove_from_series(self, series_id, job_name):
        try:
            query = """
            DELETE FROM seriesjobs
            WHERE series_id = %s
            AND job_id = (
                SELECT job_id FROM Jobs WHERE job_name = %s
            )
            RETURNING series_job_id;
            """

            self.cursor.execute(query, (series_id, job_name))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to remove job '{job_name}' from series ID '{series_id}': {e}")
            return None

    @check_connection
    def get_unadded_all(self, series_name):
        try:
            query = """
            SELECT j.job_id, j.job_name, j.role_id, j.creator_id, j.job_type
            FROM Jobs j
            LEFT JOIN SeriesJobs sj ON j.job_id = sj.job_id AND sj.series_id = (
                SELECT s.series_id FROM Series s WHERE s.series_name = %s
            )
            WHERE sj.series_id IS NULL;
            """

            self.cursor.execute(query, (series_name,))
            self.connection.commit()
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to list unattached jobs for series '{series_name}': {e}")
            return None

    @check_connection
    def get_added_all(self, series_name):
        try:
            query = """
            SELECT sj.series_job_id, j.job_id, j.job_name, j.role_id, j.creator_id, j.job_type
            FROM Jobs j
            INNER JOIN SeriesJobs sj ON j.job_id = sj.job_id
            INNER JOIN Series s ON sj.series_id = s.series_id
            WHERE s.series_name = %s ORDER BY j.job_type ASC;
            """
            
            self.cursor.execute(query, (series_name,))
            self.connection.commit()
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to list attached jobs for series '{series_name}': {e}")
            return []

    @check_connection
    def get_added_by_type(self, series_name, job_type):
        try:
            query = """
                SELECT sj.series_job_id, j.job_id, j.job_name, j.role_id, j.creator_id, j.job_type
                FROM Jobs j
                JOIN SeriesJobs sj ON j.job_id = sj.job_id
                JOIN Series s ON sj.series_id = s.series_id
                WHERE s.series_name = %s AND j.job_type = %s;
            """
            self.cursor.execute(query, (series_name, job_type))
            self.connection.commit()
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get jobs of type '{job_type}' for series '{series_name}': {e}")
            return None


    @check_connection
    def get_added(self, series_name, job_name):
        try:
            query = """
            SELECT sj.series_job_id, j.job_id, j.job_name, j.role_id, j.creator_id, j.job_type
            FROM Jobs j
            INNER JOIN SeriesJobs sj ON j.job_id = sj.job_id
            INNER JOIN Series s ON sj.series_id = s.series_id
            WHERE s.series_name = %s AND j.job_name = %s;
            """
            
            self.cursor.execute(query, (series_name, job_name))
            self.connection.commit()
            return self.cursor.fetchone()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get attached jobs for series '{series_name}': {e}")
            return []

    @check_connection
    def get_added_by_id(self, series_job_id):
        try:
            self.cursor.execute("SELECT sj.series_job_id, j.job_id, j.job_name, j.role_id, j.creator_id, j.job_type FROM seriesjobs sj INNER JOIN jobs j ON j.job_id = sj.job_id WHERE sj.series_job_id = %s", (series_job_id,))
            self.connection.commit()
            return self.cursor.fetchone()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get series job '{series_job_id}': {e}")
            return []

    @check_connection
    def get_by_roles(self, roles):
        try:
            roles = list(set(roles))
            if not roles:
                return []

            self.cursor.execute("SELECT DISTINCT job_name FROM Jobs WHERE role_id = ANY(%s);", (roles,))
            self.connection.commit()

            jobs = self.cursor.fetchall()

            return [job.job_name for job in jobs]
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get qualified jobs: {e}")
            return []

    @check_connection
    def list_series_jobs(self, series_name):
        try:
            query = """
            SELECT sj.series_job_id, j.job_name, j.role_id, j.creator_id
            FROM Series s
            JOIN SeriesJobs sj ON s.series_id = sj.series_id
            JOIN Jobs j ON sj.job_id = j.job_id
            WHERE s.series_name = %s;
            """

            self.cursor.execute(query, (series_name,))
            self.connection.commit()
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to list attached jobs for series '{series_name}': {e}")
            return None

    @check_connection
    def set_jobboard(self, job_name, channel_id):
        try:
            self.cursor.execute("UPDATE jobs SET jobboard_channel = %s WHERE job_name = %s", (channel_id, job_name))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to set jobboard channel for job '{job_name}': {e}")
            return None