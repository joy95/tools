<template>
	<view class="container">
		<u-navbar title="自媒体工具箱" fixed placeholder></u-navbar>

		<view class="feature-list">
			<u-grid :col="3" :border="false">
				<u-grid-item @click="goToFeature('watermark')">
					<u-icon name="photo" :size="40"></u-icon>
					<text class="grid-text">去水印</text>
				</u-grid-item>
				<u-grid-item @click="goToFeature('text-extract')">
					<u-icon name="file-text" :size="40"></u-icon>
					<text class="grid-text">文案提取</text>
				</u-grid-item>
				<u-grid-item @click="goToFeature('video-generate')">
					<u-icon name="play-circle" :size="40"></u-icon>
					<text class="grid-text">图文生成视频</text>
				</u-grid-item>
			</u-grid>
		</view>

		<u-gap height="20" bgColor="#f3f4f6"></u-gap>

		<view class="section-title">
			<u-text text="热门工具" size="16" bold margin="20rpx 0"></u-text>
		</view>
		<view class="popular-tools">
			<u-card title="链接解析去水印" subTitle="粘贴链接，轻松去水印" :showFoot="false">
				<view slot="body">
					<u-button type="primary" size="mini" @click="goToFeature('watermark', { type: 'link'})">立即使用</u-button>
				</view>
			</u-card>
			<u-card title="链接解析文案提取" subTitle="一键提取平台文案" :showFoot="false">
				<view slot="body">
					<u-button type="success" size="mini" @click="goToFeature('text-extract', { type: 'link'})">立即使用</u-button>
				</view>
			</u-card>
		</view>

	</view>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { onLoad } from '@dcloudio/uni-app';

const title = ref('Hello');

onLoad(() => {
  console.log('首页加载');
});

const goToFeature = (featureName: string, params?: object) => {
  let path = '';
  switch (featureName) {
    case 'watermark':
      path = '/pages/watermark/watermark';
      break;
    case 'text-extract':
      path = '/pages/text-extract/text-extract';
      break;
    case 'video-generate':
      path = '/pages/video-generate/video-generate';
      break;
    default:
      break;
  }
  if (path) {
    uni.navigateTo({
      url: path + (params ? `?${Object.keys(params).map(key => `${key}=${params[key]}`).join('&')}` : ''),
    });
  }
};
</script>

<style lang="scss">
.container {
	padding-bottom: 50rpx;
}

.feature-list {
	padding: 20rpx;
	background-color: #fff;
}

.grid-text {
	font-size: 26rpx;
	margin-top: 10rpx;
}

.section-title {
	padding: 0 20rpx;
	background-color: #fff;
	margin-top: 20rpx;
}

.popular-tools {
	padding: 0 20rpx;
	background-color: #fff;
	.u-card {
		margin-bottom: 20rpx;
	}
}
</style>
