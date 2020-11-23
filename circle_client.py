from datetime import datetime
from dateutil import parser
import os
import requests
import shutil

from enum import Enum

class CircleClient:
    class Method(Enum):
        GET = 1
        POST = 2

    class MediaType(Enum):
        Images = 'images'
        Videos = 'videos'

    COOKIE_NAME = 'prod_session'
    BASE_URL = 'https://video.logi.com'
    AUTH_URL = '/api/accounts/authorization'
    ACCESSORIES_URL = '/api/accessories'

    def __init__(self, media_root, username, password, session, cameras, latest_activity):
        self.cameras = cameras
        self.media_root = media_root
        self.username = username
        self.password = password
        self.session = session
        self.latest_activity = latest_activity

        error = False

        if media_root is None or len(media_root) < 1 or (media_root[0] != "/" and media_root[1] != ":"):
            error = True

        if not error and not os.path.isdir(media_root):
            try:
                os.makedirs(media_root)
            except FileExistsError:
                pass
            except Exception as ex:
                raise RuntimeError(ex)

        if error:
            raise RuntimeError("Parameter media_root should be valid and accessible absolute path (/for/example/like/this).")


    def authorize(self):
        print(f'Authorizing {self.username}...')

        credentials = {
            'email': self.username,
            'password': self.password
        }

        response = self._base_request(
            method=self.Method.POST,
            url=self.AUTH_URL,
            data=credentials,
            return_response=True
        )
        
        if not self.COOKIE_NAME in response.cookies:
            raise RuntimeError('Authentication failed')

        self.session = response.cookies['prod_session']
        print('Authorizaton completed successfully.')

        return self.session


    def find_cameras(self):
        accessories = self._get_accessories()

        error = False

        try:
            if len(accessories) < 1:
                error = True
        except:
            error = True
        
        if error:
            raise RuntimeError('Did not find any cameras (possible error in fetching accessories).')

        print('Found following cameras:')

        for accessory in accessories:
            camera_name = accessory['configuration']['deviceName']
            camera_id = accessory['accessoryId']

            self.cameras[camera_name] = { 'id': camera_id, 'name': camera_name, 'node_url': 'https://' + accessory['nodeId'] }
            print(self.cameras[camera_name])
        
        return self.cameras
    

    def get_new_videos(self, camera_name):
        print(f'Preparing to download latest videos for camera {camera_name}...')

        activities = self._get_activities(camera_name)
        videos = []

        latest_activity = ''
        new_latest_activity = ''

        if camera_name in self.latest_activity:
            latest_activity = self.latest_activity[camera_name]

        for activity in activities:
            activity_id = activity['activityId']

            # Do not re-download already downloaded videos.
            if latest_activity >= activity_id:
                continue

            activity_time = parser.parse(activity_id).astimezone()
            activity_time_tokens = self._get_timestamp_tokens(activity_time)

            new_latest_activity = max(new_latest_activity, activity_id)

            video_candidate_path = self._get_media_path(self.MediaType.Videos, camera_name, activity_time_tokens)

            # If file doesn't exist, fetch it
            if not os.path.exists(video_candidate_path):
                print(f'Video {activity_id} for camera {camera_name} was not found from the path {video_candidate_path}, downloading it...')
                self._download_activity(camera_name, activity_id, video_candidate_path)
                videos.append(video_candidate_path)
            
            else:
                print(f'Video {activity_id} for camera {camera_name} was already found from {video_candidate_path}.')
                pass
        
        print(f'Successfully downloaded {len(videos)} new videos from camera {camera_name}:')

        if new_latest_activity == '':
            new_latest_activity = latest_activity

        return videos, new_latest_activity


    def get_still_image(self, camera_name):
        print(f'Download latest still for camera {camera_name}...')

        with self._node_request(
            method=self.Method.GET,
            camera_name=camera_name,
            url=f'{self.ACCESSORIES_URL}/{self.cameras[camera_name]["id"]}/image',
            return_response=True,
            stream=True
        ) as response:
            if response.status_code != 200:
                raise RuntimeError('Get image request did not result in status code 200')

            still_path = self._get_media_path(self.MediaType.Images, camera_name)

            with open(still_path, 'wb') as image_file:
                shutil.copyfileobj(response.raw, image_file)

            print(f'Still {still_path} downloaded successfully.')

            return still_path


    def _download_activity(self, camera_name, activity_id, video_path):
        with self._base_request(
            method=self.Method.GET,
            url=f'{self.ACCESSORIES_URL}/{self.cameras[camera_name]["id"]}/activities/{activity_id}/mp4',
            return_response=True,
            stream=True
        ) as response:
            if response.status_code != 200:
                raise RuntimeError('Get image request did not result in status code 200')

            with open(video_path, 'wb') as video_file:
                shutil.copyfileobj(response.raw, video_file)

            return video_path


    def _get_media_path(self, media_type, camera_name, timestamp_tokens=None):
        if timestamp_tokens is None:
            timestamp_tokens = self._get_timestamp_tokens()

        media_dir = self._generate_media_dir_name(media_type.value, camera_name, timestamp_tokens)
        self._create_dir(media_dir)
        y, mo, d, h, mi, s = timestamp_tokens
        extension = 'jpg' if media_type == self.MediaType.Images else 'mp4'

        return os.path.join(media_dir, f'{camera_name} {y}{mo}{d}-{h}{mi}{s}.{extension}')


    def _create_dir(self, directory):
        try:
            os.makedirs(directory)
        except FileExistsError:
            pass
        except Exception as ex:
            raise RuntimeError(ex)
    
    
    def _generate_media_dir_name(self, media_type, camera_name, timestamp_tokens): 
        y, mo, d, _, _, _ = timestamp_tokens
        return os.path.join(self.media_root, camera_name, media_type, y, mo, d)


    # Returns tuple "2019", "02", "30", "19", "13", "18" for timestamp 2019-02-30 19:13:18
    def _get_timestamp_tokens(self, timestamp=datetime.now()):
        y = str(timestamp.year).zfill(4)
        mo = str(timestamp.month).zfill(2)
        d = str(timestamp.day).zfill(2)
        h = str(timestamp.hour).zfill(2)
        mi = str(timestamp.minute).zfill(2)
        s = str(timestamp.second).zfill(2)

        return y, mo, d, h, mi, s

    
    def _get_accessories(self):
        print('Fetching camera information...')

        accessories = self._base_request(
            method=self.Method.GET,
            url=self.ACCESSORIES_URL
        )

        return accessories


    def _get_activities(self, camera_name):
        print('Fetching information about latest videos...')

        activities = self._base_request(
            method=self.Method.POST,
            url=f'{self.ACCESSORIES_URL}/{self.cameras[camera_name]["id"]}/activities',
            data={
                "operator": "<=",
                "limit": 100,
                "filter": "relevanceLevel = 0 OR relevanceLevel >= 1",
                "scanDirectionNewer": True
            }
        )

        activities_ret = activities['activities']

        print(f'Fetched info about {len(activities_ret)} latest videos.')

        return activities_ret


    def _base_request(self, method, url, data={}, return_response=False, stream=False):
        return self.__circle_request(method, self.BASE_URL + url, data, return_response, stream)


    def _node_request(self, method, camera_name, url, data={}, return_response=False, stream=False):
        return self.__circle_request(method, self.cameras[camera_name]['node_url'] + url, data, return_response, stream)


    def __circle_request(self, method, url, data, return_response, stream):
        response = None

        if method == self.Method.POST:
            response = requests.post(
                url=url,
                cookies={self.COOKIE_NAME: self.session},
                json=data,
                headers={
                    'Content-Type': 'application/json',
                    'Origin': 'https://circle.logi.com'
                },
                stream=stream
            )
        else:
            response = requests.get(
                url=url,
                cookies={self.COOKIE_NAME: self.session},
                headers={
                    'Origin': 'https://circle.logi.com'
                },
                stream=stream
            )
        
        if return_response:
            return response
        else:
            return response.json()
