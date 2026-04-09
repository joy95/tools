<template>
	<view class="container">
		<u-navbar title="图文生成视频" fixed placeholder autoBack></u-navbar>

		<view class="section">
			<u-text text="选择图片 (最多9张)" size="16" bold margin="0 0 20rpx 0"></u-text>
			<u-upload
				:fileList="fileList"
				@afterRead="afterRead"
				@delete="deletePic"
				name="videoImages"
				multiple
				:maxCount="9"
				:previewFullImage="true"
				width="150"
				height="150"
				:action="uploadAction"
			></u-upload>
		</view>

		<u-gap height="20" bgColor="#f3f4f6"></u-gap>

		<view class="section">
			<u-text text="输入视频文案" size="16" bold margin="0 0 20rpx 0"></u-text>
			<u--textarea v-model="videoText" placeholder="请输入视频文案" border="none" height="150"></u--textarea>
		</view>

		<u-gap height="20" bgColor="#f3f4f6"></u-gap>

		<view class="section">
			<u-button type="primary" :disabled="fileList.length === 0 || !videoText" @click="generateVideo" :loading="processing" text="生成视频"></u-button>
		</view>

		<u-gap height="20" bgColor="#f3f4f6"></u-gap>

		<view class="result-section" v-if="resultUrl">
			<u-text text="生成结果" size="16" bold margin="20rpx 0"></u-text>
			<video :src="resultUrl" controls style="width: 100%; height: 200px;"></video>
			<view class="action-buttons">
				<u-button type="info" @click="downloadResult" text="下载"></u-button>
				<u-button type="warning" @click="shareResult" text="分享"></u-button>
			</view>
		</view>

	</view>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { onLoad } from '@dcloudio/uni-app';
import { Utoast } from 'uview-plus'; // 导入 UToast
import { request, uploadFile, downloadFile } from '../../utils/request'; // 导入封装的请求方法

const fileList = ref([]);
const videoText = ref('');
const processing = ref(false);
const resultUrl = ref('');

// 后端上传接口地址 (待定)
const uploadAction = ref('/api/video/upload-images'); // 使用相对路径
const generateAction = ref('/api/video/generate'); // 使用相对路径

onLoad(() => {
  console.log('图文生成视频页加载');
});

const afterRead = async (event) => {
  // 当设置 multiple 为 true 时，FileUpload 会存在多个文件
  fileList.value.push(...event.file.map(item => ({ ...item, status: 'success', message: '上传成功' })));
};

const deletePic = (event) => {
  fileList.value.splice(event.index, 1);
};

const generateVideo = async () => {
  if (fileList.value.length === 0 || !videoText.value) {
    Utoast.show({
      type: 'error',
      message: '请选择图片并输入文案',
    });
    return;
  }
  processing.value = true;
  resultUrl.value = ''; // 清空结果

  try {
    // 1. 先上传图片
    const uploadTasks = fileList.value.map(file => {
      return uploadFile<{ url: string }>({ // 使用封装的uploadFile
        url: uploadAction.value, // 上传图片的后端接口
        filePath: file.url,
        name: 'file',
      });
    });

    const uploadResults = await Promise.all(uploadTasks);

    const imageUrls = uploadResults.map(res => {
      if (res && res.url) {
        return res.url;
      } else {
        throw new Error('图片上传失败');
      }
    });

    // 2. 调用视频生成接口
    const res = await request<{ taskId: string }>({ // 使用封装的request
      url: generateAction.value,
      method: 'POST',
      data: {
        images: imageUrls,
        text: videoText.value,
        // templateId: 'default', // 可选：模板ID
        // audioOption: 'default', // 可选：配音选项
      },
    });

    if (res && res.taskId) {
      const taskId = res.taskId;
      Utoast.show({
        type: 'success',
        message: '视频生成任务已提交，请稍候',
      });
      // TODO: 轮询任务状态或通过WebSocket接收推送
      // 这里简化处理，直接等待一段时间后假设任务完成，实际应轮询状态接口
      await new Promise(resolve => setTimeout(resolve, 5000)); // 模拟等待5秒

      const statusRes = await request<{ status: string, url?: string }>({ // 使用封装的request
        url: `/api/video/status/${taskId}`,
        method: 'GET',
      });

      if (statusRes && statusRes.status === 'SUCCESS' && statusRes.url) {
        resultUrl.value = statusRes.url;
        Utoast.show({
          type: 'success',
          message: '视频生成成功',
        });
      } else {
        Utoast.show({
          type: 'error',
          message: '视频生成失败或任务未完成',
        });
      }

    } else {
      Utoast.show({
        type: 'error',
        message: '视频生成失败，请稍后再试',
      });
    }
  } catch (error) {
    Utoast.show({
      type: 'error',
      message: '请求失败' + error,
    });
  } finally {
    processing.value = false;
  }
};

// 下载结果文件
const downloadResult = async () => {
  if (!resultUrl.value) return;
  try {
    const tempFilePath = await downloadFile(resultUrl.value); // 使用封装的downloadFile
    uni.saveVideoToPhotosAlbum({
      filePath: tempFilePath,
      success: () => {
        Utoast.show({
          type: 'success',
          message: '已保存到相册',
        });
      },
      fail: () => {
        Utoast.show({
          type: 'error',
          message: '保存失败',
        });
      },
    });
  } catch (error) {
    Utoast.show({
      type: 'error',
      message: '下载失败' + error,
    });
  }
};

// 分享结果文件
const shareResult = () => {
  if (!resultUrl.value) return;
  uni.share({
    provider: 'weixin',
    type: 5, // 5:视频
    videoUrl: resultUrl.value,
    success: (res) => {
      Utoast.show({
        type: 'success',
        message: '分享成功',
      });
    },
    fail: (res) => {
      Utoast.show({
        type: 'error',
        message: '分享失败' + res.errMsg,
      });
    },
  });
};
</script>

<style lang="scss">
.container {
	padding: 20rpx;
}

.section {
	padding: 20rpx;
	background-color: #fff;
	border-radius: 8rpx;
	margin-bottom: 20rpx;
	.u-button {
		margin-top: 20rpx;
	}
}

.result-section {
	padding: 20rpx;
	background-color: #fff;
	border-radius: 8rpx;
	.action-buttons {
		display: flex;
		justify-content: space-around;
		margin-top: 20rpx;
		.u-button {
			width: 45%;
		}
	}
	video {
		width: 100%;
		height: 200px;
	}
}
</style>
