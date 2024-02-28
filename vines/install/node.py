import sys
import urllib.request
import zipfile
import os

from vines.install import comfy_path, js_path, custom_nodes_path, git_script_path, startup_script_path
from torchvision.datasets.utils import download_url
from urllib.parse import urlparse
import platform
import subprocess
import locale
from datetime import datetime

from vines.install.git_helper import GitProgress
import threading

comfy_ui_commit_datetime = datetime(1900, 1, 1, 0, 0, 0)
comfy_ui_required_commit_datetime = datetime(2024, 1, 24, 0, 0, 0)
comfy_ui_revision = "Unknown"


def handle_stream(stream, prefix):
    stream.reconfigure(encoding=locale.getpreferredencoding(), errors='replace')
    for msg in stream:
        if prefix == '[!]' and ('it/s]' in msg or 's/it]' in msg) and ('%|' in msg or 'it [' in msg):
            if msg.startswith('100%'):
                print('\r' + msg, end="", file=sys.stderr),
            else:
                print('\r' + msg[:-1], end="", file=sys.stderr),
        else:
            if prefix == '[!]':
                print(prefix, msg, end="", file=sys.stderr)
            else:
                print(prefix, msg, end="")


def run_script(cmd, cwd='.'):
    if len(cmd) > 0 and cmd[0].startswith("#"):
        print(f"[ComfyUI-Manager] Unexpected behavior: `{cmd}`")
        return 0

    process = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

    stdout_thread = threading.Thread(target=handle_stream, args=(process.stdout, ""))
    stderr_thread = threading.Thread(target=handle_stream, args=(process.stderr, "[!]"))

    stdout_thread.start()
    stderr_thread.start()

    stdout_thread.join()
    stderr_thread.join()

    return process.wait()


try:
    import git
except:
    my_path = os.path.dirname(__file__)
    requirements_path = os.path.join(my_path, "requirements.txt")

    print(f"## ComfyUI-Manager: installing dependencies")

    run_script([sys.executable, '-s', '-m', 'pip', 'install', '-r', requirements_path])

    try:
        import git
    except:
        print(f"## [ERROR] ComfyUI-Manager: Attempting to reinstall dependencies using an alternative method.")
        run_script([sys.executable, '-s', '-m', 'pip', 'install', '--user', '-r', requirements_path])

        try:
            import git
        except:
            print(
                f"## [ERROR] ComfyUI-Manager: Failed to install the GitPython package in the correct Python environment. Please install it manually in the appropriate environment. (You can seek help at https://app.element.io/#/room/%23comfyui_space%3Amatrix.org)")

    print(f"## ComfyUI-Manager: installing dependencies done.")

from git.remote import RemoteProgress


def unzip_install(files):
    temp_filename = 'manager-temp.zip'
    for url in files:
        if url.endswith("/"):
            url = url[:-1]
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}

            req = urllib.request.Request(url, headers=headers)
            response = urllib.request.urlopen(req)
            data = response.read()

            with open(temp_filename, 'wb') as f:
                f.write(data)

            with zipfile.ZipFile(temp_filename, 'r') as zip_ref:
                zip_ref.extractall(custom_nodes_path)

            os.remove(temp_filename)
        except Exception as e:
            print(f"Install(unzip) error: {url} / {e}", file=sys.stderr)
            return False

    print("Installation was successful.")
    return True


def copy_install(files, js_path_name=None):
    for url in files:
        if url.endswith("/"):
            url = url[:-1]
        try:
            if url.endswith(".py"):
                download_url(url, custom_nodes_path)
            else:
                path = os.path.join(js_path, js_path_name) if js_path_name is not None else js_path
                if not os.path.exists(path):
                    os.makedirs(path)
                download_url(url, path)

        except Exception as e:
            print(f"Install(copy) error: {url} / {e}", file=sys.stderr)
            return False

    print("Installation was successful.")
    return True


