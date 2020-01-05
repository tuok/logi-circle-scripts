import argparse
import json
import shutil
import traceback
from email_sender import MailClient
from circle_client import CircleClient
from config import read_config, write_config

config_file_path = 'config.json'

parser = argparse.ArgumentParser(description='Fetch Logitech Circle 2 still images and videos from Logitech servers.')
parser.add_argument('--action', '-a', help='What script should do when running. Available values are: still|videos')
parser.add_argument('--config', '-c', help='Specify config file location. Default value is \'config.json\'')

args = parser.parse_args()

if not args.action or args.action not in ['still', 'videos']:
    parser.error('Argument --action is incorrectly specified.')

if args.config:
    config_file_path = parser.config

config = read_config(config_file_path)

mail_client = None

if config.get('email_server', None):
    mail_client = MailClient(
        config['email_server'],
        config['email_ssl_port'],
        config['email_username'],
        config['email_password'],
        config['email_sender']
    )

client = CircleClient(
    config['media_directory'],
    config['logi_circle_username'],
    config['logi_circle_password'],
    config['logi_circle_token'],
    config.get('cameras', {})
)

client_error = config.get('client_error', False)

if client_error:
    print(
        'Previous execution resulted in fatal error, will not continue. ' +
        f'Reset error from config file \'{config_file_path}\' by setting \'client_error\'' +
        ' to false and try to run script manually for debugging.'
    )
    exit(1)

for _ in range(2):
    try:
        if not client.cameras:
            raise Exception()

        for camera in client.cameras:
            if args.action == 'still':
                client.get_still_image(camera)
            elif args.action == 'videos':
                client.get_new_videos(camera)
        break
    except Exception as ex:
        try:
            token = client.authorize()
            cameras = client.find_cameras()
            config['logi_circle_token'] = token
            config['cameras'] = cameras
        except Exception as inner_ex:
            config['client_error'] = True
            if mail_client:
                mail_client.send_mail(config['email_recipient'], 'Logi Scripts Error', traceback.format_exc())
            break
        finally:
            write_config(config, config_file_path)

# Check for disk space
total, used, free = shutil.disk_usage('/')
total_gigs = total // (2**30)
free_gigs = free // (2**30)
used_gigs = used // (2**30)

if free_gigs < 500 and mail_client:
    mail_client.send_mail(
        config['email_recipient'],
        'Logi Scripts Warning - Disk space is getting low',
        f'Total: {total_gigs} GiB\nUsed: {used_gigs} GiB\nFree: {free_gigs} GiB'
    )