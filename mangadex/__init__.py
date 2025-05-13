import requests
import os
from typing import Optional

AUTH_URL = "https://auth.mangadex.org/realms/mangadex/protocol/openid-connect/token"
BASE_URL = "https://api.mangadex.org"

class MangaDexAPI:
    def __init__(self):
        self.session = requests.Session()
        self.client_id: Optional[str] = None
        self.client_secret: Optional[str] = None
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.uploader_uuid: Optional[str] = None

    def login(self, client_id: str, client_secret: str, username: str, password: str):
        request_body = {
            "grant_type": "password",
            "client_id": client_id,
            "client_secret": client_secret,
            "username": username,
            "password": password
        }

        response = requests.post(AUTH_URL, data=request_body)

        if response.status_code == 200:
            print(f"[MangaDex.API] Logged in as {os.getenv('MangaDexLogin')}")
            self.access_token = response.json()['access_token']
            self.refresh_token = response.json()['refresh_token']
            self.client_id = client_id
            self.client_secret = client_secret
            self._update_auth_header()

            response = self.me()
            self.uploader_uuid = response["id"]
        else:
            print(f"[MangaDex.API] Login request failed with status code {response.status_code}")
            print(response.text)
            return None
        
    def refresh(self):
        if not self.refresh_token:
            print("[MangaDex.API] Tried to refresh access token without refresh token")
            return None
        
        request_body = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token
        }

        response = request_body.post(AUTH_URL, data=request_body)
        if response.status_code == 200:
            self.access_token = response.json()['access_token']
            self.refresh_token = response.json()['refresh_token']
            self._update_auth_header()
        else:
            print(f"[MangaDex.API] Refresh request failed with status code {response.status_code}")
            print(response.text)
            return None
        
    def _update_auth_header(self):
        self.session.headers.update({
            "Authorization": f"Bearer {self.access_token}"
        })

    def _request(self, method: str, url: str, retry: bool = True, **kwargs):
        response = self.session.request(method, f"{BASE_URL}{url}", **kwargs)

        if response.status_code == 401 and retry and self.refresh_token:
            self.refresh()
            return self._request(method, url, retry=False, **kwargs)
        
        return response
    
    def me(self):
        response = self._request("GET", "/user/me")
        return response.json()["data"]
    
    def group_by_id(self, group_id: str):
        response = self._request("GET", f"/group/{group_id}")
        return response.json()["data"]
    
    def check_for_session(self):
        response = self._request("GET", "/upload")
        if response.ok:
            session_id = response.json()["data"]["id"]
            return session_id
        else:
            return None
        
    def abandon_session(self, session_id):
        response = self._request("DELETE", f"/upload/{session_id}")
        if not response.ok:
            print(f"[MangaDex.API] Failed to abandon session before uploading: {response.status_code}")
            return False

        return True
    
    def create_session(self, group_ids, series_id):
        response = self._request("POST", "/upload/begin", True, json={ "groups": group_ids, "manga": series_id })
        if response.ok:
            session_id = response.json()["data"]["id"]
            return session_id
        else:
            print(f"[MangaDex.API] Session could not be created. Status code {response.status_code}")
            return None
        
    def upload_chapter(self, session_id, volume_number, chapter_number, chapter_name, language, folder_path, batch_size = 5):
        page_map = []

        for filename in os.listdir(folder_path):
            if "." not in filename or filename.split(".")[-1].lower() not in ["jpg", "jpeg", "png", "gif"]:
                continue

            page_map.append({
                "filename": filename,
                "extension": filename.split(".")[-1].lower(),
                "path": os.path.join(folder_path, filename)
            })

        successful = []
        failed = []
        batches = [
            page_map[l : l + batch_size]
            for l in range(0, len(page_map), batch_size)
        ]

        for i in range(len(batches)):
            current_batch = batches[i]

            files = [
                (
                    f"file{count}",
                    (
                        image["filename"],
                        open(image["path"], "rb"),
                        "image/" + image["extension"],
                    ),
                )
                for count, image in enumerate(
                    current_batch, start=1
                )
            ]

            response = self._request("POST", f"/upload/{session_id}", True, files=files)
            response_json = response.json()

            if response.ok:
                data = response_json["data"]

                for session_file in data:
                    successful.append({
                        "id": session_file["id"],
                        "filename": session_file["attributes"]["originalFileName"]
                    })

                for image in current_batch:
                    if image["filename"] not in [
                        page["filename"]
                        for page in successful
                    ]:
                        failed.append(image)

                start = i * batch_size
                end = start + batch_size - 1

                print(
                    f"Batch {start}-{end}:",
                    "Successful:", len(data), "|",
                    "Failed:", len(current_batch) - len(data),
                )
            else:
                print("An error occured")
                print(response_json)

        successful.sort(key=lambda a: a["filename"])
        page_order = [page["id"] for page in successful]

        chapter_draft = {
            "volume": str(volume_number) if volume_number else None,
            "chapter": str(chapter_number),
            "translatedLanguage": language,
            "title": chapter_name
        }

        response = self._request("POST", f"/upload/{session_id}/commit", True, json={ "chapterDraft": chapter_draft, "pageOrder": page_order })
        if response.ok:
            return response.json()["data"]["id"]
        else:
            print("[MangaDex.API] Chapter could not be uploaded.")
            print(response.json())
            return None

                