def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def try_install_script(url, repo_path, install_cmd):
    if platform.system() == "Windows" and comfy_ui_commit_datetime.date() >= comfy_ui_required_commit_datetime.date():
        if not os.path.exists(startup_script_path):
            os.makedirs(startup_script_path)

        script_path = os.path.join(startup_script_path, "install-scripts.txt")
        with open(script_path, "a") as file:
            obj = [repo_path] + install_cmd
            file.write(f"{obj}\n")

        return True
    else:
        print(f"\n## ComfyUI-Manager: EXECUTE => {install_cmd}")
        code = run_script(install_cmd, cwd=repo_path)

        if platform.system() == "Windows":
            try:
                if comfy_ui_commit_datetime.date() < comfy_ui_required_commit_datetime.date():
                    print("\n\n###################################################################")
                    print(
                        f"[WARN] ComfyUI-Manager: Your ComfyUI version ({comfy_ui_revision})[{comfy_ui_commit_datetime.date()}] is too old. Please update to the latest version.")
                    print(
                        f"[WARN] The extension installation feature may not work properly in the current installed ComfyUI version on Windows environment.")
                    print("###################################################################\n\n")
            except:
                pass

        if code != 0:
            if url is None:
                url = os.path.dirname(repo_path)
            print(f"install script failed: {url}")
            return False


def execute_install_script(url, repo_path, lazy_mode=False):
    install_script_path = os.path.join(repo_path, "install.py")
    requirements_path = os.path.join(repo_path, "requirements.txt")

    if lazy_mode:
        install_cmd = ["#LAZY-INSTALL-SCRIPT", sys.executable]
        try_install_script(url, repo_path, install_cmd)
    else:
        if os.path.exists(requirements_path):
            print("Install: pip packages")
            with open(requirements_path, "r") as requirements_file:
                for line in requirements_file:
                    package_name = line.strip()
                    if package_name:
                        install_cmd = [sys.executable, "-m", "pip", "install", package_name]
                        if package_name.strip() != "":
                            try_install_script(url, repo_path, install_cmd)

        if os.path.exists(install_script_path):
            print(f"Install: install script")
            install_cmd = [sys.executable, "install.py"]
            try_install_script(url, repo_path, install_cmd)

    return True


def gitclone_install(files):
    print(f"install: {files}")
    for url in files:
        if not is_valid_url(url):
            print(f"Invalid git url: '{url}'")
            return False

        if url.endswith("/"):
            url = url[:-1]
        try:
            print(f"Download: git clone '{url}'")
            repo_name = os.path.splitext(os.path.basename(url))[0]
            repo_path = os.path.join(custom_nodes_path, repo_name)

            # Clone the repository from the remote URL
            if platform.system() == 'Windows':
                res = run_script([sys.executable, git_script_path, "--clone", custom_nodes_path, url])
                if res != 0:
                    return False
            else:
                repo = git.Repo.clone_from(url, repo_path, recursive=True, progress=GitProgress())
                repo.git.clear_cache()
                repo.close()

            if not execute_install_script(url, repo_path):
                return False

        except Exception as e:
            print(f"Install(git-clone) error: {url} / {e}", file=sys.stderr)
            return False

    print("Installation was successful.")
    return True


def install_custom_node(json_data):
    install_type = json_data['install_type']
    print(f"Install custom node '{json_data['title']}'")

    res = False

    if len(json_data['files']) == 0:
        raise Exception("files 为空")

    if install_type == "unzip":
        res = unzip_install(json_data['files'])

    if install_type == "copy":
        js_path_name = json_data['js_path'] if 'js_path' in json_data else '.'
        res = copy_install(json_data['files'], js_path_name)

    elif install_type == "git-clone":
        res = gitclone_install(json_data['files'])

    if 'pip' in json_data:
        for pname in json_data['pip']:
            install_cmd = [sys.executable, "-m", "pip", "install", pname]
            try_install_script(json_data['files'][0], ".", install_cmd)

    if res:
        print(f"After restarting ComfyUI, please refresh the browser.")
        return True

    raise Exception("安装失败")
