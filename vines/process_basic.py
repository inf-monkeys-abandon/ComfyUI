import logging
import os
import time
import pathlib
import uuid

from bullmq.job import Job
import api
import config

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))


def process(job: Job):
    data = job.data
    token = data.get('token')
    app_id = data.get('app_id')
    request = data.get('request')
    requirements = data.get('requirements', [])
    output_folder = data.get('outputFolder', 'output')

    # 创建一个临时目录，用于存放输出
    os.makedirs(os.path.join(ROOT_DIR, output_folder), exist_ok=True)

    for item in requirements:
        file_path = os.path.join(ROOT_DIR, item.get('path'), item.get('filename'))
        if not os.path.exists(file_path):
            url = item.get('url')
            logging.info(f'Downloading {url} to {file_path}')
            api.download(url, file_path)

    # 发送请求
    logging.info('Sending request')
    res = api.post_prompt(request)

    prompt_id = res.get("prompt_id")
    logging.info(f'Prompt ID: {prompt_id}')

    # 轮询结果
    logging.info('Polling result')
    status = ""
    timeout_time = time.time() + 60 * 5
    while status != "success":
        res = api.get_task(prompt_id)
        status = res.get(prompt_id, {}).get("status", {}).get("status_str")
        if status == "error":
            logging.error(res)
            raise Exception("Prompt failed")
        if time.time() > timeout_time:
            raise Exception("Prompt timeout")

    # 上传图片
    hrefs = []
    # 遍历 output 下的图片
    for image_path in pathlib.Path(output_folder).glob('*.png'):
        # 上传图片
        key = f'artworks/{uuid.uuid1().hex}-{image_path.name}'
        api.upload_image_to_s3(config.S3_PUBLIC_BUCKET, key, image_path.read_bytes())
        href = f'{config.OSS_BASE_URL}/{key}'
        hrefs.append(href)
        logging.info(f'Image uploaded: {href}')

    logging.info('Image upload finished')

    # 汇报进度
    return {
        "token": token,
        "app_id": app_id,
        "hrefs": hrefs,
    }
