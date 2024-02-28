import logging
import os
import uuid

import websocket
from bullmq.job import Job
import api
import config
import json

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))


def open_websocket():
    server_address = '127.0.0.1:8188'
    client_id = str(uuid.uuid4())
    ws = websocket.WebSocket()
    ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
    return client_id, ws


def track_progress(ws, prompt, prompt_id):
    node_ids = list(prompt.keys())
    finished_nodes = []

    while True:
        out = ws.recv()
        if isinstance(out, str):
            print(f"receive message: {out}")
            message = json.loads(out)
            if message['type'] == 'progress':
                data = message['data']
                current_step = data['value']
                print('In K-Sampler -> Step: ', current_step, ' of: ', data['max'])
            if message['type'] == 'execution_cached':
                data = message['data']
                for itm in data['nodes']:
                    if itm not in finished_nodes:
                        finished_nodes.append(itm)
                        print('Progess: ', len(finished_nodes), '/', len(node_ids), ' Tasks done')
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] not in finished_nodes:
                    finished_nodes.append(data['node'])
                    print('Progess: ', len(finished_nodes), '/', len(node_ids), ' Tasks done')

                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break  # Execution is done
            # if message['type'] == 'status':
            #     queue_remaining = message.get('data', {}).get('status', {}).get('exec_info', {}).get('queue_remaining')
            #     if queue_remaining == 0:
            #         break
        else:
            continue
    return


def get_image_path(filename, subfolder):
    return os.path.join(ROOT_DIR, "output", subfolder, filename)


def get_images(prompt_id):
    output_images = []
    history = api.get_task(prompt_id)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        if 'images' in node_output:
            for image in node_output['images']:
                # if allow_preview and image['type'] == 'temp':
                #     preview_data = get_image(image['filename'], image['subfolder'], image['type'], server_address)
                #     output_data['image_data'] = preview_data
                if image['type'] == 'output':
                    image_path = get_image_path(image['filename'], image['subfolder'])
                    output_images.append(image_path)
    return output_images


def process_prompt(job: Job):
    data = job.data
    token = data.get('token')
    app_id = data.get('app_id')
    request = data.get('request')
    requirements = data.get('requirements', [])
    output_folder_tmp = request.get('outputFolder')
    print(f"Output Folder: {output_folder_tmp}")
    client_id, ws = open_websocket()

    # 创建一个临时目录，用于存放输出
    output_folder = os.path.dirname(os.path.join(ROOT_DIR, "output", output_folder_tmp))
    os.makedirs(output_folder, exist_ok=True)
    print(f"Create folder Folder if not exists {output_folder}")

    for item in requirements:
        file_path = os.path.join(ROOT_DIR, 'input', item.get('path'), item.get('filename'))
        if not os.path.exists(file_path):
            url = item.get('url')
            logging.info(f'Downloading {url} to {file_path}')
            api.download(url, file_path)

    # 发送请求
    logging.info('Sending request')
    request['client_id'] = client_id
    res = api.post_prompt(request)

    prompt_id = res.get("prompt_id")
    logging.info(f'Prompt ID: {prompt_id}')

    # 轮询结果
    # status = ""
    # timeout_time = time.time() + 60 * 5
    # while status != "success":
    #     res = api.get_task(prompt_id)
    #     if res:
    #         break
    #     if time.time() > timeout_time:
    #         raise Exception("运行 ComfyUI 超时")
    #     time.sleep(1)
    logging.info(f'Polling result of client: {client_id}, prompt_id: {prompt_id}')
    track_progress(ws=ws, prompt=request['prompt'], prompt_id=prompt_id)

    # 上传图片
    hrefs = []
    # 遍历 output 下的图片
    # file_exts = [
    #     'png',
    #     'jpeg',
    #     'jpg',
    #     'webp',
    #     'gif',
    #     'mp4',
    #     'mp3'
    # ]
    # for ext in file_exts:
    #     for file_path in pathlib.Path(output_folder).glob(f'*.{ext}'):

    generated_images = get_images(prompt_id=prompt_id)
    for image_path in generated_images:
        # 上传图片
        filename = image_path.split("/")[-1]
        key = f'artworks/{uuid.uuid1().hex}-{filename}'
        with open(image_path, 'rb') as file:
            file_content_as_bytes = file.read()
            api.upload_image_to_s3(config.S3_PUBLIC_BUCKET, key, file_content_as_bytes)
            href = f'{config.OSS_BASE_URL}/{key}'
            hrefs.append(href)
            logging.info(f'Uploaded {image_path} to {href}')

    logging.info('Image upload finished')

    # 汇报进度
    return {
        "token": token,
        "app_id": app_id,
        "hrefs": hrefs,
    }


def process_install_dependency(job: Job):
    type = job.data.get('type')
    dependency = job.data.get('data')
    print(f"Install Dependency: {type} {dependency}", )
    if type == 'MODEL':
        api.install_node(dependency)
    elif type == 'MODEL':
        api.install_model(dependency)

    return {"success": True}
