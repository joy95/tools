from .celery_app import celery_app
import os
import uuid
import requests
from PIL import Image
import cv2
import numpy as np
from paddleocr import PaddleOCR, build_logger
from moviepy.editor import ImageSequenceClip, AudioFileClip, VideoFileClip, CompositeAudioClip
from gtts import gTTS
import shutil
from bs4 import BeautifulSoup

# 配置 logger，避免 PaddleOCR 打印过多日志
logger = build_logger(name='paddleocr', use_log_file=False)

# 初始化 PaddleOCR
ocr_model = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False, logger=logger)

MEDIA_DIR = "./media"

# 辅助函数：下载文件
def download_file(url: str, save_path: str) -> bool:
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except requests.exceptions.RequestException as e:
        celery_app.logger.error(f"下载文件失败 {url}: {e}")
        return False

# 辅助函数：解析链接并获取媒体内容 (抖音、小红书、视频号)
def parse_platform_link(url: str) -> dict:
    # TODO: 实现抖音、小红书、视频号的链接解析逻辑
    # 这部分是反爬重灾区，可能需要复杂的逻辑和持续维护
    # 返回格式: { "type": "image"/"video"/"text", "content": "url"/"text_content" }
    celery_app.logger.warning(f"链接解析功能尚未完全实现，正在处理模拟数据：{url}")
    
    # 模拟解析逻辑
    if "douyin.com" in url:
        # 模拟抖音视频解析，返回一个假视频URL
        return {"type": "video", "content": "https://xxx.com/mock_douyin_video.mp4", "text_content": "模拟抖音视频文案"}
    elif "xiaohongshu.com" in url:
        # 模拟小红书图文解析，返回一个假图片URL和文案
        return {"type": "image", "content": "https://xxx.com/mock_xiaohongshu_image.jpg", "text_content": "模拟小红书图文文案"}
    elif "channels.weixin.qq.com" in url:
        # 模拟视频号视频解析，返回一个假视频URL
        return {"type": "video", "content": "https://xxx.com/mock_channels_video.mp4", "text_content": "模拟视频号视频文案"}
    else:
        # 默认返回一个通用的假图片和文案
        return {"type": "image", "content": "https://via.placeholder.com/150", "text_content": "这是通过链接解析的模拟文案"}

# ==== Celery 任务定义 ====

@celery_app.task
def remove_watermark_task(input_source: str, file_extension: str = None, is_url: bool = False):
    task_id = remove_watermark_task.request.id
    output_file_name = f"watermark_removed_{task_id}.mp4" if file_extension == ".mp4" else f"watermark_removed_{task_id}.jpg"
    output_path = os.path.join(MEDIA_DIR, output_file_name)

    try:
        local_input_path = input_source
        if is_url:
            # 解析链接获取真实媒体URL和类型
            parsed_content = parse_platform_link(input_source)
            if not parsed_content or not parsed_content.get("content"):
                raise Exception(f"无法解析链接或获取媒体内容: {input_source}")
            
            media_url = parsed_content["content"]
            media_type = parsed_content["type"]
            
            file_extension = ".mp4" if media_type == "video" else ".jpg"
            local_input_path = os.path.join(MEDIA_DIR, f"downloaded_{task_id}{file_extension}")
            if not download_file(media_url, local_input_path):
                raise Exception(f"从URL下载媒体失败: {media_url}")

        # 根据文件类型进行去水印处理
        if file_extension == ".mp4":
            # 视频去水印 (简化处理，实际需要更复杂的算法)
            # TODO: 实现更复杂的视频去水印逻辑
            shutil.copy(local_input_path, output_path) # 模拟处理，直接复制
            celery_app.logger.info(f"视频去水印任务完成 (模拟): {output_path}")
        else: # 图片去水印
            # TODO: 实现更复杂的图片去水印逻辑
            img = cv2.imread(local_input_path)
            if img is None:
                raise Exception(f"无法读取图片: {local_input_path}")
            
            # 模拟简单的图片去水印 (例如，直接返回原图)
            cv2.imwrite(output_path, img)
            celery_app.logger.info(f"图片去水印任务完成 (模拟): {output_path}")
            
        return f"/media/{output_file_name}"
    except Exception as e:
        celery_app.logger.error(f"去水印任务失败 {task_id}: {e}", exc_info=True)
        raise
    finally:
        # 清理临时文件
        if os.path.exists(local_input_path) and input_source != local_input_path:
            os.remove(local_input_path)

