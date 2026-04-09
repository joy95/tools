<template>
	<view class="container">
		<u-navbar title="文案提取" fixed placeholder autoBack></u-navbar>

		<view class="input-section">
			<u-input
				v-model="link"
				placeholder="请粘贴抖音、小红书、视频号等平台的分享链接"
				clearable
				border="bottom"
				@focus="onInputFocus"
				@blur="onInputBlur"
			></u-input>
			<u-button type="primary" :disabled="!link" @click="processByLink" :loading="processing" text="链接解析提取文案"></u-button>
		</view>

		<u-gap height="20" bgColor="#f3f4f6"></u-gap>

		<view class="upload-section">
			<u-upload
				:fileList="fileList"
				@afterRead="afterRead"
				@delete="deletePic"
				name="textExtractFile"
				multiple
				:maxCount="1"
				:previewFullImage="true"
				width="150"
				height="150"
				:action="uploadAction"
				:customStyle="{ marginBottom: '20rpx' }"
			></u-upload>
			<u-button type="success" :disabled="fileList.length === 0" @click="processByUpload" :loading="processing" text="上传图片提取文案"></u-button>
		</view>

		<u-gap height="20" bgColor="#f3f4f6"></u-gap>

		<view class="result-section" v-if="extractedText">
			<u-text text="提取结果" size="16" bold margin="20rpx 0"></u-text>
			<u--textarea v-model="extractedText" placeholder="提取到的文案" border="none" height="150"></u--textarea>
			<view class="action-buttons">
				<u-button type="info" @click="copyText" text="复制文案"></u-button>
			</view>
		</view>
	</view>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { onLoad } from '@dcloudio/uni-app';
import { Utoast } from 'uview-plus'; // 导入 UToast
import { request, uploadFile } from '../../utils/request'; // 导入封装的请求方法

const link = ref('');
const fileList = ref([]);
const processing = ref(false);
const extractedText = ref('');

// 后端上传接口地址 (待定)
const uploadAction = ref('/api/text/upload'); // 使用相对路径

onLoad((options) => {
  if (options && options.type === 'link') {
    // 可以自动聚焦输入框或者给出提示
  }
});

const onInputFocus = () => {
  fileList.value = [];
};

const onInputBlur = () => {
};

const afterRead = async (event) => {
  fileList.value.push({ ...event.file[0], status: 'success', message: '上传成功' });
  link.value = ''; // 清空链接
};

const deletePic = (event) => {
  fileList.value.splice(event.index, 1);
};

// 通过链接解析提取文案
const processByLink = async () => {
  if (!link.value) {
    Utoast.show({
      type: 'error',
      message: '请输入链接',
    });
    return;
  }
  processing.value = true;
  extractedText.value = ''; // 清空结果
  try {
    // TODO: 调用后端链接解析文案提取API
    // 假设后端返回数据格式为 { text: 'xxx' }
    const res = await request<{ text: string }>({ // 使用封装的request
      url: '/api/text/extract',
      method: 'POST',
      data: { url: link.value },
    });

    if (res && res.text) {
      extractedText.value = res.text;
      Utoast.show({
        type: 'success',
        message: '文案提取成功',
      });
    } else {
      Utoast.show({
        type: 'error',
        message: '文案提取失败，请检查链接或稍后再试',
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

// 通过文件上传提取文案
const processByUpload = async () => {
  if (fileList.value.length === 0) {
    Utoast.show({
      type: 'error',
      message: '请选择图片',
    });
    return;
  }
  processing.value = true;
  extractedText.value = ''; // 清空结果
  try {
    // TODO: 调用后端文件上传文案提取API
    // 假设后端返回数据格式为 { text: 'xxx' }
    const res = await uploadFile<{ text: string }>({ // 使用封装的uploadFile
      url: uploadAction.value, // 后端上传接口地址
      filePath: fileList.value[0].url,
      name: 'textExtractFile',
      formData: {},
    });

    if (res && res.text) {
      extractedText.value = res.text;
      Utoast.show({
        type: 'success',
        message: '文案提取成功',
      });
    } else {
      Utoast.show({
        type: 'error',
        message: '文案提取失败，请稍后再试',
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

// 复制文案
const copyText = () => {
  if (!extractedText.value) return;
  uni.setClipboardData({
    data: extractedText.value,
    success: () => {
      Utoast.show({
        type: 'success',
        message: '复制成功',
      });
    },
    fail: () => {
      Utoast.show({
        type: 'error',
        message: '复制失败',
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
}
</style>
