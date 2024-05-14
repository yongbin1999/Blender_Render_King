# app.py

from flask import Flask, request, redirect, url_for, render_template, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import logging
import os
import json
import subprocess
from datetime import datetime
import urllib.parse
import socket
import sys
import webbrowser
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import random
import threading
import tkinter as tk
from tkinter import filedialog, simpledialog


def get_lan_ip():
    """获取局域网IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))  # 这不会实际地发送数据
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config['UPLOAD_FOLDER'] = 'uploads'  # 设置上传文件夹

# 获取当前脚本所在的绝对路径和配置文件
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')


# 获取输出文件夹
def get_output_path():
    """
    从配置文件中获取输出目录。如果指定的输出目录有效，则使用该目录；
    否则，默认使用脚本同级目录下的 'Output' 目录。
    """
    default_output_path = os.path.join(BASE_DIR, 'Output')  # 默认输出目录
    if os.path.exists(CONFIG_FILE):  # 检查配置文件是否存在
        with open(CONFIG_FILE, 'r', encoding='utf-8') as config_file:
            config = json.load(config_file)
            output_path = config.get(
                'output_path', default_output_path)  # 尝试获取配置的输出目录
            # 检查配置的输出目录是否存在且可写
            if os.path.exists(output_path) and os.access(output_path, os.W_OK):
                return output_path  # 返回配置的输出目录
            else:
                print(f"配置的输出目录 {output_path} 无效，使用默认输出目录。")
    return default_output_path  # 如果配置文件不存在或配置的目录无效，返回默认输出目录


# 使用 get_output_path 函数来定义 OUTPUT_FOLDER
OUTPUT_FOLDER = get_output_path()
os.makedirs(OUTPUT_FOLDER, exist_ok=True)  # 确保输出目录存在

# 允许上传的文件类型
ALLOWED_EXTENSIONS = {'blend'}


def allowed_file(filename):
    """检查文件类型是否被允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_blender_exe_path():
    """获取Blender的执行路径"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as config_file:
            config = json.load(config_file)
            return config.get('blender_exe')
    return None  # 如果找不到配置，则返回None，后续可以根据这个做处理


@app.route('/')
def index():
    """渲染主页"""
    return render_template('index.html')

# 辅助函数：确保文件名安全，并生成保存路径


def save_file(file):
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)  # 确保目录存在
    file.save(file_path)
    return filename  # 返回安全的文件名


@app.route('/upload', methods=['POST'])
def upload_file():
    # 初始化渲染类型和子目录名为空字符串
    render_type = request.form.get('render_type')
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    subfolder_name = ""

    # 处理.blend文件（优先处理以保证可以创建基于此文件名的目录）
    file = request.files.get('file')
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        subfolder_name = f"{os.path.splitext(filename)[0]}_{
            timestamp}"  # 创建子目录名
        uploads_path = os.path.join(
            app.config['UPLOAD_FOLDER'], subfolder_name, filename)
        os.makedirs(os.path.dirname(uploads_path), exist_ok=True)
        file.save(uploads_path)
        blend_path = uploads_path
    else:
        return jsonify({'error': '上传文件类型错误或缺失 .blend 文件'}), 400

    # 创建输出目录
    output_path = os.path.join(OUTPUT_FOLDER, subfolder_name)
    os.makedirs(output_path, exist_ok=True)

    # 处理附加文件
    additional_files = request.files.getlist('file[]')
    for add_file in additional_files:
        if add_file and add_file.filename:
            save_path = os.path.join(
                app.config['UPLOAD_FOLDER'], subfolder_name, secure_filename(add_file.filename))
            os.makedirs(os.path.dirname(save_path), exist_ok=True)  # 确保目录存在
            add_file.save(save_path)

    # 处理文件夹中的文件
    folder_files = request.files.getlist('folder')
    for folder_file in folder_files:
        if folder_file and folder_file.filename:
            relative_path = secure_filename(folder_file.filename)
            # 这里将文件保存到与 .blend 文件相同的子目录下
            save_path = os.path.join(
                app.config['UPLOAD_FOLDER'], subfolder_name, relative_path)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)  # 确保目录存在
            folder_file.save(save_path)

    # 调用渲染函数（此处省略了渲染函数的代码，调用逻辑保持不变）
    render_blend_file(blend_path, output_path, render_type)

    # 读取渲染完成后的文件路径
    output_info_path = os.path.join(BASE_DIR, 'output_info.txt')
    try:
        with open(output_info_path, 'r', encoding='utf-8') as f:
            final_rendered_path = f.read().strip()  # 读取实际的渲染输出路径
        os.remove(output_info_path)  # 删除output_info.txt文件，因为它已经不再需要了
    except Exception as e:
        logging.error(f"读取或删除output_info.txt失败: {e}")
        return jsonify({'error': '获取渲染文件失败'}), 500
    # 返回成功消息
    return jsonify({'filename': filename, 'status': '渲染已完成', 'url': final_rendered_path})


@app.route('/files/<path:filename>')
def uploaded_file(filename):
    """发送已上传的文件"""
    return send_from_directory(OUTPUT_FOLDER, filename)


def render_blend_file(blend_path, output_path, render_type):
    """调用外部程序进行渲染"""
    try:
        blend_path = blend_path.replace('/', '\\\\')
        blender_exe_path = get_blender_exe_path()
        if blender_exe_path:
            render_command = [
                blender_exe_path,
                '--background',
                '--disable-abort-handler',
                '--disable-crash-handler',
                # '--debug-all',
                '--python-use-system-env',
                '--python', 'render_script.py',
                # '--python', '_internal/render_script.py',
                '--',
                blend_path,
                output_path,
                render_type
            ]
            try:
                subprocess.run(render_command)
            except subprocess.CalledProcessError as e:
                logging.error(f"Blender 命令执行失败: {e}")
        else:
            logging.error("没有找到可执行的Blender路径。")
    except Exception as e:
        logging.error(f"渲染过程中发生错误: {e}")


class FileMonitorHandler(FileSystemEventHandler):
    def __init__(self, folder_path, render_type, output_base_path):
        self.folder_path = folder_path
        self.render_type = render_type
        self.output_base_path = output_base_path
        self.recent_events = {}

    def on_created(self, event):
        if not event.is_directory and allowed_file(event.src_path):
            event_time = time.time()
            # 检查该文件是否最近已处理
            if self.should_process(event.src_path, event_time):
                print(f'检测到新文件: {event.src_path}')
                # 启动新线程以等待文件稳定
                threading.Thread(target=self.deferred_process,
                                 args=(event.src_path, event_time)).start()

    def should_process(self, src_path, current_time, wait_time=2):
        """
        检查文件是否在wait_time时间内被重复触发。
        如果是新文件或距上次触发时间超过wait_time，则返回True。
        """
        last_event_time = self.recent_events.get(src_path, 0)
        if current_time - last_event_time > wait_time:
            self.recent_events[src_path] = current_time
            return True
        return False

    def deferred_process(self, src_path, event_time, stabilization_time=3):
        """
        等待文件稳定，然后进行处理。
        """
        # 延迟等待以确保文件稳定
        time.sleep(stabilization_time)
        # 再次检查事件时间戳，以确保在这段等待时间内没有新的事件
        if self.recent_events.get(src_path) == event_time:
            print(f'文件 {src_path} 准备渲染...')
            self.process_blend_file(src_path)

    def wait_for_file_transfer_to_complete(self, file_path, wait_interval=5, retries=5):
        """等待文件无变化"""
        previous_size = -1
        current_size = os.path.getsize(file_path)
        attempts = 0
        while previous_size != current_size and attempts < retries:
            previous_size = current_size
            time.sleep(wait_interval)
            current_size = os.path.getsize(file_path)
            attempts += 1
        return previous_size == current_size

    def process_blend_file(self, file_path):
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        blend_name = os.path.splitext(os.path.basename(file_path))[0]
        subfolder_name = f"{blend_name}_{timestamp}"

        blend_dir = os.path.dirname(file_path)

        # 路径增加，用于检查或标记渲染信息的txt文件
        render_info_file_path = os.path.join(
            blend_dir, blend_name + "_render_info.txt")

        # 随机等待0到2秒
        time.sleep(random.uniform(0, 2))

        # 检查是否已存在渲染信息文件
        if os.path.exists(render_info_file_path):
            print(f"已存在其他程序渲染，跳过渲染: {blend_name}")
            return

        # 创建渲染信息文件以防止重复渲染
        self.create_or_touch_file(render_info_file_path)

        # 根据配置设定输出路径
        if self.output_base_path:
            output_path = os.path.join(self.output_base_path, subfolder_name)
        else:
            output_path = os.path.join(blend_dir, subfolder_name)

        os.makedirs(output_path, exist_ok=True)

        # 调用渲染，传递到外部渲染函数
        render_blend_file(file_path, output_path, self.render_type)

        # 渲染完成后，删除渲染信息文件
        try:
            os.remove(render_info_file_path)
        except OSError as e:
            print(f"无法删除渲染信息文件 {render_info_file_path}: {e.strerror}")

        # 读取渲染完成后删除output_info.txt
        output_info_path = os.path.join(BASE_DIR, 'output_info.txt')
        os.remove(output_info_path)

    def create_or_touch_file(self, file_path):
        """创建或更新文件的时间戳"""
        with open(file_path, 'a', encoding='utf-8'):
            os.utime(file_path, None)  # 更新文件时间，如果文件不存在则创建


# 定义全局变量以存储配置参数
global_config = {}

def read_config():
    ''' 读取配置文件 '''
    global global_config
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as config_file:
            global_config = json.load(config_file)
    else:
        global_config = {}
        with open(CONFIG_FILE, 'w', encoding='utf-8') as config_file:
            json.dump(global_config, config_file)


def save_config():
    with open(CONFIG_FILE, 'w', encoding='utf-8') as config_file:
        json.dump(global_config, config_file, ensure_ascii=False, indent=4)


def edit_config():
    ''' 修改配置，并为特定项添加文件和目录选择器 '''
    root = tk.Tk()
    root.title("配置编辑器")

    def save_and_close():
        ''' 保存并关闭窗口 '''
        save_config()
        root.destroy()

    def update_value(var, ent):
        global_config[var] = ent.get()

    def browse_file(var, entry):
        filepath = filedialog.askopenfilename()
        if filepath:
            global_config[var] = filepath
            entry.delete(0, tk.END)
            entry.insert(0, filepath)

    def browse_folder(var, entry):
        folderpath = filedialog.askdirectory()
        if folderpath:
            global_config[var] = folderpath
            entry.delete(0, tk.END)
            entry.insert(0, folderpath)

    for key, value in global_config.items():
        frame = tk.Frame(root)
        frame.pack(fill='x', padx=10, pady=5)

        tk.Label(frame, text=key).pack(side='left')
        entry = tk.Entry(frame, width=50)
        entry.insert(0, str(value))
        entry.pack(side='left', expand=True, fill='x')

        if key in ('blender_exe', 'Animation_watch_folder', 'Animation_watch_output_path', 'Image_watch_folder', 'Image_watch_output_path', 'output_path'):
            if key == 'blender_exe':
                def action(var=key, ent=entry): return browse_file(var, ent)
            else:
                def action(var=key, ent=entry): return browse_folder(var, ent)

            browse_btn = tk.Button(frame, text='Path', command=action)
            browse_btn.pack(side='left', padx=5)
        else:
            entry.bind('<KeyRelease>', lambda event, var=key,
                       ent=entry: update_value(var, ent))

    save_btn = tk.Button(root, text="保存", command=save_and_close)
    save_btn.pack(pady=5)

    root.mainloop()


if __name__ == '__main__':

    read_config()  # 加载配置
    edit_config()  # 允许用户编辑配置

    with open(CONFIG_FILE, 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)

    animation_folder = config.get("Animation_watch_folder", "")
    image_folder = config.get("Image_watch_folder", "")
    # 获取动画和图像监视渲染的输出路径配置
    animation_output_path = config.get("Animation_watch_output_path", "")
    image_output_path = config.get("Image_watch_output_path", "")

    if animation_folder:
        observer = Observer()
        observer.schedule(FileMonitorHandler(animation_folder, "animation", animation_output_path),
                          animation_folder, recursive=True)
        observer.start()

    if image_folder:
        observer_image = Observer()
        observer_image.schedule(FileMonitorHandler(image_folder, "image", image_output_path),
                                image_folder, recursive=True)
        observer_image.start()

    logging.basicConfig(filename='app.log', level=logging.ERROR)
    lan_ip = get_lan_ip()
    port = config.get('web_port', 6618)
    print(f" * Running on http://{lan_ip}:{port}")
    webbrowser.open(f'http://{lan_ip}:{port}', new=2)
    app.run(host=lan_ip, port=port, debug=False)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()

        if 'observer_image' in locals():
            observer_image.stop()
            observer_image.join()
