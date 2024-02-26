import json
import logging
import os
import subprocess
import sys
import time
import traceback

import boto3
import requests
from botocore.client import Config
import config

JSON_HEADERS = {'Content-type': 'application/json; charset=utf-8'}

proc = None
ckpt_dir = './ComfyUI/models/checkpoints'

s3 = boto3.client(
    "s3",
    endpoint_url=config.S3_ENDPOINT,
    aws_access_key_id=config.S3_ACCESS_KEY,
    aws_secret_access_key=config.S3_SECRET_KEY,
    region_name=config.S3_REGION,
    config=Config(s3={'addressing_style': 'virtual'})
)


def download(url, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    os.system(f'wget -q -O {file_path} "{url}"')
    return file_path


def init_aws():
    # init aws
    aws_credential_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.aws')
    os.makedirs(aws_credential_folder, exist_ok=True)
    with open(os.path.join(aws_credential_folder, 'credentials'), 'w') as f:
        f.write('''[default]
aws_access_key_id = {access_key}
aws_secret_access_key = {secret_key}
'''.format(access_key=config.S3_ACCESS_KEY, secret_key=config.S3_SECRET_KEY))

    with open(os.path.join(aws_credential_folder, 'config'), 'w') as f:
        f.write('''[default]
region = {region}
output = json
s3 =
  addressing_style = virtual
'''.format(region=config.S3_REGION))
    logging.info('AWS initialized')


def run_command(command, desc=None):
    if desc is not None:
        logging.info(f'{desc}')
    logging.info(f'{command}')

    return subprocess.Popen(command, stdout=sys.stdout,
                            stderr=sys.stderr, shell=True)


def raise_for_status(res, data=None):
    try:
        res.raise_for_status()
    except Exception as e:
        if data is not None:
            logging.info(f"data: {data}")
        raise Exception(*e.args, f"text: {res.text}")


def get_history():
    res = requests.get('http://localhost:8188/history', timeout=5)
    raise_for_status(res)
    return res.json()


def get_task(prompt_id):
    res = requests.get(f'http://localhost:8188/history/{prompt_id}', timeout=5)
    raise_for_status(res)
    return res.json()


def post_prompt(req):
    data = json.dumps(req).encode()
    res = requests.post('http://localhost:8188/prompt',
                        data=data, headers=JSON_HEADERS, timeout=5)
    raise_for_status(res, data)
    return res.json()


def upload_to_s3(bucket, key, file_path):
    s3.upload_file(file_path, bucket, key)


def upload_image_to_s3(bucket, key, image_bytes):
    s3.put_object(Bucket=bucket, Key=key, Body=image_bytes,
                  ContentType='image/png')


def download_from_s3(bucket, key, file_path):
    s3.download_file(bucket, key, file_path)


def download_from_s3_if_exists(bucket, key, file_path):
    try:
        s3.download_file(bucket, key, file_path)
    except Exception:
        logging.info(f'file not found: {bucket}/{key}')
        traceback.print_exc()
        pass


def exising_s3_file(bucket, key):
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def ensure_sd_model(model_name, model_path):
    if os.path.exists(model_path) is False:
        logging.info(f'Downloading model {model_path}')
        os.system(f'rm -rf {ckpt_dir}/*')

        if os.path.exists(model_path):
            logging.info(f'File {model_path} exists')
            return

        download_from_s3(
            config.S3_MODEL_BUCKET,
            'Stable-diffusion/' + model_name, model_path)


def ensure_webui():
    command = 'cd ComfyUI && python3 main.py'

    global proc
    if proc is None or proc.poll() is not None:
        # start webui with model path
        proc = run_command(command, 'Starting ComfyUI')
        # wait for webui to start
        while 1:
            time.sleep(2)
            if proc.poll() is not None:
                proc = None
                raise Exception('ComfyUI exited unexpectedly')
            try:
                get_history()
                logging.info('ComfyUI started')
                break
            except Exception:
                pass
