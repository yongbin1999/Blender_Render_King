# render_script.py

import bpy
import sys
import os

# 脚本所在的路径
script_dir = os.path.dirname(os.path.realpath(__file__))
internal_dir = os.path.join(script_dir, '_internal')

# 获取命令行参数
argv = sys.argv
argv = argv[argv.index("--") + 1:]  # 获取 "--" 后的所有参数

blend_file = argv[0]  # .blend 文件路径
output_path = argv[1]  # 输出文件夹路径
render_type = argv[2]  # 渲染类型：'image' 或 'animation'

# 确保输出路径是绝对路径
output_path = os.path.abspath(output_path)

# 加载 .blend 文件
bpy.ops.wm.open_mainfile(filepath=blend_file)

# 设置输出路径
if render_type == 'animation':
    bpy.context.scene.render.filepath = os.path.join(
        output_path, '')
else:
    bpy.context.scene.render.filepath = os.path.join(output_path, '')  # 单帧图像

# 用于合成节点的输出路径设置
for scene in bpy.data.scenes:
    if scene.node_tree:
        for node in scene.node_tree.nodes:
            if node.type == 'OUTPUT_FILE':
                node.base_path = os.path.join(output_path, 'composite_output/')

# 尝试渲染并捕获异常
try:
    if render_type == "image":
        bpy.ops.render.render(write_still=True)
    elif render_type == "animation":
        bpy.ops.render.render(animation=True)
except Exception as e:
    print("渲染过程中出现错误:", e)
    # 这里可以记录错误，或决定是否继续执行后续渲染流程

# 渲染完成后，将渲染完成的文件路径写入到一个文本文件中
if os.path.exists(internal_dir):
    output_info_path = os.path.join(internal_dir, 'output_info.txt')
else:
    output_info_path = os.path.join(script_dir, 'output_info.txt')

with open(output_info_path, 'w', encoding='utf-8') as f:
    f.write(bpy.context.scene.render.filepath)
print('渲染完成，输出保存到：', bpy.context.scene.render.filepath)
