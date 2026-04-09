<template>
	<view class="container">
		<u-navbar title="去水印" fixed placeholder autoBack></u-navbar>

		<view class="input-section">
			<u-input
				v-model="link"
				placeholder="请粘贴抖音、小红书、视频号等平台的分享链接"
				clearable
				border="bottom"
				@focus="onInputFocus"
				@blur="onInputBlur"
			></u-input>
			<u-button type="primary" :disabled="!link" @click="processByLink" :loading="processing" text="链接解析去水印"></u-button>
		</view>

		<u-gap height="20" bgColor="#f3f4f6"></u-gap>

		<view class="upload-section">
			<u-upload
				:fileList="fileList"
				@afterRead="afterRead"
				@delete="deletePic"
				name="watermarkFile"
				multiple
				:maxCount="1"
				:previewFullImage="true"
				width="150"
				height="150"
				:action="uploadAction"
				:customStyle="{ marginBottom: '20rpx' }"
			></u-upload>
			<u-button type="success" :disabled="fileList.length === 0" @click="processByUpload" :loading="processing" text="上传文件去水印"></u-button>
		</view>

		<u-gap height="20" bgColor="#f3f4f6"></u-gap>

		<view class="result-section" v-if="resultUrl">
			<u-text text="处理结果" size="16" bold margin="20rpx 0"></u-text>
			<template v-if="isImageResult">
				<u--image :src="resultUrl" mode="aspectFit" width="100%" height="200px"></u--image>
			</template>
			<template v-else>
				<video :src="resultUrl" controls style="width: 100%; height: 200px;"></video>
			</template>
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
import { Utoast } from 'uview-plus'; // 导入 UToast 以便使用轻提示
import { request, uploadFile, downloadFile } from '../../utils/request'; // 导入封装的请求方法

const link = ref('');
const fileList = ref([]);
const processing = ref(false);
const resultUrl = ref('');
const isImageResult = ref(true); // 判断结果是图片还是视频

// 后端上传接口地址 (待定)
const uploadAction = ref('/api/watermark/upload'); // 使用相对路径，BASE_URL会在request中拼接

// 页面加载时根据参数判断是否为链接解析模式
onLoad((options) => {
  if (options && options.type === 'link') {
    // 可以自动聚焦输入框或者给出提示
  }
});

const onInputFocus = () => {
  // 输入框聚焦时的逻辑，例如清除文件列表
  fileList.value = [];
};

const onInputBlur = () => {
  // 输入框失焦时的逻辑
};

// 文件读取完成后的回调
const afterRead = async (event) => {
  // 当设置 multiple 为 true 时，FileUpload 会存在多个文件，这里只取第一个
  fileList.value.push({ ...event.file[0], status: 'success', message: '上传成功' });
  link.value = ''; // 清空链接
};

// 删除图片
const deletePic = (event) => {
  fileList.value.splice(event.index, 1);
};

// 通过链接解析去水印
const processByLink = async () => {
  if (!link.value) {
    Utoast.show({
      type: 'error',
      message: '请输入链接',
    });
    return;
  }
  processing.value = true;
  resultUrl.value = ''; // 清空结果
  try {
    // TODO: 调用后端链接解析去水印API
    // 假设后端返回数据格式为 { url: 'xxx', type: 'image/video' }
    const res = await request<{ url: string, type: 'image' | 'video' }>({ // 使用封装的request
      url: '/api/watermark/remove',
      method: 'POST',
      data: { url: link.value },
    });

    if (res && res.url) {
      resultUrl.value = res.url;
      isImageResult.value = res.type === 'image';
      Utoast.show({
        type: 'success',
        message: '去水印成功',
      });
    } else {
      Utoast.show({
        type: 'error',
        message: '去水印失败，请检查链接或稍后再试',
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

// 通过文件上传去水印
const processByUpload = async () => {
  if (fileList.value.length === 0) {
    Utoast.show({
      type: 'error',
      message: '请选择文件',
    });
    return;
  }
  processing.value = true;
  resultUrl.value = ''; // 清空结果
  try {
    // TODO: 调用后端文件上传去水印API
    // 假设后端返回数据格式为 { url: 'xxx', type: 'image/video' }
    const res = await uploadFile<{ url: string, type: 'image' | 'video' }>({ // 使用封装的uploadFile
      url: uploadAction.value, // 后端上传接口地址
      filePath: fileList.value[0].url,
      name: 'watermarkFile',
      formData: {},
    });

    if (res && res.url) {
      resultUrl.value = res.url;
      isImageResult.value = res.type === 'image';
      Utoast.show({
        type: 'success',
        message: '去水印成功',
      });
    } else {
      Utoast.show({
        type: 'error',
        message: '去水印失败，请稍后再试',
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
    if (isImageResult.value) {
      uni.saveImageToPhotosAlbum({
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
    } else {
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
    }
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
    type: isImageResult.value ? 2 : 5, // 2:图片, 5:视频
    imageUrl: isImageResult.value ? resultUrl.value : '',
    videoUrl: !isImageResult.value ? resultUrl.value : '',
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

.input-section,
.upload-section {
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
