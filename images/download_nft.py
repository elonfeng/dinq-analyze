from PIL import Image
import pillow_avif  # 需要安装 pillow-avif-plugin 来支持 AVIF
import os

def convert_avif_to_jpg(input_path, output_path=None):
    """
    将AVIF图像转换为JPG格式
    
    参数:
        input_path: AVIF文件的路径
        output_path: 输出JPG文件的路径(可选)。如果不指定，将在相同目录下创建同名的.jpg文件
    """
    try:
        # 如果没有指定输出路径，则使用输入文件名(改扩展名为.jpg)
        if output_path is None:
            output_path = os.path.splitext(input_path)[0] + '.jpg'
            
        # 打开AVIF图像
        with Image.open(input_path) as img:
            # 转换为RGB模式(以防图像是RGBA)
            rgb_img = img.convert('RGB')
            # 保存为JPG
            rgb_img.save(output_path, 'JPEG', quality=95)
            print(f"转换成功: {output_path}")
            
    except Exception as e:
        print(f"转换过程中出现错误: {e}")

# 使用示例
if __name__ == "__main__":
    # 单个文件转换
    convert_avif_to_jpg("example.avif")
    
    # 或者转换指定目录下的所有AVIF文件
    """
    input_dir = "avif_files"
    for filename in os.listdir(input_dir):
        if filename.lower().endswith('.avif'):
            input_path = os.path.join(input_dir, filename)
            convert_avif_to_jpg(input_path)
    """