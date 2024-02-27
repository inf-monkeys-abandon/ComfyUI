import asyncio
import logging
import signal
from dotenv import load_dotenv

load_dotenv()

from bullmq import Worker
from bullmq.job import Job
import api
import config
import process_basic

server_running = True

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


def prerun():
    api.init_aws()

    # logging.info('sync controlnet from s3')
    # api.sync_controlnet_from_s3('/tmp/controlnet')
    # logging.info('sync controlnet from s3 done')

    # logging.info('sync webui buildin models from s3')
    # api.sync_webui_buildin_models_from_s3('./models')
    # logging.info('sync webui buildin models from s3 done')

    # api.ensure_huggingface()
    # api.ensure_annotator_models('/tmp/annotator_models')


async def process(job: Job, job_token):
    logging.info("job start: %s", job_token)

    data = job.data
    type = data.get('type')

    # api.ensure_webui()
    if type == 'process_basic':
        result = process_basic.process(job)
    else:
        raise Exception('不支持的任务类型')

    logging.info("job finished")
    return result


async def main():
    prerun()

    queue_name = "comfyui-infer"
    worker = Worker(queue_name, process, {"connection": config.REDIS_URL, "lockDuration": 1 * 60 * 60 * 1000})
    logging.info(f"Listening queue: {queue_name}")

    while server_running:
        await asyncio.sleep(1)

    await worker.close()


def sigint_handler(sig, frame):
    logging.info(f'Interrupted with signal {sig}')
    global server_running
    server_running = False


if __name__ == "__main__":
    # signal.signal(signal.SIGINT, sigint_handler)
    asyncio.run(main())
