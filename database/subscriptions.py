from utils.checks import check_connection

class Subscriptions:
    def __init__(self, connection, cursor):
        self.connection = connection
        self.cursor = cursor

    @check_connection
    def new(self, member_id, series_id):
        try:
            self.cursor.execute("INSERT INTO SeriesSubscriptions (member_id, series_id) VALUES (%s, %s) ON CONFLICT (member_id, series_id) DO NOTHING RETURNING subscription_id;", (member_id, series_id))
            self.connection.commit()

            subscription_id = self.cursor.fetchone()

            if subscription_id:
                return subscription_id[0]
            else:
                return None
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to add new series subscription: {e}")
            return None

    @check_connection
    def delete(self, member_id, series_id):
        try:
            self.cursor.execute("DELETE FROM SeriesSubscriptions WHERE member_id = %s AND series_id = %s", (member_id, series_id))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            return None

    @check_connection
    def delete_all(self, member_id):
        try:
            self.cursor.execute("DELETE FROM SeriesSubscriptions WHERE member_id = %s", (member_id,))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            return None

    @check_connection
    def get_all(self, member_id):
        try:
            query = """
            SELECT 
                ss.subscription_id,
                ss.subscribed_at,
                s.series_id,
                s.series_name
            FROM 
                SeriesSubscriptions ss
            JOIN 
                Series s ON ss.series_id = s.series_id
            JOIN 
                Members m ON ss.member_id = m.member_id
            WHERE 
                m.member_id = %s;
            """
            self.cursor.execute(query, (member_id,))
            self.connection.commit()
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get all subscriptions for member '{member_id}': {e}")
            return None

    @check_connection
    def is_subscribed(self, member_id, series_id):
        try:
            self.cursor.execute("SELECT * FROM SeriesSubscriptions WHERE member_id = %s AND series_id = %s", (member_id, series_id))
            self.connection.commit()
            if self.cursor.fetchone():
                return True
            return False
        except Exception as e:
            self.connection.rollback()
            return None