@celery_app.task
def extract_text_task(input_source: str, is_url: bool = False):
    task_id = extract_text_task.request.id
    extracted_text = ""

    try:
        local_input_path = input_source
        if is_url:
            parsed_content = parse_platform_link(input_source)
            if not parsed_content:
                raise Exception(f"无法解析链接或获取内容: {input_source}")
            
            if parsed_content.get("type") == "text" and parsed_content.get("text_content"):
                # 如果链接直接解析出文案，则直接使用
                extracted_text = parsed_content["text_content"]
                celery_app.logger.info(f"从URL直接提取文案完成: {extracted_text[:50]}...")
                return extracted_text
            elif parsed_content.get("type") in ["image", "video"] and parsed_content.get("content"):
                media_url = parsed_content["content"]
                file_extension = ".jpg" if parsed_content["type"] == "image" else ".mp4"
                local_input_path = os.path.join(MEDIA_DIR, f"downloaded_{task_id}{file_extension}")
                if not download_file(media_url, local_input_path):
                    raise Exception(f"从URL下载媒体失败: {media_url}")
            else:
                raise Exception(f"无法从链接获取可提取文案的媒体内容: {input_source}")

        # 使用 PaddleOCR 提取文案 (如果不是从链接直接获取的文案)
        if not extracted_text:
            img = cv2.imread(local_input_path)
            if img is None:
                raise Exception(f"无法读取图片进行文案提取: {local_input_path}")
            
            result = ocr_model.ocr(img, cls=True)
            if result and result[0]:
                extracted_text = "\n".join([line[1][0] for line in result[0]])
            
            celery_app.logger.info(f"图片文案提取任务完成: {extracted_text[:50]}...")
            
        return extracted_text
    except Exception as e:
        celery_app.logger.error(f"文案提取任务失败 {task_id}: {e}", exc_info=True)
        raise
    finally:
        if os.path.exists(local_input_path) and input_source != local_input_path:
            os.remove(local_input_path)


@celery_app.task
def generate_video_task(image_urls: List[str], text: str, template_id: str = "default", audio_option: str = "default"):
    task_id = generate_video_task.request.id
    output_file_name = f"generated_video_{task_id}.mp4"
    output_path = os.path.join(MEDIA_DIR, output_file_name)
    temp_audio_path = os.path.join(MEDIA_DIR, f"temp_audio_{task_id}.mp3")
    temp_images_dir = os.path.join(MEDIA_DIR, f"temp_images_{task_id}")
    os.makedirs(temp_images_dir, exist_ok=True)

    try:
        # 1. 下载图片
        local_image_paths = []
        for i, img_url in enumerate(image_urls):
            img_path = os.path.join(temp_images_dir, f"image_{i}.jpg")
            if not download_file(img_url, img_path):
                raise Exception(f"下载图片失败: {img_url}")
            local_image_paths.append(img_path)
        
        # 2. 文本转语音
        tts = gTTS(text=text, lang='zh', slow=False)
        tts.save(temp_audio_path)
        audio_clip = AudioFileClip(temp_audio_path)

        # 3. 视频合成 (简化处理)
        # 假设每张图片展示2秒
        total_duration = len(local_image_paths) * 2
        if audio_clip.duration > total_duration:
            total_duration = audio_clip.duration # 如果语音更长，以语音时长为准
        
        # 创建图片序列剪辑
        image_clips = []
        for img_path in local_image_paths:
            img = Image.open(img_path)
            img_clip = ImageSequenceClip([np.array(img)], fps=1) # 简单序列，每帧1秒
            image_clips.append(img_clip.set_duration(total_duration / len(local_image_paths)))

        # 合并图片序列
        final_clip = ImageSequenceClip([cv2.imread(p) for p in local_image_paths], fps=1) # 简单将所有图片作为帧，每秒1帧
        final_clip = final_clip.set_duration(total_duration)

        # 添加音频
        final_clip = final_clip.set_audio(audio_clip.set_duration(final_clip.duration))
        
        # 写入视频文件
        final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac", fps=24)

        celery_app.logger.info(f"视频生成任务完成: {output_path}")
        return f"/media/{output_file_name}"
    except Exception as e:
        celery_app.logger.error(f"视频生成任务失败 {task_id}: {e}", exc_info=True)
        raise
    finally:
        # 清理临时文件
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
        if os.path.exists(temp_images_dir):
            shutil.rmtree(temp_images_dir)

