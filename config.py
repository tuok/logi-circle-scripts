import json

def read_config(path):
    required_keys = [
        'media_directory',
        'logi_circle_username',
        'logi_circle_password',
        'email_server',
        'email_ssl_port',
        'email_username',
        'email_password',
        'email_sender',
        'email_recipient'
    ]
    
    config = None

    with open(path, 'r') as config_file:
        config = json.loads(config_file.read())

    for key in required_keys:
        if not key in config:
            raise RuntimeError(f'Config file does not contain required item "{key}"')

    return config


def write_config(config, path):
    with open(path, 'w') as config_file:
        config_file.write(json.dumps(config, indent=4))
